---
layout: default
title: SEMIF Database
parent: Dataset
nav_order: 1
---

# SEMIF Database
{: .no_toc }

Semi-Field Database - Optimized for machine learning training with precise bounding boxes and segmentation masks.
{: .fs-6 .fw-300 }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## Overview

<div class="db-card" markdown="1">

**Database Name:** SEMIF (Semi-Automated Field Database)

**Purpose:** Stores processed image cutouts/crops of individual plants with detailed bounding box annotations, taxonomy, and image characteristics. Optimized for machine learning training and synthetic image generation.

**Current release:** `{{ site.data.db_stats.database.file }}`, with {% include num.html n=site.data.db_stats.totals.rows %} rows and {{ site.data.db_stats.database.columns }} columns. Current counts by species and size class are on the [Statistics](statistics.html) page.


</div>

---

## Understanding SEMIF Records

{: .important }
> **Key Concept**: Each row in the SEMIF database represents a **single bounding box detection instance** (individual plant or plant part), not a complete image. Multiple detection instances may originate from the same source image. Images with no detections at all appear as a single placeholder row with `cutout_id = NULL`.

### Database Structure

The SEMIF database is organized around **bounding box detections** rather than images:

**Full-Sized Images**  
Standardized, color-corrected photos capturing entire scenes with multiple potted plants. Each source image has been processed to ensure consistent quality across the dataset. Images are identified by `image_id` and contain dimensions in `fullres_width` and `fullres_height`.

**Bounding Box Instances** *(Every Record)*  
Every row in SEMIF represents one bounding box detection. Each detection includes normalized coordinates in `xmin`, `ymin`, `xmax` and `ymax`, a unique `cutout_id`, and links back to its source image via `image_id`. Pixel coordinates in `bbox_xywh` are available for most detections.

**Cutout Images** *(Subset of Records)*  
Some detections have been processed to extract individual plant segments as separate cutout files. Availability is tracked **per detection**, so detections from the same image can differ. Check the `cutout_exists` field, or whether `cutout_juno_url` is filled, to determine availability.

### Detection Records: Bounding Boxes vs. Cutouts

{: .note }
> **Critical Distinction**: All detections have bounding box coordinates (`xmin`, `ymin`, `xmax`, `ymax`), but not all have extracted cutout images. Cutout availability is tracked per detection, so detections from the same `image_id` can have different `cutout_exists` values.

```
Source Image (image_id: IMG_001)
├── Image 1 (cutout_id: IMG_001_0) → bbox ✓ | cutout ✓
└── Image 1 (cutout_id: IMG_001_1) → bbox ✓ | cutout ✗

Source Image (image_id: IMG_002)
├── Image 2 (cutout_id: IMG_002_0) → bbox ✓ | cutout ✗
└── Image 2 (cutout_id: IMG_002_1) → bbox ✓ | cutout ✗
```

### What Every Detection Includes

**Mandatory (all detections):**
- **Unique identifier**: `cutout_id` specific to this detection
- **Source reference**: `image_id` linking back to the original full-sized image
- **Bounding box coordinates**: `xmin`, `ymin`, `xmax`, `ymax` defining the detection's location in the source image (normalized to 0-1)

**Optional (determined per detection):**
- **Extracted cutout image**: Path to the cropped image in `cutout_path` or `cropout_path`
- **Segmentation mask**: Pixel-level plant boundary in `cutout_mask_path`
- **Availability flag**: `cutout_exists` field (1 = cutout available, 0 = bbox only)
- **Download links**: `cutout_juno_url` and its sibling columns, filled only where the file exists

{: .tip }
> **Query Strategy**: Filter by `cutout_exists = 1` to get only records with extracted cutout images. All records can be used for object detection training with bounding boxes. Add `is_primary = 1` to keep one preferred view of each plant that appears in several overlapping images. When you also filter by `batch_id` or `category_usda_symbol`, `cutout_juno_url IS NOT NULL` selects the same rows as `cutout_exists = 1` and runs much faster.

<!-- <div class="stats-grid" markdown="1">

<div class="stat-card">
<span class="stat-number">62</span>
<span class="stat-label">Attributes</span>
</div>

<div class="stat-card">
<span class="stat-number">50K+</span>
<span class="stat-label">Cutouts</span>
</div>

