import logging
from datetime import date
from pathlib import Path

import click
import pandas as pd

from .client import MetricsClient
from .symbol_map import parse_symbols_file


def _warn(msg: str) -> None:
    click.echo(click.style(f"Warning: {msg}", fg="yellow"), err=True)

def _error(msg: str) -> None:
    click.echo(click.style(msg, fg="red", bold=True), err=True)

def _success(msg: str) -> None:
    click.echo(click.style(msg, fg="green"))

def _info(msg: str) -> None:
    click.echo(click.style(msg, fg="cyan"))


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


@click.group()
@click.option("--verbose", is_flag=True, help="Show debug output")
def cli(verbose: bool) -> None:
    _setup_logging(verbose)


@cli.command()
@click.option("--metric", required=True, help="Metric name (e.g. PriceUSD, ReferenceRateUSD)")
@click.option(
    "--symbols",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="File with trading pairs (one BASE/QUOTE per line)",
)
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
@click.option("--output", required=True, help="Output parquet file path")
def get(metric: str, symbols: str, start: str, end: str, output: str) -> None:
    symbol_map = parse_symbols_file(symbols)
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)

    if start_date >= end_date:
        raise click.BadParameter("start must be before end", param_hint="--start/--end")

    client = MetricsClient()
    valid_map, skipped = client.validate_assets_and_metric(symbol_map, metric)

    for orig, reason in skipped.items():
        _warn(f"{orig} - {reason}")

    if not valid_map:
        _error("No valid symbols remaining to query")
        raise SystemExit(1)

    assets = list(valid_map.keys())
    df = client.get_asset_metrics(assets, metric, start_date, end_date)

    if df.empty:
        _error("No data returned for the given parameters")
        raise SystemExit(1)

    df = df.drop_duplicates(subset=["time", "asset"])
    df_pivot = df.pivot(index="time", columns="asset", values=metric)
    df_pivot.columns = [valid_map[col] for col in df_pivot.columns]
    df_pivot.columns.name = None

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_pivot.to_parquet(out_path)
    _success(f"Saved {len(df_pivot)} rows to {out_path}")


@cli.command()
@click.option("--symbol", default=None, help="Filter metrics by symbol (e.g. btc)")
def list_metrics(symbol: str) -> None:
    client = MetricsClient()
    metrics = client.list_available_metrics(asset=symbol)
    if not metrics:
        _error("No metrics found")
        raise SystemExit(1)
    label = f" Metrics for {symbol} " if symbol else " All available metrics "
    _info(f"{label}({len(metrics)})")
    for m in metrics:
        click.echo(m)


@cli.command()
def list_symbols() -> None:
    client = MetricsClient()
    assets = client.list_available_assets()
    if not assets:
        _error("No symbols found")
        raise SystemExit(1)
    _info(f" Available symbols ({len(assets)})")
    for a in assets:
        click.echo(a)
