# cm-metrics

CLI tool for fetching historical market metrics from CoinMetrics and exporting them to Parquet files for downstream analysis.

## Features

- Query CoinMetrics asset metrics by date range
- Validate requested symbols and metrics before export
- Export a pivoted time series table to parquet
- List available assets and metrics from the CoinMetrics catalog

## Requirements

- Python 3.10+
- Access to the CoinMetrics API
- Optional: `CM_API_KEY` environment variable for authenticated requests

## Installation

```bash
python -m pip install -e .
```

## Usage

### List available assets

```bash
cm-metrics list-symbols
```

### List available metrics for a symbol

```bash
cm-metrics list-metrics --symbol btc
```

### Fetch metrics for a set of symbols

Create a symbols file such as `symbols.txt`:

```text
btc/usd
eth/usd
sol/usd
```

Then run:

```bash
cm-metrics get \
  --metric PriceUSD \
  --symbols symbols.txt \
  --start 2024-01-01 \
  --end 2024-01-31 \
  --output data/priceusd.parquet
```

This reads the symbol list, validates each asset/metric pair, fetches the requested metric data, and writes a pivoted parquet table indexed by time.

## Environment

If you have a CoinMetrics API key, set it before running the CLI:

```bash
export CM_API_KEY="your-api-key"
```

On Windows PowerShell:

```powershell
$env:CM_API_KEY="your-api-key"
```

If no API key is provided, the client falls back to the community client behavior.

## Project layout

```text
cm-metrics/
├── README.md
├── pyproject.toml
├── src/
│   └── cm_metrics/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── client.py
│       └── symbol_map.py
└── .gitignore
```

## Notes

- The CLI expects one symbol per line in the input file.
- Symbols may be written as `BASE/QUOTE` or as a base asset name like `btc`.
- The output parquet file is created automatically if the parent directory does not exist.
