---
layout: default
title: Access & Query
nav_order: 4
has_children: true
---

# Access the Dataset
{: .no_toc }

Querying and accessing data from the AgIR dataset.
{: .fs-6 .fw-300 }

{: .note }
> Access only available to USDA SciNet users. Public access coming soon.

---

## Two Ways to Query

**AgIR-CVToolkit (recommended)** is a command-line tool and Python API for filtering, sampling and exporting records. It suits building datasets and reproducible queries.

1. [Installation & Setup](installation.html): install with uv and point the toolkit at the database
2. [SciNet Setup](scinet-usage.html): copy the database and fetch files on SciNet
3. [Query Guide](query-tools.html): filters, sampling and exports

**Direct SQL** works with any SQLite tool. See the [SemiF schema](../dataset/semif.html) for every column and [Statistics](../dataset/statistics.html) for what the database holds.

---

## Quick Examples

### AgIR-CVToolkit

```bash
# 100 primary cutouts of barley (USDA symbol HOVU)
agir-cv query --db semif \
  --filters "category_usda_symbol=HOVU" \
  --filters "cutout_juno_url is not null" --filters "is_primary=1" \
  --limit 100

# A balanced set: 20 primary cutouts per species
agir-cv query --db semif \
  --filters "category_usda_symbol=HOVU,PISA6,SECE" \
  --filters "cutout_juno_url is not null" --filters "is_primary=1" \
  --sample "stratified:by=category_common_name,per_group=20"
```

{: .warning }
> Always set `--limit` or a sample. Without one, a query exports every matching row.

[See more examples →](query-tools.html)

### Direct SQL

```sql
SELECT cutout_id, category_common_name, estimated_area_bin, cutout_juno_url
FROM semif
WHERE category_usda_symbol = 'HOVU'
  AND is_primary = 1
  AND cutout_juno_url IS NOT NULL
LIMIT 100;
```

---

## Documentation Map

| Documentation | Purpose |
|---------------|---------|
| [Installation & Setup](installation.html) | Install AgIR-CVToolkit and set the database path |
| [SciNet Setup](scinet-usage.html) | Copy the database and transfer files on SciNet |
| [Query Guide](query-tools.html) | Filter, sample and export data |
| [SemiF Schema](../dataset/semif.html) | Individual plant cutouts - {{ site.data.db_stats.database.columns }} fields |
| [Statistics](../dataset/statistics.html) | Counts by species, size class and state |

---

## Need Help?

Start with [Installation & Setup](installation.html), or report a problem on [GitHub Issues](https://github.com/precision-sustainable-ag/AgIR-CVToolkit/issues).
