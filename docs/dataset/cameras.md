---
layout: default
title: Imaging Equipment
parent: Dataset
nav_order: 3
---

# Imaging Equipment
{: .no_toc }

Hardware specifications for the cameras, lenses, and illumination systems used to collect images in the AgIR dataset.
{: .fs-6 .fw-300 }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## Overview

Images in the AgIR SEMIF database were captured using the **BenchBot**, an aluminum gantry system designed for high-throughput, semi-controlled plant image collection. The BenchBot traverses nursery potting areas and acquires overlapping images that are subsequently processed using Structure from Motion (SfM) to reconstruct the potting area in 3D — enabling precise, automated labeling of each pot's location.

Two camera configurations have been used across collection seasons. The majority of images use the [Sony Alpha 7R IV](#primary-camera-sony-alpha-7r-iv), while more recent acquisitions use the [SVS-Vistek SHR 10GigE (shr661CXGE)](#machine-vision-camera-svs-vistek-shr-10gige-shr661cxge).

---

## Image Capture Strategy

To support accurate SfM reconstruction, images are captured with a minimum of **33% overlap** from both the front and side perspectives. To ensure consistent color reproduction across sessions, a **color calibration checkerboard** is photographed at the start of each collection day.

---

## Primary Camera: Sony Alpha 7R IV

The Sony Alpha 7R IV (ILCE-7RM4) is used for the majority of images in the dataset. Mounted on the BenchBot gantry, it is equipped with interchangeable lenses (55 mm or 35 mm) and a **Godox AR400 ring flash** for uniform illumination.

| Specification | Value |
|:--------------|:------|
| **Sensor** | Full-frame BSI Exmor R CMOS |
| **Effective Resolution** | 61.0 MP (9,504 × 6,336 px) |
| **Sensor Size** | 35.7 × 23.8 mm |
| **Pixel Pitch** | 3.76 µm |
| **ISO Range** | 100–32,000 (expandable 50–102,400) |
| **Shutter Speeds** | 1/8,000 s to 30 s |
| **Lens Mount** | Sony E-mount |
| **Lenses Used** | FE 55mm F1.8 ZA, FE 35mm |
| **Illumination** | Godox AR400 ring flash |

{: .note }
> The `lens_model` field in the SEMIF database records the specific lens used for each image (e.g., `FE 55mm F1.8 ZA`).

**References:** [Sony Alpha 7R IV Specifications](https://www.dpreview.com/products/sony/slrs/sony_a7riv/specifications)

---

## Machine Vision Camera: SVS-Vistek SHR 10GigE (shr661CXGE)

More recent images in the dataset were captured using the **SVS-Vistek SHR 10GigE (shr661CXGE)**, a high-resolution industrial machine vision camera. It is paired with the **Excelitas inspec.x L 4/60 lens** and a ring flash for illumination.

### Camera

| Specification | Value |
|:--------------|:------|
| **Model** | shr661CXGE |
| **Product Series** | SHR 10GigE |
| **Sensor** | Sony IMX661 (CMOS, global shutter) |
| **Resolution** | 13,392 × 9,528 (127.60 MP) |
| **Sensor Size** | 46.2 × 32.87 mm (Type 3.6) |
| **Pixel Size** | 3.45 µm × 3.45 µm |
| **Sensor Bit Depth** | 8-bit, 12-bit |
| **Pixel Formats** | bayer8, bayer12packed |
| **Spectral Range** | 400–1,000 nm |
| **Dynamic Range** | 74.4 dB |
| **SNR** | 41.5 dB |
| **Max Frame Rate** | 8.2 fps |
| **Exposure Time** | 163 µs to 60 s |
| **Gain** | 0.0–36.0 dB |
| **Interface** | 10GigE (RJ-45) |
| **Power Supply** | 10–25 VDC (or PoE+) |
| **Operating Temperature** | −10 °C to 60 °C |
| **Body Dimensions (L×W×H)** | 83 × 80 × 80 mm |
| **Weight** | 580 g |
| **Lens Mount** | M72×0.75 |

### Lens: Excelitas inspec.x L 4/60

| Specification | Value |
|:--------------|:------|
| **Model** | inspec.x L 4/60 (LINOS) |
| **Focal Length** | 60 mm |
| **Aperture** | f/4.0 |
| **Magnification Range** | 0 – 0.2× |
| **Max Image Circle** | 70.8 mm |
| **Interface** | M45×0.75 threaded (Modular Focus helical mount) |

{: .tip }
> The inspec.x L 4/60 is optimized for large-sensor imaging in space-constrained environments, providing exceptional contrast and low distortion over its full image circle — a good match for the IMX661's large 46 mm sensor.

**References:** [Excelitas inspec.x L 4/60 Product Page](https://www.excelitas.com/product/inspecx-l-460)

### Illumination

A **ring flash** is used with the SHR 10GigE configuration to provide uniform, shadow-free illumination consistent with the BenchBot's overhead capture geometry.

---

## Camera Comparison

| Feature | Sony Alpha 7R IV | SVS-Vistek shr661CXGE |
|:--------|:-----------------|:----------------------|
| **Sensor** | BSI CMOS (full-frame) | Sony IMX661 CMOS (global shutter) |
| **Resolution** | 61.0 MP (9,504 × 6,336) | 127.6 MP (13,392 × 9,528) |
| **Sensor Size** | 35.7 × 23.8 mm | 46.2 × 32.87 mm |
| **Pixel Size** | 3.76 µm | 3.45 µm |
| **Shutter** | Focal-plane (rolling) | Global shutter |
| **Interface** | Sony E-mount / USB | 10GigE (RJ-45) |
| **Primary Use** | Most dataset images | Recent acquisitions |
| **Lens(es)** | FE 55mm F1.8 ZA, FE 35mm | Excelitas inspec.x L 4/60 |
| **Illumination** | Godox AR400 ring flash | Ring flash |
