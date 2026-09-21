---
layout: default
title: Statistics
parent: Dataset
nav_order: 4
description: "Current counts of detections, cutouts and primary cutouts in the AgIR database, by state, size class and species."
---

{% assign db = site.data.db_stats.database %}
{% assign t = site.data.db_stats.totals %}

# Database Statistics
{: .no_toc }

Current contents of **{{ db.file }}** (version {{ db.version }}, released {{ db.release }}). Counts generated {{ db.generated }}.
{: .fs-6 .fw-300 }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## At a glance

<div class="stats-grid" markdown="0">
  <div class="stat-card">
    <span class="stat-number">{% include compact_num.html n=t.images %}</span>
    <span class="stat-label">Images</span>
  </div>
  <div class="stat-card">
    <span class="stat-number">{% include compact_num.html n=t.detections %}</span>
    <span class="stat-label">Detections</span>
  </div>
  <div class="stat-card">
    <span class="stat-number">{% include compact_num.html n=t.cutouts %}</span>
    <span class="stat-label">Cutouts</span>
  </div>
  <div class="stat-card">
    <span class="stat-number">{% include compact_num.html n=t.primary_cutouts %}</span>
    <span class="stat-label">Primary cutouts</span>
  </div>
  <div class="stat-card">
    <span class="stat-number">{{ t.species }}</span>
    <span class="stat-label">Species</span>
  </div>
  <div class="stat-card">
    <span class="stat-number">{{ site.data.db_stats.by_state.size }}</span>
    <span class="stat-label">States</span>
  </div>
</div>

## What is counted

| Term | Meaning in the database | Count |
|:-----|:------------------------|------:|
| **Detection** | One bounding box in one image: a row with a `cutout_id`. | {% include num.html n=t.detections %} |
| **Cutout** | A detection whose cutout files are available for download (`cutout_exists = 1`). | {% include num.html n=t.cutouts %} |
| **Primary cutout** | A cutout with `is_primary = 1`: the preferred view of a plant that appears in several overlapping images. Use these to count each plant about once. | {% include num.html n=t.primary_cutouts %} |
| **Size class** | The `estimated_area_bin` column: bounding-box area in cm². Rows without a bin are shown as *Unbinned*. | – |

{% assign gap = t.primary_detections | minus: t.primary_cutouts %}
{: .note }
> The database holds {% include num.html n=t.rows %} rows in total: the {% include num.html n=t.detections %} detections plus {% include num.html n=t.images_without_detections %} placeholder rows for images with no detections. A further {% include num.html n=gap %} detections are flagged primary but do not have downloadable cutouts yet, so they are not counted as primary cutouts here.

---

## By state

<div class="table-wrapper" markdown="0">
<table class="sortable">
  <thead>
    <tr>
      <th>State</th>
      <th class="num">Batches</th>
      <th class="num">Images</th>
      <th class="num">Primary cutouts</th>
      <th class="num">Cutouts</th>
      <th class="num">Detections</th>
    </tr>
  </thead>
  <tbody>
{%- for r in site.data.db_stats.by_state %}
    <tr>
      <td>{% case r.state %}{% when "MD" %}Maryland{% when "NC" %}North Carolina{% when "TX" %}Texas{% else %}{{ r.state }}{% endcase %} ({{ r.state }})</td>
      <td class="num" data-sort="{{ r.batches }}">{% include num.html n=r.batches %}</td>
      <td class="num" data-sort="{{ r.images }}">{% include num.html n=r.images %}</td>
      <td class="num" data-sort="{{ r.primary_cutouts }}">{% include num.html n=r.primary_cutouts %}</td>
      <td class="num" data-sort="{{ r.cutouts }}">{% include num.html n=r.cutouts %}</td>
      <td class="num" data-sort="{{ r.detections }}">{% include num.html n=r.detections %}</td>
    </tr>
{%- endfor %}
    <tr class="total-row">
      <td><strong>Total</strong></td>
      <td class="num"><strong>{% include num.html n=t.batches %}</strong></td>
      <td class="num"><strong>{% include num.html n=t.images %}</strong></td>
      <td class="num"><strong>{% include num.html n=t.primary_cutouts %}</strong></td>
      <td class="num"><strong>{% include num.html n=t.cutouts %}</strong></td>
      <td class="num"><strong>{% include num.html n=t.detections %}</strong></td>
    </tr>
  </tbody>
