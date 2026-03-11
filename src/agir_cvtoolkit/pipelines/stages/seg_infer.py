"""
Segmentation inference pipeline stage - Refactored.

Usage:
    agir-cvtoolkit infer-seg --override model.ckpt_path=/path/to/model.ckpt
"""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import torch
from omegaconf import DictConfig
from PIL import Image, ImageEnhance
from tqdm import tqdm

from agir_cvtoolkit.core.db import AgirDB
from agir_cvtoolkit.pipelines.utils.seg_utils import (
    SegModel,
    TiledInference,
    SegPostProcessor,
    SegVisualizer,
    load_image_from_record,
    select_available_gpus,
)

import logging
log = logging.getLogger(__name__)


# ============================================================================
# Data Classes for Configuration
# ============================================================================

@dataclass
class InferenceConfig:
    """Configuration extracted from DictConfig for easier access."""
    # Source
    source_type: str
    db_name: str
    image_mode: str
    
    # Custom mode
    custom_enabled: bool
    custom_mode: Optional[str]
    custom_image_dir: Optional[Path]
    custom_label_json_path: Optional[Path]
    
    # Model
    model_ckpt: Path
    
    # Post-processing
    threshold: float
    min_area: int
    edge_threshold: Optional[float]
    
    # Output
    save_masks: bool
    save_images: bool
    save_cutouts: bool
    save_viz: bool
    save_colorized: bool
    cutout_use_rgba: bool
    
    # Colorization
    colorize_brightness: float
    colorize_rgb_field: str
    
    @classmethod
    def from_hydra(cls, cfg: DictConfig) -> InferenceConfig:
        """Create InferenceConfig from Hydra DictConfig."""
        seg_cfg = cfg.seg_inference
        source = seg_cfg.source
        custom = source.get("custom", {})
        output = seg_cfg.output
        
        return cls(
            source_type=source.type,
            db_name=source.db,
            image_mode=source.get("image_mode", "cutout"),
            custom_enabled=custom.get("enabled", False),
            custom_mode=custom.get("mode"),
            custom_image_dir=Path(custom["image_dir"]) if custom.get("image_dir") else None,
            custom_label_json_path=Path(custom["label_json_path"]) if custom.get("label_json_path") else None,
            model_ckpt=Path(seg_cfg.model.ckpt_path),
            threshold=seg_cfg.post_process.threshold,
            min_area=seg_cfg.post_process.get("min_area", 0),
            edge_threshold=seg_cfg.post_process.get("edge_occupancy_threshold"),
            save_masks=output.get("save_masks", True),
            save_images=output.get("save_images", False),
            save_cutouts=output.get("save_cutouts", True),
            save_viz=output.get("save_viz", False),
            save_colorized=output.get("save_colorized_masks", False),
            cutout_use_rgba=output.get("cutout_use_rgba", False),
            colorize_brightness=output.get("colorize_brightness", 6.5),
            colorize_rgb_field=output.get("colorize_rgb_field", "category_rgb"),
        )


# ============================================================================
# Record Loading
# ============================================================================