<div class="stat-card">
<span class="stat-number">150+</span>
<span class="stat-label">Species</span>
</div>

<div class="stat-card">
<span class="stat-number">98%</span>
<span class="stat-label">Quality</span>
</div>

</div> -->

<!-- --- -->

<!-- ## Primary Use Cases

<div class="feature-grid" markdown="1">
 -->
<!-- <div class="feature-card" markdown="1"> -->
<!-- <div class="feature-icon">🤖</div> -->

<!-- **Machine Learning Training**  
Cutout images with precise bounding boxes for object detection models
</div> -->

<!-- <div class="feature-card" markdown="1"> -->
<!-- <div class="feature-icon">📊</div> -->

<!-- **Image Quality Analysis**  
Detailed metrics on blur, color characteristics, and component analysis
</div> -->

<!-- <div class="feature-card" markdown="1"> -->
<!-- <div class="feature-icon">🔍</div> -->

<!-- **Spatial Relationship Tracking**  
Overlap detection and management between multiple annotations
</div> -->

<!-- <div class="feature-card" markdown="1"> -->
<!-- <div class="feature-icon">🌿</div> -->

<!-- **Species-Level Identification**  
Taxonomic classification from cropped plant images
</div> -->

<!-- <div class="feature-card" markdown="1"> -->
<!-- <div class="feature-icon">🎯</div> -->

<!-- **Non-Target Weed Detection**  
Specialized classification with confidence scoring
</div> -->

<!-- <div class="feature-card" markdown="1"> -->
<!-- <div class="feature-icon">📐</div> -->

<!-- **Area Estimation**  
Multiple area metrics with categorical binning
</div> -->

<!-- </div> -->

---

## Schema Documentation

### 1. Temporal & Batch Information

Track when and how data was processed.

| Field | Type | Description |
|:------|:-----|:------------|
| `season` | String | Growing season identifier, for example `summer_weeds_2023` |
| `datetime` | String | Timestamp of image capture. **Mixed formats**: most rows look like `2022:06:25 01:11:08`, the rest like `2025-10-03T15:28:39`, so do not compare it as text. Use `batch_id` or `season` to select by date |
| `bbot_version` | String | Version of the field-robot software that captured the images (`2.0`, `3.0` or `3.1`) |
| `batch_id` | String | Site and capture date, for example `MD_2022-06-24`; also identifies the processing batch |

---

### 2. Image Metadata

Original source image information and camera settings.

| Field | Type | Description |
|:------|:-----|:------------|
| `image_id` | String | Unique identifier for the source image |
| `fullres_height` | Integer | Height of the full-resolution source image in pixels |
| `fullres_width` | Integer | Width of the full-resolution source image in pixels |
| `exif_meta` | String | EXIF metadata from the original image, packed as JSON |
| `camera_info` | String | Camera pose and calibration for the image (position, orientation, field of view, lens coefficients), packed as JSON |
| `lens_model` | String | Camera lens model used for capture |

---

### 3. File Paths & Storage

Locations and download links for images, masks, and metadata files.

| Field | Type | Description |
|:------|:-----|:------------|
| `image_path` | String | Path to the full source image |
| `mask_path` | String | Path to the segmentation mask file |
| `json_path` | String | Path to associated JSON metadata |
| `cropout_path` | String | Path to the JPEG crop of the detection |
| `cutout_path` | String | Path to the PNG cutout (transparent background) |
| `cutout_mask_path` | String | Path to the cutout's segmentation mask |
| `cutout_json_path` | String | Path to cutout's JSON metadata |
| `cropout_juno_url` | String | Direct-download URL for the crop; filled only where the file exists |
| `cutout_juno_url` | String | Direct-download URL for the cutout; filled only where the file exists |
| `cutout_mask_juno_url` | String | Direct-download URL for the cutout mask; filled only where the file exists |
| `cutout_json_juno_url` | String | Direct-download URL for the cutout metadata; filled only where the file exists |

{: .tip }
> **Crop vs. cutout**: `cropout_path` is a JPEG crop of the detection and `cutout_path` is the PNG cutout with a transparent background. These paths are derived from `cutout_id`, so use `cutout_exists` or the `*_juno_url` columns to confirm a file exists.