</table>
</div>

---

## By size class

Size class is the bounding-box area in cm² (`estimated_area_bin`). It is only available for detections that were matched to the original production database, so a share of newer detections is *Unbinned*, and all primary cutouts have a size class.

<div class="table-wrapper" markdown="0">
<table class="sortable">
  <thead>
    <tr>
      <th>Size class</th>
      <th class="num">Primary cutouts</th>
      <th class="num">Cutouts</th>
      <th class="num">Detections</th>
    </tr>
  </thead>
  <tbody>
{%- for r in site.data.db_stats.by_size %}
    <tr>
      <td data-sort="{{ forloop.index }}">{% if r.size_class == "unbinned" %}Unbinned{% else %}{{ r.size_class }} cm²{% endif %}</td>
      <td class="num" data-sort="{{ r.primary_cutouts }}">{% if r.primary_cutouts == 0 %}–{% else %}{% include num.html n=r.primary_cutouts %}{% endif %}</td>
      <td class="num" data-sort="{{ r.cutouts }}">{% include num.html n=r.cutouts %}</td>
      <td class="num" data-sort="{{ r.detections }}">{% include num.html n=r.detections %}</td>
    </tr>
{%- endfor %}
    <tr class="total-row">
      <td><strong>Total</strong></td>
      <td class="num"><strong>{% include num.html n=t.primary_cutouts %}</strong></td>
      <td class="num"><strong>{% include num.html n=t.cutouts %}</strong></td>
      <td class="num"><strong>{% include num.html n=t.detections %}</strong></td>
    </tr>
  </tbody>
</table>
</div>

---

## By species

Sorted by primary cutouts. {{ t.species_with_cutouts }} of the {{ t.species }} species have cutouts so far; the rest have detections only. Rows marked † are catalog classes rather than species (`unknown`, `colorchecker`, `background`).

<div class="table-wrapper" markdown="0">
<table class="sortable">
  <thead>
    <tr>
      <th>Species</th>
      <th>USDA symbol</th>
      <th>Group</th>
      <th class="num">Primary cutouts</th>
      <th class="num">Cutouts</th>
      <th class="num">Detections</th>
    </tr>
  </thead>
  <tbody>
{%- for sp in site.data.db_stats.species %}
    <tr>
      <td>{{ sp.name }}{% unless sp.is_species %} †{% endunless %}</td>
      <td><code>{{ sp.symbol }}</code></td>
      <td>{{ sp.group }}</td>
      <td class="num" data-sort="{{ sp.primary_cutouts }}">{% if sp.primary_cutouts == 0 %}–{% else %}{% include num.html n=sp.primary_cutouts %}{% endif %}</td>
      <td class="num" data-sort="{{ sp.cutouts }}">{% if sp.cutouts == 0 %}–{% else %}{% include num.html n=sp.cutouts %}{% endif %}</td>
      <td class="num" data-sort="{{ sp.detections }}">{% include num.html n=sp.detections %}</td>
    </tr>
{%- endfor %}
    <tr class="total-row">
      <td><strong>Total</strong></td>
      <td></td>
      <td></td>
      <td class="num"><strong>{% include num.html n=t.primary_cutouts %}</strong></td>
      <td class="num"><strong>{% include num.html n=t.cutouts %}</strong></td>
      <td class="num"><strong>{% include num.html n=t.detections %}</strong></td>
    </tr>
  </tbody>
</table>
</div>

---

## Primary cutouts by species and size class

Species with at least one primary cutout. Columns are size classes in cm².