class RecordLoader:
    """Handles loading records from various sources."""
    
    def __init__(self, cfg: DictConfig, infer_cfg: InferenceConfig):
        self.cfg = cfg
        self.infer_cfg = infer_cfg
        self.run_root = Path(cfg.paths.run_root)
    
    def load_records(self) -> List[Dict]:
        """Load records based on configured source type."""
        if self.infer_cfg.custom_enabled:
            return self._load_custom_records()
        elif self.infer_cfg.source_type == "query_result":
            return self._load_query_results()
        elif self.infer_cfg.source_type == "db_query":
            return self._load_db_query()
        else:
            raise ValueError(f"Unknown source type: {self.infer_cfg.source_type}")
    
    def _load_custom_records(self) -> List[Dict]:
        """Load records from custom JSON file."""
        log.info("Loading records from custom source...")
        json_path = self.infer_cfg.custom_label_json_path
        
        if not json_path or not json_path.exists():
            raise FileNotFoundError(f"Custom label JSON not found: {json_path}")
        
        with open(json_path, 'r') as f:
            records = json.load(f)
        
        log.info(f"Loaded {len(records)} records from custom source")
        return records
    
    def _load_query_results(self) -> List[Dict]:
        """Load records from previous query stage results."""
        query_json = self.run_root / "query" / "query.json"
        query_csv = self.run_root / "query" / "query.csv"
        
        # Try JSON first
        if query_json.exists():
            log.info(f"Loading records from: {query_json}")
            with open(query_json) as f:
                return json.load(f)
        
        # Fall back to CSV
        if query_csv.exists():
            log.info(f"Loading records from: {query_csv}")
            return self._load_csv_records(query_csv)
        
        raise FileNotFoundError("No previous query results found (query.json or query.csv)")
    
    def _load_csv_records(self, csv_path: Path) -> List[Dict]:
        """Load and process CSV records."""
        try:
            df = pd.read_csv(csv_path)
        except pd.errors.EmptyDataError:
            log.info("CSV file is empty")
            return []
        
        if df.empty:
            return []
        
        log.info(f"Loaded {len(df)} records from CSV")
        
        # Clean up data
        df = df.where(pd.notnull(df), None)
        df = df[df['bbox_xywh'].notna() & (df['bbox_xywh'] != '')]
        
        log.info(f"Filtered to {len(df)} valid records")
        return df.to_dict(orient="records")
    
    def _load_db_query(self) -> List[Dict]:
        """Run fresh database query."""
        log.info("Running fresh database query...")
        
        source_cfg = self.cfg.seg_inference.source
        db_cfg = self.cfg.db[self.infer_cfg.db_name]
        
        with AgirDB.connect(
            db_type=self.infer_cfg.db_name,
            db_path=db_cfg.db_path,
            table=db_cfg.get("table"),
        ) as db:
            query = db.builder()
            
            # Apply filters
            if source_cfg.get("filters"):
                for key, value in source_cfg.filters.items():
                    query = query.filter(**{key: value})
            
            # Apply sampling
            if source_cfg.get("sample"):
                query = self._apply_sampling(query, source_cfg.sample)
            
            # Apply limit
            if source_cfg.get("limit"):
                query = query.limit(source_cfg.limit)
            
            records = query.all()
            
            # Convert to dict format
            from agir_cvtoolkit.pipelines.utils.serializers import _rec_to_dict
            return [_rec_to_dict(r) for r in records]
    
    @staticmethod
    def _apply_sampling(query, sample_cfg):
        """Apply sampling strategy to query."""
        strategy = sample_cfg.strategy
        
        if strategy == "stratified":
            return query.sample_stratified(
                by=sample_cfg.by,
                per_group=sample_cfg.per_group,
                seed=sample_cfg.get("seed"),
            )
        elif strategy == "random":
            return query.sample_random(sample_cfg.n)
        elif strategy == "seeded":
            return query.sample_seeded(sample_cfg.n, sample_cfg.get("seed", 42))
        
        return query


# ============================================================================
# Image Processing
# ============================================================================

class ImageProcessor:
    """Handles image loading and inference."""
    
    def __init__(
        self,
        cfg: DictConfig,
        infer_cfg: InferenceConfig,
        model: SegModel,
        tiled_inference: TiledInference,
        device: torch.device,
    ):
        self.cfg = cfg
        self.infer_cfg = infer_cfg
        self.model = model
        self.tiled_inference = tiled_inference
        self.device = device
    
    def load_image(self, record: Dict) -> Optional[np.ndarray]:
        """Load image from record based on mode."""
        if self.infer_cfg.custom_enabled:
            return self._load_custom_image(record)
        
        return load_image_from_record(
            record,
            self.cfg,
            image_mode=self.infer_cfg.image_mode
        )
    
    def _load_custom_image(self, record: Dict) -> Optional[np.ndarray]:
        """Load image from custom directory."""
        img_path = record.get("image_path")
        if not img_path:
            log.warning(f"No image_path in custom record")
            return None
        
        img_path = Path(img_path)
        if not img_path.exists():
            log.warning(f"Custom image not found: {img_path}")
            return None
        
        return np.array(Image.open(img_path).convert("RGB"))
    
    def run_inference(self, img: np.ndarray) -> tuple[np.ndarray, float]:
        """Run tiled inference and return mask + inference time."""
        t0 = perf_counter()
        pred_mask = self.tiled_inference.predict(
            img_rgb_u8=img,
            model=self.model,
            device=self.device,
        )
        inference_time_ms = int((perf_counter() - t0) * 1000)
        return pred_mask, inference_time_ms
    
    def process_bboxes(
        self,
        img: np.ndarray,
        bboxes: List[Dict],
    ) -> List[tuple[str, np.ndarray, np.ndarray, float]]:
        """Process multiple bounding boxes within an image.
        
        Returns:
            List of (cutout_id, cutout_img, pred_mask, inference_time_ms)
        """
        results = []
        
        for bbox_record in bboxes:
            cutout_id = bbox_record.get("cutout_id", "unknown")
            bbox_xywh = bbox_record.get("bbox_xywh")
            
            if bbox_xywh is None:
                continue
            
            # Extract bbox region
            x = int(bbox_xywh[0] - bbox_xywh[2] / 2)
            y = int(bbox_xywh[1] - bbox_xywh[3] / 2)
            w = int(bbox_xywh[2])
            h = int(bbox_xywh[3])
            cutout_img = img[y:y+h, x:x+w]
            
            if cutout_img.size == 0:
                log.warning(f"Empty cutout for bbox {cutout_id}")
                continue
            
            # Run inference on cutout
            pred_mask, inference_time_ms = self.run_inference(cutout_img)
            results.append((cutout_id, cutout_img, pred_mask, inference_time_ms))
        
        return results


