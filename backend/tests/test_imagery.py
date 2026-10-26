"""Regression tests for real-data coverage selection; Earth Engine is mocked here."""
import unittest
from unittest.mock import MagicMock, patch
from services.gee_service import gee_service

class ImageryQualityTests(unittest.TestCase):
    def run_preview(self, coverages, adaptive=True):
        composite=MagicMock()
        composites=[(composite, 10, c) for c in coverages]
        with patch.object(gee_service, '_initialized', True), \
             patch.object(gee_service, '_create_geometry', return_value='geometry'), \
             patch.object(gee_service, '_composite', side_effect=composites) as fetch, \
             patch.object(gee_service, '_get_visualization', return_value=(composite, {})):
            result,_=gee_service.get_quality_imagery({}, '2026-08-25', '2026-09-24', adaptive=adaptive)
        return result,fetch

    def test_stops_when_requested_period_is_clear(self):
        result,fetch=self.run_preview([100])
        self.assertTrue(result['readyForAnalysis'])
        self.assertFalse(result['expandedWindow'])
        self.assertEqual(fetch.call_count,1)

    def test_fills_gaps_with_explicit_earlier_window(self):
        result,fetch=self.run_preview([72,99.95])
        self.assertEqual(result['startDate'],'2026-07-26')
        self.assertEqual(result['endDate'],'2026-09-24')
        self.assertTrue(result['expandedWindow'])
        self.assertEqual(fetch.call_count,2)

    def test_incomplete_preview_cannot_be_analyzed(self):
        result,fetch=self.run_preview([1,10,50,90])
        self.assertFalse(result['readyForAnalysis'])
        self.assertEqual(fetch.call_count,4)

    def test_analysis_does_not_silently_widen_dates(self):
        result,fetch=self.run_preview([72],adaptive=False)
        self.assertFalse(result['readyForAnalysis'])
        self.assertEqual(fetch.call_count,1)
        with patch.object(gee_service,'get_quality_imagery',return_value=(result,None)):
            with self.assertRaisesRegex(ValueError,'72%'):
                gee_service.get_sentinel2_imagery({},'2026-08-25','2026-09-24')

    def test_no_scenes_reports_useful_error(self):
        with patch.object(gee_service,'_initialized',True), patch.object(gee_service,'_create_geometry'), \
             patch.object(gee_service,'_composite',return_value=(None,0,0)):
            with self.assertRaisesRegex(ValueError,'No satellite scenes'):
                gee_service.get_quality_imagery({},'2026-08-25','2026-09-24')

if __name__=='__main__': unittest.main()
