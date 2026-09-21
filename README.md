# AgIR-CVToolkit

Agricultural Image Repository Computer Vision Toolkit - query the SemiF and Field Agricultural Image Repository (AgIR) databases and fetch the matching files.

## Quick Start

```bash
# Install
pip install -e .

# Query database
agir-cv query --db semif --filters "state=NC" --limit 100

# Fetch the files for the last query from Juno (dry-run unless --submit is given)
agir-cv scinet-transfer
```

## What it does

1. **Query** - Filter, sample and export records from the SemiF/Field databases
2. **Transfer** - Pull the files for a query from Juno to SciNet with Globus

## Documentation

Full documentation available in `docs/` directory:
- [Getting Started](docs_copy/GETTING_STARTED/installation.md)
- [Pipeline Overview](docs_copy/GETTING_STARTED/pipeline_overview.md)
- [Configuration Guide](docs_copy/CONFIGURATION/hydra_config_quick_ref.md)

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