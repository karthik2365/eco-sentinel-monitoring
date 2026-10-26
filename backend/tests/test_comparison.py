import unittest
from datetime import date
from unittest.mock import patch
from tests import test_app as app_fixture
GEOMETRY = app_fixture.GEOMETRY
from services.comparison_service import comparison_request
from services.gee_service import gee_service
from services.gemini_service import gemini_service, AIServiceError
from services.orchestrator import Orchestrator
from models.analysis_incident import AgentLog, Analysis, Report
from extensions import db

class ComparisonDates(unittest.TestCase):
    def test_latest_freezes_today_with_inclusive_dates(self):
        result=comparison_request({'comparison_mode':'latest','historical_date':'2026-09-25'}, date(2026,10,25))
        self.assertEqual(result['historical']['startDate'],'2026-08-27')
        self.assertEqual(result['historical']['endDate'],'2026-09-26')
        self.assertEqual(result['current']['endDate'],'2026-10-26')
        self.assertEqual(result['windowDays'],30)

    def test_two_nearby_dates_have_disjoint_equal_windows(self):
        result=comparison_request({'comparison_mode':'custom','historical_date':'2026-09-25','comparison_date':'2026-10-01'},date(2026,10,25))
        self.assertEqual(result['windowDays'],6)
        self.assertEqual(result['historical']['endDate'],result['current']['startDate'])

    def test_invalid_dates_are_rejected(self):
        for old,new in [('2026-10-25','2026-10-25'),('2026-10-26','2026-10-25'),('2026-09-25','2099-01-01'),('bad','2026-10-25')]:
            with self.assertRaises(ValueError):
                comparison_request({'comparison_mode':'custom','historical_date':old,'comparison_date':new},date(2026,10,25))

# Reuse the isolated app fixture without inheriting its full test suite.
class ComparisonFlow(unittest.TestCase):
    setUp=app_fixture.AppTests.setUp
    tearDown=app_fixture.AppTests.tearDown
    job=app_fixture.AppTests.job

    def request_job(self):
        with patch('routes.analysis.orchestrator.start_analysis') as start:
            res=self.client.post('/api/analysis/start',headers=self.headers,json={
                'aoi_id':self.aoi_id,'comparison_mode':'custom',
                'historical_date':'2026-08-01','comparison_date':'2026-09-25'})
            self.assertEqual(res.status_code,201)
            start.assert_called_once()
        job=db.session.get(Analysis,res.json['analysis_id'])
        self.assertEqual(job.logs.filter_by(action='comparison_request').one().details['mode'],'custom')
        return job.id

    def run_comparison(self, coverage=100, missing=False):
        ident=self.request_job()
        image={'imageUrl':'https://example.test/image.png','imageCount':10,
               'coveragePercent':coverage,'readyForAnalysis':coverage>=99.5}
        metrics={'historicalNdvi':0.3,'currentNdvi':0.4,'ndviChange':0.1,'commonCoveragePercent':coverage}
        runner=Orchestrator();runner._app=self.app
        results=[ValueError('No satellite scenes'),(image,object())] if missing else [(image,object()),(image,object())]
        with patch.object(gee_service,'get_quality_imagery',side_effect=results) as fetch, \
             patch.object(gee_service,'download_image',return_value=True), \
             patch.object(gee_service,'compare_composites',return_value=metrics) as measured, \
             patch.object(gemini_service,'check_connection',side_effect=AIServiceError('TEST missing key')) as provider:
            runner._run_pipeline(ident,GEOMETRY,'2026-08-01','2026-09-25')
        db.session.expire_all()
        response=self.client.get(f'/api/analysis/{ident}',headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['status'],'comparison_ready')
        self.assertEqual(Report.query.count(),0)
        self.assertEqual(fetch.call_args_list[0].args[1:3],('2026-07-03','2026-08-02'))
        self.assertEqual(fetch.call_args_list[1].args[1:3],('2026-08-27','2026-09-26'))
        return response.json['comparison'],provider,measured

    def test_invalid_key_keeps_both_images_and_numeric_comparison(self):
        result,provider,measured=self.run_comparison()
        self.assertTrue(result['historical']['imageUrl'].startswith('/static/'))
        self.assertTrue(result['current']['imageUrl'].startswith('/static/'))
        self.assertEqual(result['metrics']['ndviChange'],0.1)
        self.assertEqual(result['aiStatus'],'unavailable')
        provider.assert_called_once();measured.assert_called_once()

    def test_partial_coverage_does_not_block_visual_comparison(self):
        result,provider,measured=self.run_comparison(coverage=80)
        self.assertEqual(result['historical']['coveragePercent'],80)
        self.assertEqual(result['aiStatus'],'limited_coverage')
        provider.assert_not_called();measured.assert_called_once()

    def test_missing_period_retains_other_image(self):
        result,provider,measured=self.run_comparison(missing=True)
        self.assertEqual(result['historical']['state'],'unavailable')
        self.assertEqual(result['current']['state'],'ready')
        provider.assert_not_called();measured.assert_not_called()

    def test_comparison_metadata_is_owner_scoped(self):
        ident=self.request_job()
        self.assertEqual(self.client.get(f'/api/analysis/{ident}').status_code,401)
        other=self.client.post('/api/auth/register',json={'username':'comparison-other','email':'compare@example.test','password':'test-only'})
        response=self.client.get(f'/api/analysis/{ident}',headers={'Authorization':'Bearer '+other.json['token']})
        self.assertEqual(response.status_code,404)

if __name__=='__main__':unittest.main()
