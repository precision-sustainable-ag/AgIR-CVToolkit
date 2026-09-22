# AgIR-CVToolkit

Agricultural Image Repository Computer Vision Toolkit - query the SemiF and Field Agricultural Image Repository (AgIR) databases and fetch the matching files.

## Quick Start

```bash
# Install (uv creates .venv and installs Python 3.13 if needed: https://docs.astral.sh/uv/)
uv sync

# Query database: big soybean cutouts (USDA symbol GLMA4)
uv run agir-cv query --db semif --filters "category_usda_symbol=GLMA4" --filters "estimated_area_bin=1000-5000,5000-10000,10000+" --limit 100

# Fetch the files for the last query from Juno (dry-run unless --submit is given)
uv run agir-cv scinet-transfer
```

## What it does

1. **Query** - Filter, sample and export records from the SemiF/Field databases
2. **Transfer** - Pull the files for a query from Juno to SciNet with Globus

## Structure

```
AgIR-CVToolkit/
├── src/agir_cvtoolkit/    # Main package
├── docs/                   # Full documentation
├── conf/                   # Configuration files
└── outputs/                # Pipeline outputs
```

## License

See LICENSE file for details.