# ============================================================================
# Output Management
# ============================================================================

class OutputManager:
    """Handles saving all outputs (masks, images, cutouts, visualizations)."""
    
    def __init__(
        self,
        cfg: DictConfig,
        infer_cfg: InferenceConfig,
        visualizer: Optional[SegVisualizer],
    ):
        self.cfg = cfg
        self.infer_cfg = infer_cfg
        self.paths = cfg.paths
        self.visualizer = visualizer
    
    def save_outputs(
        self,
        record_id: str,
        record: Dict,
        img: np.ndarray,
        mask: np.ndarray,
        edge_occupancy: float,
    ) -> Dict[str, Optional[str]]:
        """Save all configured outputs and return paths."""
        paths = {}
        
        # Save mask
        if self.infer_cfg.save_masks:
            paths['mask_path'] = self._save_mask(record_id, mask)
        
        # Save colorized mask
        if self.infer_cfg.save_colorized and self.infer_cfg.save_masks:
            paths['colorized_mask_path'] = self._save_colorized_mask(
                record_id, record, paths.get('mask_path')
            )
        
        # Save image
        if self.infer_cfg.save_images:
            paths['image_path'] = self._save_image(record_id, img)
        
        # Save cutout
        if self.infer_cfg.save_cutouts:
            paths['cutout_path'] = self._save_cutout(record_id, img, mask)
        
        # Save visualization
        if self.infer_cfg.save_viz and self.visualizer:
            area_bin = record.get("area_bin", "")
            paths['viz_path'] = self._save_visualization(
                record_id, record, img, mask, edge_occupancy, area_bin
            )
        
        return paths
    
    def _save_mask(self, record_id: str, mask: np.ndarray) -> str:
        """Save prediction mask."""
        mask_path = Path(self.paths.masks) / f"{record_id}.png"
        mask_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(mask, mode="L").save(mask_path)
        log.debug(f"Saved mask: {mask_path}")
        return str(mask_path)
    
    def _save_colorized_mask(
        self,
        record_id: str,
        record: Dict,
        mask_path: Optional[str],
    ) -> Optional[str]:
        """Save colorized mask."""
        if not mask_path:
            return None
        
        colorized_path = Path(self.paths.colorized_masks) / f"{record_id}.png"
        rgb_value = self._get_rgb_from_record(record)
        
        try:
            self._colorize_mask(
                mask_path=Path(mask_path),
                rgb_value=rgb_value,
                out_path=colorized_path,
                brightness=self.infer_cfg.colorize_brightness,
            )
            log.debug(f"Saved colorized mask: {colorized_path}")
            return str(colorized_path)
        except Exception as e:
            log.error(f"Failed to colorize mask: {e}")
            return None
    
    def _save_image(self, record_id: str, img: np.ndarray) -> str:
        """Save source image."""
        img_path = Path(self.paths.images) / f"{record_id}.jpg"
        img_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(img, mode="RGB").save(
            img_path, format="JPEG", quality=100, subsampling=0, optimize=False
        )
        log.debug(f"Saved image: {img_path}")
        return str(img_path)
    
    def _save_cutout(
        self,
        record_id: str,
        img: np.ndarray,
        mask: np.ndarray,
    ) -> str:
        """Save masked cutout."""
        cutout_path = Path(self.paths.cutouts) / f"{record_id}.png"
        cutout_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._save_cutout_image(
            img, mask, cutout_path,
            use_rgba=self.infer_cfg.cutout_use_rgba
        )
        log.debug(f"Saved cutout: {cutout_path}")
        return str(cutout_path)
    
    def _save_visualization(
        self,
        record_id: str,
        record: Dict,
        img: np.ndarray,
        mask: np.ndarray,
        edge_occupancy: float,
        area_bin: str,
    ) -> str:
        """Save visualization."""
        viz_path = Path(self.paths.plots) / f"area_{area_bin}_{record_id}_viz.png"
        viz_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.visualizer.plot_quad(
            record=record,
            img_rgb_u8=img,
            pred_mask=mask,
            out_path=viz_path,
            edge_occupancy=edge_occupancy,
        )
        log.debug(f"Saved visualization: {viz_path}")
        return str(viz_path)
    
    def _get_rgb_from_record(self, record: Dict) -> Any:
        """Extract RGB value from record."""
        # Try primary field
        rgb_value = record.get(self.infer_cfg.colorize_rgb_field)
        if rgb_value:
            return rgb_value
        
        # Try fallback fields
        for field in ["category_rgb", "rgb", "category_hex"]:
            if field in record and record.get(field):
                log.debug(f"Using RGB from fallback field: {field}")
                return record[field]
        
        # Use default fallback
        log.warning("No RGB field found, using fallback color")
        return [0, 255, 0]
    
    def _colorize_mask(
        self,
        mask_path: Path,
        rgb_value: Any,
        out_path: Path,
        brightness: float = 6.5,
    ) -> None:
        """Colorize a grayscale mask."""
        if not mask_path.exists():
            raise FileNotFoundError(f"Mask not found: {mask_path}")
        
        # Load grayscale mask
        mask_img = Image.open(mask_path).convert("L")
        
        # Parse RGB value
        rgb = self._parse_rgb(rgb_value)
        
        # Create colored composite
        color_img = Image.new("RGB", mask_img.size, rgb)
        black_img = Image.new("RGB", mask_img.size, (0, 0, 0))
        
        # Binarize mask for compositing
        mask_np = np.array(mask_img)
        mask_np = np.where(mask_np > 0, 255, 0).astype(np.uint8)
        mask_img = Image.fromarray(mask_np, mode="L")
        
        colorized = Image.composite(color_img, black_img, mask_img)
        
        # Brighten for better visualization
        if brightness != 1.0:
            enhancer = ImageEnhance.Brightness(colorized)
            colorized = enhancer.enhance(brightness)
        
        # Save
        out_path.parent.mkdir(parents=True, exist_ok=True)
        colorized.save(out_path)
    
    def _parse_rgb(self, rgb_value: Any) -> tuple:
        """Parse RGB value from various formats."""
        try:
            if isinstance(rgb_value, str):
                rgb_value = ast.literal_eval(rgb_value)
            
            if isinstance(rgb_value, (list, tuple)) and len(rgb_value) == 3:
                # Normalize to 0-255
                if all(0.0 <= float(v) <= 1.0 for v in rgb_value):
                    return tuple(int(float(v) * 255) for v in rgb_value)
                else:
                    return tuple(int(v) for v in rgb_value)
            
            log.warning(f"Invalid RGB format: {rgb_value}")
            return (0, 255, 0)
        
        except Exception as e:
            log.warning(f"Error parsing RGB: {e}")
            return (0, 255, 0)
    
    @staticmethod
    def _save_cutout_image(
        img: np.ndarray,
        mask: np.ndarray,
        path: Path,
        use_rgba: bool = False,
        hard_binary: bool = False,
        thresh: int = 128,
    ) -> None:
        """Save cutout image with masked pixels."""
        assert img.ndim == 3 and img.shape[2] == 3
        h, w = img.shape[:2]
        assert mask.shape[:2] == (h, w)
        
        # Normalize mask to uint8 [0, 255]
        alpha = OutputManager._normalize_mask(mask)
        
        if hard_binary:
            alpha = (alpha >= thresh).astype(np.uint8) * 255
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if use_rgba:
            # RGBA with transparency
            rgba = np.zeros((h, w, 4), dtype=np.uint8)
            rgba[:, :, :3] = img
            rgba[:, :, 3] = alpha
            
            # Clear RGB where fully transparent
            fully_transparent = (alpha == 0)
            if np.any(fully_transparent):
                rgba[fully_transparent, :3] = 0
            
            Image.fromarray(rgba, mode="RGBA").save(path, format="PNG")
        else:
            # RGB with black background
            masked = np.zeros_like(img, dtype=np.uint8)
            vis = alpha > 0
            masked[vis] = img[vis]
            Image.fromarray(masked, mode="RGB").save(path, format="PNG")
    
    @staticmethod
    def _normalize_mask(mask: np.ndarray) -> np.ndarray:
        """Normalize mask to uint8 [0, 255]."""
        if mask.dtype == np.bool_:
            return mask.astype(np.uint8) * 255
        
        m = mask.astype(np.float32)
        m_min, m_max = float(np.min(m)), float(np.max(m))
        
        if m_max <= 1.0:
            return (m * 255.0).round().astype(np.uint8)
        elif m_max <= 255.0:
            if m_max > 0 and m_max < 255:
                return (m * (255.0 / m_max)).clip(0, 255).round().astype(np.uint8)
            else:
                return m.clip(0, 255).round().astype(np.uint8)
        else:
            return ((m - m_min) / max(1e-6, (m_max - m_min)) * 255.0).round().astype(np.uint8)


