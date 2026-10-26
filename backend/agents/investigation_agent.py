"""Attach explicit evidence limits; no invented history or legal determinations."""
from .base_agent import BaseAgent

class InvestigationAgent(BaseAgent):
    def __init__(self):
        super().__init__('investigation_01', 'Strategic Investigation Unit')

    def execute(self, analysis_id, incidents):
        self.update_status('working')
        for incident in incidents:
            incident['context'] = 'Confirm this visual finding with a field inspection and local records. No permits or regulatory databases were queried.'
            incident['history'] = 'Historical evidence is limited to the baseline image. Seasonal differences can resemble environmental change.'
        self.log_action(analysis_id, 'evidence_review', reasoning='Recorded imagery limitations and recommended field verification; no unsupported legal conclusions.')
        self.update_status('completed')
        return {'status': 'success', 'incidents': incidents}
