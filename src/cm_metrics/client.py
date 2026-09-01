import logging
import os
import time
from collections import deque
from datetime import date
from typing import List, Optional, Tuple

import pandas as pd
from coinmetrics.api_client import CoinMetricsClient

log = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: float = 6.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque = deque()

    def wait(self):
        now = time.monotonic()
        while self._timestamps and self._timestamps[0] <= now - self.window_seconds:
            self._timestamps.popleft()
        if len(self._timestamps) >= self.max_requests:
            sleep_time = self._timestamps[0] + self.window_seconds - now
            if sleep_time > 0:
                log.debug("Rate limit reached, sleeping %.2fs", sleep_time)
                time.sleep(sleep_time)
        self._timestamps.append(time.monotonic())


def _monthly_chunks(start: date, end: date) -> List[Tuple[date, date, bool]]:
    chunks = []
    current = start
    while current < end:
        if current.month == 12:
            next_month = current.replace(year=current.year + 1, month=1, day=1)
        else:
            next_month = current.replace(month=current.month + 1, day=1)
        is_last = next_month >= end
        chunk_end = end if is_last else next_month
        chunks.append((current, chunk_end, is_last))
        current = next_month
    return chunks


class MetricsClient:
    def __init__(self):
        api_key = os.environ.get("CM_API_KEY")
        kwargs = {"max_retries": 5}
        if api_key:
            log.info("Using API key from CM_API_KEY environment variable")
            self._client = CoinMetricsClient(api_key, **kwargs)
        else:
            log.info("No API key found, using community client")
            self._client = CoinMetricsClient(**kwargs)
        self._rate_limiter = RateLimiter()

    def get_asset_metrics(
        self,
        assets: List[str],
        metric: str,
        start_time: date,
        end_time: date,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        chunks = _monthly_chunks(start_time, end_time)
        frames = []

        for chunk_start, chunk_end, end_inclusive in chunks:
            log.info(
                "Fetching %s for %d assets from %s to %s",
                metric, len(assets), chunk_start.isoformat(), chunk_end.isoformat(),
            )
            self._rate_limiter.wait()
            data = self._client.get_asset_metrics(
                assets=assets,
                metrics=metric,
                frequency=frequency,
                start_time=chunk_start.isoformat(),
                end_time=chunk_end.isoformat(),
                end_inclusive=end_inclusive,
            ).to_dataframe()
            if data is not None and not data.empty:
                frames.append(data)
            else:
                log.warning(
                    "No data for %s from %s to %s",
                    metric, chunk_start.isoformat(), chunk_end.isoformat(),
                )

        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def validate_assets_and_metric(
        self, symbol_map: dict[str, str], metric: str
    ) -> Tuple[dict[str, str], dict[str, str]]:
        """Check which symbols and metric combos are available.

        Returns:
            valid: {base_asset: original_symbol} for supported combos
            skipped: {original_symbol: reason} for unsupported ones
        """
        all_assets = set(self.list_available_assets())

        valid_candidates = {}
        skipped = {}
        for base, original in symbol_map.items():
            if base in all_assets:
                valid_candidates[base] = original
            else:
                skipped[original] = "symbol not found in CoinMetrics catalog"

        if not valid_candidates:
            return {}, skipped

        self._rate_limiter.wait()
        catalog = self._client.catalog_asset_metrics_v2(
            assets=list(valid_candidates.keys()),
        ).to_list()

        valid = {}
        for item in catalog:
            base = item["asset"]
            original = valid_candidates[base]
            available = {m["metric"] for m in item.get("metrics", [])}
            if metric in available:
                valid[base] = original
            else:
                skipped[original] = f"metric '{metric}' not available for this symbol"

        return valid, skipped

    def list_available_assets(self) -> List[str]:
        self._rate_limiter.wait()
        catalog = self._client.catalog_asset_metrics_v2().to_list()
        return sorted(item["asset"] for item in catalog)

    def list_available_metrics(self, asset: Optional[str] = None) -> List[str]:
        kwargs = {}
        if asset:
            kwargs["assets"] = asset
        self._rate_limiter.wait()
        catalog = self._client.catalog_asset_metrics_v2(**kwargs).to_list()
        metrics = set()
        for item in catalog:
            for m in item.get("metrics", []):
                metrics.add(m["metric"])
        return sorted(metrics)