# ============================================================================
# Main Inference Stage
# ============================================================================

class SegmentationInferenceStage:
    """Refactored segmentation inference pipeline stage."""
    
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.infer_cfg = InferenceConfig.from_hydra(cfg)
        self.paths = cfg.paths
        self.run_root = Path(cfg.paths.run_root)
        
        # Setup components
        self.device = self._setup_device()
        self.model = self._load_model()
        
        self.tiled_inference = TiledInference(
            tile_h=cfg.seg_inference.tile.height,
            tile_w=cfg.seg_inference.tile.width,
            overlap=cfg.seg_inference.tile.overlap,
            pad_mode=cfg.seg_inference.tile.pad_mode,
            pad_divisor=cfg.seg_inference.model.pad_divisor,
        )
        
        self.post_processor = SegPostProcessor(
            threshold=self.infer_cfg.threshold,
            min_area=self.infer_cfg.min_area,
            edge_occupancy_threshold=self.infer_cfg.edge_threshold,
        )
        
        self.visualizer = (
            SegVisualizer(overlay_alpha=cfg.seg_inference.visualization.overlay_alpha)
            if cfg.seg_inference.visualization.enabled else None
        )
        
        # Setup helper components
        self.record_loader = RecordLoader(cfg, self.infer_cfg)
        self.image_processor = ImageProcessor(
            cfg, self.infer_cfg, self.model, self.tiled_inference, self.device
        )
        self.output_manager = OutputManager(cfg, self.infer_cfg, self.visualizer)
        
        # Metrics
        self.metrics = {
            "total_records": 0,
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "total_inference_time_ms": 0,
        }
    
    def _setup_device(self) -> torch.device:
        """Setup GPU device."""
        gpu_cfg = self.cfg.seg_inference.get("gpu", {})
        max_gpus = gpu_cfg.get("max_gpus", 1)
        exclude_ids = gpu_cfg.get("exclude_ids", [0])
        
        try:
            device_ids = select_available_gpus(max_gpus, exclude_ids, verbose=True)
            import os
            os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(map(str, device_ids))
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            log.info(f"Using device: {device}")
            return device
        except Exception as e:
            log.warning(f"GPU setup failed: {e}, falling back to CPU")
            return torch.device("cpu")
    
    def _load_model(self) -> SegModel:
        """Load segmentation model from checkpoint."""
        model_cfg = self.cfg.seg_inference.model
        
        log.info(f"Loading model from: {model_cfg.ckpt_path}")
        
        model = SegModel(
            arch=model_cfg.arch,
            encoder_name=model_cfg.encoder_name,
            in_channels=model_cfg.in_channels,
            num_classes=model_cfg.num_classes,
            encoder_weights=model_cfg.get("encoder_weights", "imagenet"),
            mean=model_cfg.normalization.mean,
            std=model_cfg.normalization.std,
        )
        
        model.load_checkpoint(
            self.infer_cfg.model_ckpt,
            device=self.device,
            strict=model_cfg.get("strict_load", True),
        )
        
        return model
    
    def _process_record(
        self,
        record: Dict,
        manifest: pd.DataFrame,
    ) -> Optional[Dict]:
        """Process a single record through inference pipeline."""
        try:
            # Determine record ID
            record_id = self._get_record_id(record)
            
            # Check for duplicates in full_image mode
            if self.infer_cfg.image_mode == "full_image":
                if record_id in manifest['record_id'].unique():
                    log.info(f"Skipping {record_id} - already processed")
                    self.metrics["skipped"] += 1
                    return None
            
            # Load image
            img = self.image_processor.load_image(record)
            if img is None:
                log.warning(f"Could not load image for {record_id}")
                self.metrics["skipped"] += 1
                return None
            
            log.info(f"Loaded image shape: {img.shape} for {record_id}")
            
            # Handle custom bbox mode
            if self.infer_cfg.custom_enabled and self.infer_cfg.custom_mode == "segment_bboxes":
                return self._process_bboxes_mode(record, img, manifest)
            
            # Standard inference
            pred_mask, inference_time_ms = self.image_processor.run_inference(img)
            
            # Post-process
            log.info("Post-processing mask...")
            pred_mask, edge_occupancy = self.post_processor.process(
                pred_mask,
                class_id=record.get("category_class_id", 27)
            )
            
            log.info(f"Edge occupancy: {edge_occupancy:.3f}")
            
            # Check edge occupancy threshold
            if self._should_skip_by_edge(edge_occupancy, record_id):
                return None
            
            # Save outputs
            output_paths = self.output_manager.save_outputs(
                record_id, record, img, pred_mask, edge_occupancy
            )
            
            # Update metrics
            self.metrics["processed"] += 1
            self.metrics["total_inference_time_ms"] += inference_time_ms
            
            # Build manifest entry
            return self._build_manifest_entry(
                record_id, record, img, pred_mask,
                edge_occupancy, inference_time_ms, output_paths
            )
        
        except Exception as e:
            log.error(f"Failed to process record {record.get('id', 'unknown')}: {e}")
            self.metrics["failed"] += 1
            return None
    
    def _process_bboxes_mode(
        self,
        record: Dict,
        img: np.ndarray,
        manifest: pd.DataFrame,
    ) -> Optional[Dict]:
        """Process record in bbox segmentation mode."""
        record_id = record.get("image_id", record.get("id", "unknown"))
        log.info(f"Running bbox segmentation for {record_id}...")
        
        bboxes = record.get("xywh_detections", [])
        if not bboxes:
            log.warning(f"No bounding boxes found for {record_id}")
            self.metrics["skipped"] += 1
            return None
        
        # Process each bbox
        bbox_results = self.image_processor.process_bboxes(img, bboxes)
        
        for cutout_id, cutout_img, pred_mask, inference_time_ms in bbox_results:
            # Post-process
            pred_mask, edge_occupancy = self.post_processor.process(
                pred_mask,
                class_id=record.get("category_class_id", 27)
            )
            
            if self._should_skip_by_edge(edge_occupancy, cutout_id):
                continue
            
            # Save outputs for this bbox
            output_paths = self.output_manager.save_outputs(
                cutout_id, record, cutout_img, pred_mask, edge_occupancy
            )
            
            self.metrics["processed"] += 1
            self.metrics["total_inference_time_ms"] += inference_time_ms
        
        # Return manifest entry for parent record
        return self._build_manifest_entry(
            record_id, record, img, None, 0.0, 0, {}
        )
    
    def _get_record_id(self, record: Dict) -> str:
        """Extract appropriate record ID based on mode."""
        if self.infer_cfg.image_mode == "full_image":
            return record.get("image_id", record.get("id", "unknown"))
        else:
            return record.get("cutout_id", record.get("id", "unknown"))
    
    def _should_skip_by_edge(self, edge_occupancy: float, record_id: str) -> bool:
        """Check if record should be skipped based on edge occupancy."""
        threshold = self.infer_cfg.edge_threshold
        if threshold is not None and edge_occupancy > threshold:
            log.info(f"Skipping {record_id} - edge occupancy {edge_occupancy:.3f} > {threshold}")
            self.metrics["skipped"] += 1
            return True
        return False
    
    def _build_manifest_entry(
        self,
        record_id: str,
        record: Dict,
        img: np.ndarray,
        pred_mask: Optional[np.ndarray],
        edge_occupancy: float,
        inference_time_ms: int,
        output_paths: Dict[str, Optional[str]],
    ) -> Dict:
        """Build manifest entry for a processed record."""
        common_name = record.get("category_common_name", record.get("common_name", "unknown"))
        common_name = common_name.lower().replace(" ", "_")
        area_bin = record.get("area_bin", "")
        
        return {
            "record_id": record_id,
            "image_mode": self.infer_cfg.image_mode,
            "common_name": common_name,
            "area_bin": area_bin,
            "image_path": output_paths.get("image_path"),
            "mask_path": output_paths.get("mask_path"),
            "colorized_mask_path": output_paths.get("colorized_mask_path"),
            "cutout_path": output_paths.get("cutout_path"),
            "viz_path": output_paths.get("viz_path"),
            "inference_time_ms": inference_time_ms,
            "edge_occupancy": float(edge_occupancy),
            "image_shape": list(img.shape) if img is not None else None,
            "mask_shape": list(pred_mask.shape) if pred_mask is not None else None,
        }
    
    def run(self) -> None:
        """Run the segmentation inference pipeline."""
        log.info("=" * 80)
        log.info("Starting Segmentation Inference Pipeline")
        log.info("=" * 80)
        
        # Load records
        records = self.record_loader.load_records()
        
        if not records:
            log.warning("No records to process")
            return
        
        self.metrics["total_records"] = len(records)
        log.info(f"Processing {len(records)} records...")
        
        # Initialize manifest CSV
        manifest_path = Path(self.paths.manifest_path).with_suffix('.csv')
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        
        df = pd.DataFrame(columns=[
            'record_id', 'common_name', 'edge_occupancy',
            'inference_time_ms', 'mask_path', 'image_path', 'plot_path',
        ])
        df.to_csv(manifest_path, index=False)
        
        # Process records with progress tracking
        metrics_path = Path(self.paths.metrics_path)
        metrics_update_interval = 10
        
        for idx, record in enumerate(tqdm(records, desc="Inference"), 1):
            result = self._process_record(record, df)
            
            if result:
                # Append to CSV
                new_row = pd.DataFrame([result])
                new_row.to_csv(manifest_path, mode='a', header=False, index=False)
                df = pd.concat([df, new_row], ignore_index=True)
            
            # Periodic metrics update
            if idx % metrics_update_interval == 0:
                self._update_metrics(metrics_path)
        
        # Final metrics update
        self._update_metrics(metrics_path)
        
        # Print summary
        self._print_summary(manifest_path, metrics_path)
    
    def _update_metrics(self, metrics_path: Path) -> None:
        """Update and save metrics."""
        if self.metrics["processed"] > 0:
            self.metrics["avg_inference_time_ms"] = (
                self.metrics["total_inference_time_ms"] / self.metrics["processed"]
            )
        else:
            self.metrics["avg_inference_time_ms"] = 0
        
        with open(metrics_path, "w") as f:
            json.dump(self.metrics, f, indent=2)
    
    def _print_summary(self, manifest_path: Path, metrics_path: Path) -> None:
        """Print pipeline summary."""
        log.info("=" * 80)
        log.info("Segmentation Inference Complete")
        log.info("=" * 80)
        log.info(f"Total records: {self.metrics['total_records']}")
        log.info(f"Processed: {self.metrics['processed']}")
        log.info(f"Skipped: {self.metrics['skipped']}")
        log.info(f"Failed: {self.metrics['failed']}")
        log.info(f"Avg inference time: {self.metrics['avg_inference_time_ms']:.1f}ms")
        log.info(f"Results saved to: {self.paths.run_root}")
        log.info(f"Manifest: {manifest_path}")
        log.info(f"Metrics: {metrics_path}")
        log.info("=" * 80)