<div class="table-wrapper" markdown="0">
<table class="sortable">
  <thead>
    <tr>
      <th>Species</th>
{%- for s in site.data.db_stats.size_classes %}
      <th class="num">{{ s }}</th>
{%- endfor %}
      <th class="num">Total</th>
    </tr>
  </thead>
  <tbody>
{%- for sp in site.data.db_stats.species %}
{%- if sp.primary_cutouts > 0 %}
    <tr>
      <td>{{ sp.name }}{% unless sp.is_species %} †{% endunless %}</td>
{%- for v in sp.primary_by_size %}
      <td class="num" data-sort="{{ v }}">{% if v == 0 %}–{% else %}{% include num.html n=v %}{% endif %}</td>
{%- endfor %}
      <td class="num" data-sort="{{ sp.primary_cutouts }}"><strong>{% include num.html n=sp.primary_cutouts %}</strong></td>
    </tr>
{%- endif %}
{%- endfor %}
    <tr class="total-row">
      <td><strong>Total</strong></td>
{%- for s in site.data.db_stats.by_size %}
{%- unless s.size_class == "unbinned" %}
      <td class="num"><strong>{% include num.html n=s.primary_cutouts %}</strong></td>
{%- endunless %}
{%- endfor %}
      <td class="num"><strong>{% include num.html n=t.primary_cutouts %}</strong></td>
    </tr>
  </tbody>
</table>
</div>

---

## Check these numbers yourself

The database ships with a pre-aggregated view, `v_cutout_summary`, that returns cutout counts by species, size class and primary flag in well under a second:

```sql
-- Primary cutouts per species and size class
SELECT category_common_name, estimated_area_bin, cutout_count
FROM v_cutout_summary
WHERE is_primary = 1
ORDER BY category_common_name, estimated_area_bin;

-- Detections (every row that has a cutout_id)
SELECT COUNT(*) FROM semif WHERE cutout_id IS NOT NULL;
```

See the [Query Guide](../access/query-tools.html) for the command-line tool.

<script>
{% raw %}
/* Click a column header to sort a table that has the class "sortable".
   Numbers sort by the data-sort value (or the cell text), text sorts alphabetically,
   and the Total row stays at the bottom. Without JavaScript the tables keep their default order.
   NOTE: use only block comments here. The site's production build joins all lines into one,
   so a line comment would comment out the rest of the script. Also avoid tag-like text in comments. */
(function () {
  function keyOf(cell) {
    var raw = (cell.hasAttribute('data-sort') ? cell.getAttribute('data-sort') : cell.textContent).trim();
    var num = Number(raw);
    return raw !== '' && !isNaN(num) ? num : raw.toLowerCase();
  }

  function makeSortable(table) {
    var head = table.tHead && table.tHead.rows[0];
    var body = table.tBodies[0];
    if (!head || !body) return;
    var all = Array.prototype.slice.call(body.rows);
    var totals = all.filter(function (r) { return r.classList.contains('total-row'); });
    var rows = all.filter(function (r) { return !r.classList.contains('total-row'); });
    rows.forEach(function (r, i) { r._order = i; });   /* default order, used to break ties */

    Array.prototype.forEach.call(head.cells, function (th, col) {
      th.classList.add('sortable-col');
      th.tabIndex = 0;

      function sort() {
        var current = th.getAttribute('aria-sort');
        var numericColumn = th.classList.contains('num');
        /* first click: biggest first for counts, A-Z for text; click again to reverse */
        var dir = current ? (current === 'ascending' ? 'descending' : 'ascending')
                          : (numericColumn ? 'descending' : 'ascending');
        Array.prototype.forEach.call(head.cells, function (h) { h.removeAttribute('aria-sort'); });
        th.setAttribute('aria-sort', dir);
        var sign = dir === 'ascending' ? 1 : -1;
        rows.sort(function (a, b) {
          var x = keyOf(a.cells[col]), y = keyOf(b.cells[col]);
          var c = (typeof x === 'number' && typeof y === 'number') ? x - y : String(x).localeCompare(String(y));
          return c !== 0 ? sign * c : a._order - b._order;
        });
        rows.forEach(function (r) { body.appendChild(r); });
        totals.forEach(function (r) { body.appendChild(r); });
      }

      th.addEventListener('click', sort);
      th.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); sort(); }
      });
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll('table.sortable'), makeSortable);
})();
{% endraw %}
</script>