---

### 4. Annotation & Detection

Bounding boxes, masks, and detection metadata.

| Field | Type | Description |
|:------|:-----|:------------|
| `is_primary` | Integer | Boolean flag (0/1) marking the preferred detection when the same plant appears in overlapping images. `NULL` where not evaluated |
| `cutout_exists` | Integer | Boolean flag (0/1) indicating if the cutout file exists |
| `cutout_id` | String | Unique identifier for this cutout |
| `bbox_xywh` | String | Bounding box in pixels, [x, y, width, height] format. Filled for most, not all, detections |
| `category_class_id` | Integer | Numeric class identifier for the category |
| `overlapping_cutout_ids` | String | IDs of other cutouts that overlap with this one |
| `xmin`, `ymin`, `xmax`, `ymax` | Float | Bounding box in normalized image coordinates (0-1, top-left origin). Boxes near the image edge can fall slightly outside 0-1 |
| `det_classname` | String | Detector class: `plant` or `color_checker` |
| `det_confidence` | Float | Detector confidence, where recorded |
| `non_target_weed` | String | Off-target-weed flag: `'0'` or `'1'`, plus a stray literal `'non_target_weed'` in some rows. Use `IN ('0', '1')` for a clean flag |
| `non_target_weed_pred_conf` | Float | Model confidence for the `non_target_weed` flag |

**Example `bbox_xywh` format:**
```python
[245, 180, 120, 95] # [x_top_left, y_top_left, width, height]
```

---

### 5. Spatial Information

Geographic location and area measurements.

| Field | Type | Description |
|:------|:-----|:------------|
| `bbox_area_cm2` | Float | Measured bounding box area in square centimeters. Reliable only where `crs` is `LOCAL` |
| `estimated_bbox_area_cm2` | Float | Estimated bounding box area in square centimeters. Same caveat as `bbox_area_cm2` |
| `estimated_area_bin` | String | Categorical size bin for the estimated area, in cm²: `0-1`, `1-10`, `10-100`, `100-500`, `500-1000`, `1000-5000`, `5000-10000`, `10000+`. Only present for detections matched to the production database |
| `state` | String | US state where image was captured (`MD`, `NC` or `TX`) |
| `crs` | String | Coordinate reference system of `global_coordinates`: `LOCAL`, `32618`, `4326`, `32617` or `32614` |
| `global_coordinates` | String | Bounding box corners and centroid in world coordinates, packed as JSON (`top_left`, `top_right`, `bottom_left`, `bottom_right`, `global_centroid`). `NULL` when not georeferenced |
| `local_coordinates` | String | Pixel-space corners. Always `NULL` in this release |
| `pixel_area` | Float | `cutout_width * cutout_height`, in pixels |

---

### 6. Taxonomic Classification

Complete taxonomic hierarchy from kingdom to species.

| Field | Type | Description |
|:------|:-----|:------------|
| `category_usda_symbol` | String | USDA PLANTS database symbol code |
| `category_eppo_code` | String | European and Mediterranean Plant Protection Organization code |
| `category_group` | String | High-level taxonomic or functional group: `dicot`, `monocot`, `unknown`, `colorchecker` or `background` |
| `category_class` | String | Taxonomic class |
| `category_subclass` | String | Taxonomic subclass |
| `category_order` | String | Taxonomic order |
| `category_family` | String | Taxonomic family |
| `category_genus` | String | Taxonomic genus |
| `category_species` | String | Taxonomic species name |
| `category_common_name` | String | Common name of the plant |
| `category_authority` | String | Taxonomic authority citation |
| `category_multispecies` | String | JSON array of the component USDA symbols for catalog classes that cover several species (mostly `[]`) |

**Example taxonomy:**
```
Common Name: Barley
USDA Symbol: HOVU
Family: Poaceae
Genus: Hordeum
Species: vulgare
```

---

### 7. Plant Characteristics

Growth and life cycle information.

| Field | Type | Description |
|:------|:-----|:------------|
| `category_growth_habit` | String | Growth habit (e.g., graminoid, forb/herb, shrub) |
| `category_duration` | String | Life cycle duration (annual, biennial, perennial, or a combination) |

