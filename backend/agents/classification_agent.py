"""Normalize the paired-image findings without inventing fallback incidents."""
import math
from .base_agent import BaseAgent

class ClassificationAgent(BaseAgent):
    CATEGORIES = {'Deforestation', 'Construction', 'Water Surface Change', 'Land Use Change', 'Agricultural Expansion', 'Uncertain Change'}
    def __init__(self):
        super().__init__('classification_01', 'Environmental Classification Officer')

    def execute(self, analysis_id, image_url, detected_regions):
        self.update_status('working')
        incidents = []
        try:
            for region in detected_regions:
                confidence = float(region.get('confidence', 0))
                if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                    raise ValueError('AI returned an invalid confidence estimate.')
                category = region.get('category')
                severity = str(region.get('severity', 'low')).lower()
                if severity not in ('low', 'medium', 'high', 'critical'):
                    raise ValueError('AI returned an invalid severity level.')
                incidents.append({'category': category if category in self.CATEGORIES else 'Uncertain Change',
                                  'severity': severity, 'confidence': confidence,
                                  'description': region['description'], 'location': region.get('location'),
                                  'affected_area': None})
            self.log_action(analysis_id, 'classification_complete', reasoning=f'Validated {len(incidents)} image-based findings; locations refer to the selected area center.')
            self.update_status('completed')
            return {'status': 'success', 'incidents': incidents}
        except Exception as exc:
            self.update_status('failed')
            return {'status': 'error', 'error': str(exc)}
