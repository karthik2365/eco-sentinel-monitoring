"""Integration tests use isolated SQLite and explicit AI/imagery fixtures, never live credentials."""
import json
import logging
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch
from config import TestingConfig, Config
from app import create_app
from extensions import db, socketio
from models.user_aoi import AOI, User
from models.analysis_incident import Analysis, Incident, Report
from services.orchestrator import Orchestrator
from services.scheduler import Monitor, run_due
from services.gemini_service import gemini_service, AIServiceError
from agents.detection_agent import DetectionAgent
from utils.geometry import polygon, centroid

GEOMETRY = {'type':'rectangle','coordinates':[[78.43,17.37],[78.47,17.41]]}

class AppTests(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        with patch('app._init_services'):
            self.app = create_app(TestingConfig)
        self.context = self.app.app_context(); self.context.push()
        self.client = self.app.test_client()
        response = self.client.post('/api/auth/login', json={'username':'demo','password':'demo123'})
        self.assertEqual(response.status_code, 200)
        self.token = response.json['token']; self.headers = {'Authorization':'Bearer '+self.token}
        self.user_id = response.json['user']['id']
        self.aoi = AOI(user_id=self.user_id, name='TEST FIXTURE AREA', geometry=GEOMETRY)
        db.session.add(self.aoi); db.session.commit()
        self.aoi_id = self.aoi.id
        self.temp = tempfile.TemporaryDirectory()
        self.upload_patch = patch.object(Config, 'UPLOAD_FOLDER', self.temp.name); self.upload_patch.start()

    def tearDown(self):
        db.session.remove(); db.drop_all(); self.context.pop()
        self.upload_patch.stop(); self.temp.cleanup()

    def job(self):
        job = Analysis(aoi_id=self.aoi_id, status='pending')
        db.session.add(job); db.session.commit(); return job

    def test_authorization_and_ownership(self):
        job = self.job()
        self.assertEqual(self.client.get(f'/api/analysis/{job.id}').status_code,401)
        other = self.client.post('/api/auth/register',json={'username':'other','email':'other@example.test','password':'test-only-password'})
        h = {'Authorization':'Bearer '+other.json['token']}
        self.assertEqual(self.client.get(f'/api/analysis/{job.id}',headers=h).status_code,404)
        self.assertEqual(self.client.delete(f'/api/analysis/{job.id}',headers=h).status_code,404)
        self.assertEqual(self.client.get('/api/analysis/list',headers=h).json,[])
        self.assertEqual(self.client.get('/api/auth/admin/users').status_code,404)

    def test_invalid_inputs_do_not_create_jobs(self):
        for start,end in [('2025-02-01','2025-01-01'),('invalid','2025-01-01'),('2025-01-01','2099-01-01')]:
            res=self.client.post('/api/analysis/start',headers=self.headers,json={'aoi_id':self.aoi_id,'start_date':start,'end_date':end})
            self.assertEqual(res.status_code,400)
        self.assertEqual(Analysis.query.count(),0)
        self.assertEqual(self.client.post('/api/map/aoi',headers=self.headers,json={'geometry':{'type':'polygon','coordinates':[[1,1],[1,1],[1,1]]}}).status_code,400)

    def test_preview_returns_quality_and_effective_dates(self):
        from services.gee_service import gee_service
        result = {'imageUrl':'https://example.test/image.png','imageCount':20,
                  'coveragePercent':99.9,'readyForAnalysis':True,
                  'startDate':'2026-07-26','endDate':'2026-09-24','expandedWindow':True}
        with patch.object(gee_service,'_initialized',True), patch.object(
                gee_service,'get_quality_imagery',return_value=(result,None)):
            response=self.client.post('/api/map/preview',headers=self.headers,json={
                'geometry':GEOMETRY,'startDate':'2026-08-25','endDate':'2026-09-24'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json,dict(success=True,**result))

    def test_geometry_normalization(self):
        result=polygon(GEOMETRY)
        self.assertEqual(result['type'],'Polygon')
        self.assertEqual(result,polygon(result))
        center=centroid(result)
        self.assertAlmostEqual(center['lat'],17.39)
        self.assertAlmostEqual(center['lon'],78.45)
        with self.assertRaises(ValueError): polygon({'type':'rectangle','coordinates':[[0,0],[0,0]]})

    def test_no_change_is_zero_incidents(self):
        job=self.job(); agent=DetectionAgent();agent.analysis_id=job.id
        with patch.object(gemini_service,'analyze_images',return_value='{"changes":[]}') as call:
            result=agent.execute(job.id,'after.png',GEOMETRY,'before.png')
        self.assertEqual(result['detected_regions'],[])
        self.assertEqual(call.call_args.args[0],['before.png','after.png'])

    def test_invalid_model_output_is_failure(self):
        job=self.job();agent=DetectionAgent();agent.analysis_id=job.id
        with patch.object(gemini_service,'analyze_images',return_value='not JSON'):
            result=agent.execute(job.id,'after.png',GEOMETRY,'before.png')
        self.assertEqual(result['status'],'error')
        self.assertEqual(Incident.query.count(),0)

    def test_provider_failure_does_not_create_report(self):
        job=self.job(); runner=Orchestrator();runner._app=self.app
        with patch.object(gemini_service,'check_connection',side_effect=AIServiceError('TEST: invalid key')):
            runner._run_pipeline(job.id,GEOMETRY,'2025-01-01','2025-02-01')
        db.session.expire_all()
        self.assertEqual(db.session.get(Analysis,job.id).status,'failed')
        self.assertEqual(Incident.query.count(),0)
        self.assertEqual(Report.query.count(),0)
        result=self.client.get(f'/api/analysis/{job.id}',headers=self.headers).json
        self.assertIn('invalid key',result['error'])

    def test_complete_pipeline_creates_readable_pdf(self):
        job=self.job();runner=Orchestrator();runner._app=self.app
        # Reuse repository sample imagery as a fixture, never label it as a current observation.
        image=Path(__file__).parent/'fixtures/satellite.png'
        imagery={'status':'success','current_url':'fixture','baseline_path':str(image),'current_path':str(image)}
        findings={'changes':[{'description':'TEST FIXTURE: visual change <script>not executable</script>', 'category':'Land Use Change','severity':'low','confidence':0.5}]}
        with patch.object(gemini_service,'check_connection',return_value=True), patch.object(runner.imagery_agent,'execute',return_value=imagery), patch.object(gemini_service,'analyze_images',return_value=json.dumps(findings)), patch.object(gemini_service,'generate_text',return_value='TEST FIXTURE: This is a deterministic integration test, not environmental evidence.'):
            runner._run_pipeline(job.id,GEOMETRY,'2025-01-01','2025-02-01')
        db.session.expire_all()
        self.assertEqual(db.session.get(Analysis,job.id).status,'completed')
        self.assertEqual(Incident.query.count(),1)
        report=Report.query.one();self.assertNotIn('<script>',report.content_html)
        from pypdf import PdfReader
        pdf=Path(self.temp.name)/f'local_report_{job.id}.pdf'
        self.assertTrue(pdf.exists())
        text='\n'.join(page.extract_text() for page in PdfReader(pdf).pages)
        self.assertIn('TEST FIXTURE',text)
        self.assertIn('Executive Summary',text)
        self.assertEqual(self.client.get(f'/api/analysis/reports/{job.id}',headers=self.headers).status_code,200)

    def test_schedule_is_persistent_and_pauseable(self):
        with patch('services.orchestrator.orchestrator.start_analysis') as start:
            res=self.client.post('/api/analysis/start',headers=self.headers,json={'aoi_id':self.aoi_id,'start_date':'2025-01-01','end_date':'2025-02-01','analysis_type':'watchdog','frequency':'weekly','threshold':'significant'})
            self.assertEqual(res.status_code,201);start.assert_called_once()
        monitor=Monitor.query.one()
        self.assertEqual(monitor.frequency,'weekly')
        self.assertGreater(monitor.next_run,datetime.utcnow()+timedelta(days=6))
        res=self.client.patch(f'/api/monitors/{monitor.id}',headers=self.headers,json={'active':False})
        self.assertFalse(res.json['active'])
        self.assertEqual(self.client.get('/api/monitors',headers=self.headers).json['monitors'][0]['threshold'],'significant')

    def test_scheduler_catches_up_once_and_skips_paused(self):
        monitor=Monitor(aoi_id=self.aoi_id,frequency='daily',threshold='any',active=True,next_run=datetime.utcnow()-timedelta(days=3))
        db.session.add(monitor);db.session.commit()
        with patch('services.orchestrator.orchestrator.start_analysis') as start:
            run_due(self.app);run_due(self.app)
            start.assert_called_once()
        self.assertEqual(Analysis.query.count(),1)
        monitor.active=False;monitor.next_run=datetime.utcnow()-timedelta(days=1);db.session.commit()
        with patch('services.orchestrator.orchestrator.start_analysis') as start:
            run_due(self.app);start.assert_not_called()

    def test_socket_authentication_and_scoping(self):
        guest=socketio.test_client(self.app)
        self.assertFalse(guest.is_connected())
        client=socketio.test_client(self.app,auth={'token':self.token})
        self.assertTrue(client.is_connected())
        other=self.client.post('/api/auth/register',json={'username':'socketother','email':'socket@example.test','password':'test-only'})
        outsider=socketio.test_client(self.app,auth={'token':other.json['token']})
        from services.events import emit_analysis
        job=self.job();emit_analysis('analysis_progress',{'analysis_id':job.id,'progress':25})
        self.assertTrue(client.get_received())
        self.assertEqual(outsider.get_received(),[])
        client.disconnect();outsider.disconnect()

if __name__=='__main__':unittest.main(verbosity=2)
