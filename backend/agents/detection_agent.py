"""Compare dated baseline and current imagery, allowing no-change results."""
from .base_agent import BaseAgent
from services.gemini_service import gemini_service, parse_json
from utils.geometry import centroid

class DetectionAgent(BaseAgent):
    def __init__(self):
        super().__init__('detection_01', 'Change Detection Specialist')

    def execute(self, analysis_id, current_image_url, aoi_geometry=None,
                baseline_image_url=None, baseline_date=None):
        self.update_status('working')
        self.log_action(analysis_id, 'comparing_images', reasoning='Comparing baseline (first image) and current (second image).')
        try:
            if not baseline_image_url:
                raise ValueError('Baseline imagery is required to assess changes. Choose another period.')
            prompt = """Compare these two satellite composites. The FIRST is the baseline; the SECOND is current.
Describe only changes visibly supported by both images. Account for seasonality, clouds, illumination, and resolution.
Do not infer illegality, pollution chemistry, exact coordinates, measured area, or historical facts from appearance alone.
Return ONLY JSON: {"changes": [{"description": "visual evidence and uncertainty", "category": "Land Use Change", "severity": "low", "confidence": 0.5}]}.
Use an empty changes array if no credible changes are visible. Maximum 5 changes. Categories: Deforestation,
Construction, Water Surface Change, Land Use Change, Agricultural Expansion, Uncertain Change.
Severity: low, medium, high, critical. Confidence is an uncalibrated visual estimate from 0 to 1."""
            result = parse_json(gemini_service.analyze_images([baseline_image_url, current_image_url], prompt))
            changes = result.get('changes') if isinstance(result, dict) else None
            if not isinstance(changes, list) or len(changes) > 5:
                raise ValueError('AI returned an invalid changes list. Please retry.')
            for index, item in enumerate(changes):
                if not isinstance(item, dict) or not isinstance(item.get('description'), str) or not item['description'].strip():
                    raise ValueError('AI returned a change without supporting evidence.')
                item.update(id=f'change_{index+1}', location=centroid(aoi_geometry), area_affected=None)
            self.log_action(analysis_id, 'detection_complete', reasoning=f'{len(changes)} potential changes supported by image comparison.')
            self.update_status('completed')
            return {'status': 'success', 'detected_regions': changes}
        except Exception as exc:
            self.update_status('failed')
            self.log_action(analysis_id, 'error', status='error', reasoning=str(exc))
            return {'status': 'error', 'error': str(exc)}
