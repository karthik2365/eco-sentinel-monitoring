"""
Google Earth Engine Service

Provides integration with Google Earth Engine for satellite imagery acquisition and processing.
"""

from datetime import date, timedelta
import logging
import os
import requests
from typing import Any, Dict, Optional, Tuple

import ee
from utils.geometry import polygon

from config import Config

logger = logging.getLogger(__name__)


class GEEService:
    """
    Singleton service for Google Earth Engine operations.
    """
    
    _instance: Optional['GEEService'] = None
    _initialized: bool = False
    
    # Cloud masking SCL values
    CLEAR_VEGETATION = 4
    CLEAR_SOIL = 5
    CLEAR_WATER = 6
    CLEAR_SNOW = 11
    
    def __new__(cls) -> 'GEEService':
        if cls._instance is None:
            cls._instance = super(GEEService, cls).__new__(cls)
        return cls._instance
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def initialize(self, service_account_file: Optional[str] = None, project_id: Optional[str] = None) -> bool:
        if self._initialized:
            return True

        key_file = service_account_file or Config.GEE_SERVICE_ACCOUNT
        proj_id = project_id or Config.GEE_PROJECT_ID or "agentathon"

        try:
            # Try to initialize with service account credentials
            if key_file and os.path.exists(key_file):
                logger.info(f"Initializing GEE with service account: {key_file}")
                credentials = ee.ServiceAccountCredentials(None, key_file)
                ee.Initialize(credentials=credentials, project=proj_id)
            else:
                # Fallback to default credentials (for Cloud Run with attached service account)
                logger.info("Service key not found, trying default credentials...")
                ee.Initialize(project=proj_id)
            
            self._initialized = True
            logger.info("Google Earth Engine initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize GEE: {e}")
            return False

    MIN_COVERAGE = 99.5

    @staticmethod
    def _valid_pixels(image):
        # Count observed pixels, not the fractional alpha introduced by clipping
        # polygon edges. Use the same bands and mask for coverage and comparison.
        return (image.select(["B2", "B3", "B4", "B8"]).mask()
                .reduce(ee.Reducer.min()).unmask(0, sameFootprint=False).gt(0))

    def _composite(self, geometry, start_date, end_date):
        # Judge each pixel, not the cloud percentage of an entire 100 km tile.
        scenes = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                  .filterBounds(geometry).filterDate(start_date, end_date))
        scores = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
        clear = scenes.linkCollection(scores, ["cs_cdf"]).map(
            lambda image: image.updateMask(image.select("cs_cdf").gte(0.60))
            .select(["B2", "B3", "B4", "B8"]))
        count = scenes.size().getInfo()
        if not count:
            return None, 0, 0.0
        composite = clear.median()
        # Include missing tile footprints as zero; exclude only land outside the AOI.
        valid = (self._valid_pixels(composite)
                 .rename("valid"))
        coverage = valid.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geometry, scale=120,
            bestEffort=True, maxPixels=1000000, tileScale=4).get("valid").getInfo()
        return composite, count, 100.0 * (coverage or 0.0)

    def get_quality_imagery(self, aoi_geometry, start_date, end_date,
                            layer_type="rgb", adaptive=True):
        """Return a real clear-pixel composite with measured, approximate coverage.

        Widen only backwards in time and report the effective dates. Never fill
        gaps with synthetic pixels or unmasked cloudy observations.
        """
        if not self._initialized:
            raise RuntimeError("GEE service not initialized.")
        geometry = self._create_geometry(aoi_geometry)
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
        days = (end - start).days
        windows = [days] + ([n for n in (60, 120, 180) if n > days] if adaptive else [])
        sentinel, image_count, coverage = None, 0, 0.0
        effective_start = start_date
        for window in windows:
            effective_start = (end - timedelta(days=window)).isoformat()
            sentinel, image_count, coverage = self._composite(geometry, effective_start, end_date)
            logger.info("Satellite composite %s to %s: %s scenes, %.2f%% coverage",
                        effective_start, end_date, image_count, coverage)
            if coverage >= self.MIN_COVERAGE:
                break
        if sentinel is None:
            raise ValueError("No satellite scenes found. Choose another date or area.")
        image, vis_params = self._get_visualization(sentinel, layer_type)
        url = image.clip(geometry).getThumbURL({"region": geometry, "dimensions": 1024,
                                "crs": "EPSG:4326", "format": "png", **vis_params})
        return {
            "imageUrl": url, "imageCount": image_count,
            "coveragePercent": round(coverage, 2),
            "readyForAnalysis": coverage >= self.MIN_COVERAGE,
            "startDate": effective_start, "endDate": end_date,
            "requestedStartDate": start_date,
            "expandedWindow": effective_start != start_date,
            "layerType": layer_type,
            "source": "Sentinel-2 / Cloud Score+",
            "sourceResolutionMeters": 10,
            "qualityVersion": 2,
        }, sentinel

    def compare_composites(self, aoi_geometry, historical, current):
        """Summarize NDVI only where BOTH composites have valid pixels."""
        geometry = self._create_geometry(aoi_geometry)
        before = historical.normalizedDifference(["B8", "B4"]).rename("before")
        after = current.normalizedDifference(["B8", "B4"]).rename("after")
        common = (self._valid_pixels(historical).And(self._valid_pixels(current))
                  .And(before.mask().unmask(0, sameFootprint=False).gt(0))
                  .And(after.mask().unmask(0, sameFootprint=False).gt(0)))
        coverage = common.unmask(0, sameFootprint=False).rename("common").reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geometry, scale=120,
            bestEffort=True, maxPixels=1000000, tileScale=4).get("common").getInfo()
        bands = (before.addBands(after).addBands(after.subtract(before).rename("change"))
                 .updateMask(common))
        stats = bands.reduceRegion(reducer=ee.Reducer.mean(), geometry=geometry, scale=120,
                                   bestEffort=True, maxPixels=1000000, tileScale=4).getInfo()
        return {"commonCoveragePercent": round(100 * (coverage or 0), 2),
                "historicalNdvi": stats.get("before"), "currentNdvi": stats.get("after"),
                "ndviChange": stats.get("change"), "samplingScaleMeters": 120, "qualityVersion": 2}

    def get_sentinel2_imagery(self, aoi_geometry, start_date, end_date,
                              cloud_threshold=Config.DEFAULT_CLOUD_THRESHOLD,
                              layer_type="rgb"):
        # Analyses use exactly the reviewed date range, including its baseline.
        result, image = self.get_quality_imagery(
            aoi_geometry, start_date, end_date, layer_type, adaptive=False)
        if not result["readyForAnalysis"]:
            raise ValueError(
                f"Only {result['coveragePercent']}% usable satellite coverage for "
                f"{start_date} to {end_date}. Choose a clearer period or smaller area.")
        return result["imageUrl"], image, result["imageCount"]

    def _create_geometry(self, aoi_geometry: Dict[str, Any]) -> ee.Geometry:
        """Create geometry handling both Rectangle and Polygon formats robustly."""
        return ee.Geometry(polygon(aoi_geometry))

    def _get_visualization(self, image: ee.Image, layer_type: str) -> Tuple[ee.Image, Dict[str, Any]]:
        if layer_type == "ndvi":
            ndvi_image = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
            vis_params = {
                "min": -0.2, "max": 0.8,
                "palette": ["#d73027", "#fc8d59", "#fee08b", "#d9ef8b", "#91cf60", "#1a9850"]
            }
            return ndvi_image, vis_params
        else:
            rgb_image = image.select(["B4", "B3", "B2"])
            vis_params = {"min": 0, "max": 3000}
            return rgb_image, vis_params

    def download_image(self, url: str, output_path: str) -> bool:
        """Download image from URL to local path."""
        try:
           response = requests.get(url, stream=True, timeout=60)
           if response.status_code == 200:
               os.makedirs(os.path.dirname(output_path), exist_ok=True)
               with open(output_path, 'wb') as f:
                   for chunk in response.iter_content(1024):
                       f.write(chunk)
               return True
           return False
        except Exception as e:
            logger.error(f"Failed to download image: {e}")
            return False

# Singleton instance
gee_service = GEEService()
