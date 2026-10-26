"""
Imagery Acquisition Agent

Responsible for acquiring satellite imagery from Google Earth Engine.
"""

import logging
import os
from typing import Any, Dict

from .base_agent import BaseAgent
from services.gee_service import gee_service

logger = logging.getLogger(__name__)


class ImageryAgent(BaseAgent):
    """
    Agent for acquiring satellite imagery.
    
    Connects to Google Earth Engine to fetch Sentinel-2 imagery
    for the specified area and date range.
    """
    
    def __init__(self):
        super().__init__(agent_id="imagery_01", name="Imagery Acquisition Analyst")

    def execute(
        self,
        analysis_id: int,
        aoi_geometry: Dict[str, Any],
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Acquire satellite imagery for the specified area and date range.
        Downloads images synchronously to ensure they're available for the report.
        """
        self.update_status("working")
        self.log_action(analysis_id, "start_acquisition", reasoning=f"Acquiring imagery for {start_date} to {end_date}")
        
        try:
            # 1. Acquire Current Image
            self.log_action(analysis_id, "querying_current", reasoning="Querying Sentinel-2 for current imagery")
            current_url, _, current_count = gee_service.get_sentinel2_imagery(
                aoi_geometry, start_date, end_date
            )
            
            # 2. Acquire Baseline Image (1 year prior)
            from datetime import datetime, timedelta
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            base_start = (start_dt - timedelta(days=365)).strftime("%Y-%m-%d")
            base_end = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")
            
            self.log_action(analysis_id, "querying_baseline", reasoning=f"Querying baseline imagery ({base_start})")
            baseline_url, _, baseline_count = gee_service.get_sentinel2_imagery(
                aoi_geometry, base_start, base_end
            )

            if not current_url or not baseline_url:
                self.log_action(analysis_id, "acquisition_failed", status="error", reasoning="No current or baseline imagery found")
                self.update_status("failed")
                return {"status": "failed", "error": "No current or baseline imagery found. Widen the date range or choose another area."}

            # Prepare local paths
            local_dir = os.path.join("static", "images", "analysis")
            os.makedirs(local_dir, exist_ok=True)
            
            cur_path = os.path.abspath(os.path.join(local_dir, f"local_analysis_{analysis_id}_current.png"))
            base_path = os.path.abspath(os.path.join(local_dir, f"local_analysis_{analysis_id}_baseline.png"))

            # Download images SYNCHRONOUSLY (we're already in a background thread)
            self.log_action(analysis_id, "downloading", reasoning="Downloading images for report")
            
            cur_downloaded = gee_service.download_image(current_url, cur_path)
            base_downloaded = gee_service.download_image(baseline_url, base_path) if baseline_url else False
            
            if not cur_downloaded or not base_downloaded:
                raise RuntimeError('Could not download both satellite images. Please retry.')
            self.update_status("completed")
            
            return {
                "status": "success",
                "current_url": current_url,
                "baseline_url": baseline_url,
                "current_path": cur_path if cur_downloaded else None,
                "baseline_path": base_path if base_downloaded else None,
                "image_count": current_count + (baseline_count or 0)
            }

        except Exception as e:
            error_msg = f"Imagery acquisition error: {str(e)}"
            logger.error(error_msg)
            self.log_action(analysis_id, "error", status="error", reasoning=error_msg)
            self.update_status("failed")
            return {"status": "error", "error": str(e)}