**Growth habits:**
- `graminoid` - Grass-like plant (grasses, sedges)
- `forb/herb` - Herbaceous flowering plant
- `forb/herb vine` - Herbaceous climbing/trailing plant
- `forb/herb, subshrub` - Herbaceous plant with a woody base
- `shrub` - Woody plant

---

### 8. Reference & Visualization

Links to external databases and display properties.

| Field | Type | Description |
|:------|:-----|:------------|
| `category_usda_link` | String | URL to USDA PLANTS database entry |
| `category_taxonomic_notes` | String | Additional taxonomic notes or clarifications |
| `category_hex` | String | Hexadecimal color code for visualization |
| `category_rgb` | String | RGB color values for visualization |
| `category_alias` | String | JSON array of alternative names (mostly `[]`) |

**Example color values:**
```
Hex: #4CAF50
RGB: (76, 175, 80)
```

---

### 9. Cutout Image Characteristics

Technical properties of the cropped image.

| Field | Type | Description |
|:------|:-----|:------------|
| `cutout_height` | Integer | Height of the cutout image in pixels |
| `cutout_width` | Integer | Width of the cutout image in pixels |
| `blur_effect` | Float | Sharpness score from 0 to 1 (higher is sharper) |
| `num_components` | Integer | Number of connected components in the segmentation |
| `cropout_rgb_mean` | String | Mean RGB values of the cutout image |
| `cropout_rgb_std` | String | Standard deviation of RGB values |
| `extends_border` | Integer | Boolean flag indicating if cutout extends to image border |

{: .tip }
> **Quality Filtering**: `blur_effect` runs from 0 to 1 with typical values around 0.3 to 0.4, so pick a cutoff from the distribution rather than a fixed number. Filter by `num_components` to find clean single-plant images.

**Example quality thresholds:**
```python
# Sharper half of the cutouts (the median is about 0.36)
blur_effect >= 0.36

# Single plant detection
num_components <= 2

# Not extending to border
extends_border == 0
```

---

### 10. Cultivar

Only populated for cultivar-tracking batches (mostly peanut trials).

| Field | Type | Description |
|:------|:-----|:------------|
| `cultivar_id` | Integer | Numeric cultivar class ID |
| `cultivar_name` | String | Cultivar name, for example `Peanut - Bailey II` |
| `cultivar_display_name` | String | Display name of the cultivar |
| `cultivar_line_name` | String | Breeding line name, when applicable |
| `cultivar_registered` | Integer | `1` for a registered cultivar, `0` for an experimental line |
| `cultivar_hex` | String | Display color as a hex code |
| `cultivar_r`, `cultivar_g`, `cultivar_b` | Integer | Display color as RGB components (0-255) |

---

## External Integrations

<div class="feature-grid" markdown="1">

<div class="feature-card" markdown="1">

**USDA PLANTS Database**  
Access via `category_usda_symbol` and `category_usda_link`

[Visit USDA PLANTS →](https://plants.usda.gov/)
</div>

<div class="feature-card" markdown="1">

**EPPO Database**  
Access via `category_eppo_code`

[Visit EPPO →](https://www.eppo.int/)
</div>


</div>


---

## Accessing the Data

{: .note }
> **Query this database** using the AgIR-CVToolkit. The toolkit provides powerful filtering, sampling, and export capabilities.

[View Complete Query Guide →](../access/query-tools.html){: .btn .btn-primary }

---

<!-- ## Next Steps

<div class="feature-grid" markdown="1">
       
<div class="feature-card" markdown="1">

**📊 View Statistics**  
Explore species distribution and data characteristics

[Statistics →](../statistics/overview.html)
</div>

<div class="feature-card" markdown="1">

**🖼️ See Examples**  
Browse sample images and annotations

[Gallery →](../examples/index.html)
</div>

<div class="feature-card" markdown="1">

**🔧 Access the Data**  
Learn how to query with AgIR-CVToolkit

[Query Documentation →](https://github.com/yourusername/AgIR-CVToolkit/blob/main/docs/PIPELINE_STAGES/01_query/)
</div>

<div class="feature-card" markdown="1">

**📚 Compare with FIELD**  
See the Field observation database

[FIELD Database →](field.html)
</div>

</div> -->