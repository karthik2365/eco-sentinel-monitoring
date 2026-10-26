import unittest
from unittest.mock import patch,MagicMock
from services.gemini_service import response_text,AIServiceError,GeminiService

class AIResponseTests(unittest.TestCase):
    def test_success(self):
        self.assertEqual(response_text({'choices':[{'finish_reason':'stop','message':{'content':' OK '}}]}),'OK')

    def test_http_200_provider_error_is_not_connection_error(self):
        with self.assertRaisesRegex(AIServiceError,'rate limited'):
            response_text({'error':{'code':429,'message':'Provider busy'},'choices':None})

    def test_reasoning_exhaustion_is_not_connection_error(self):
        with self.assertRaisesRegex(AIServiceError,'output limit'):
            response_text({'choices':[{'finish_reason':'length','message':{'content':None}}]})

    def test_missing_completion_is_explicit(self):
        with self.assertRaisesRegex(AIServiceError,'no completion'):
            response_text({'choices':None})

    def test_temporary_error_retries_once_and_returns_answer(self):
        error=MagicMock();error.model_dump.return_value={'error':{'code':503}}
        good=MagicMock();good.model_dump.return_value={'choices':[{'finish_reason':'stop','message':{'content':'answer'}}]}
        with patch('services.gemini_service.Config.get_api_keys',return_value=['test-key']), patch('services.gemini_service.OpenAI') as client, patch('services.gemini_service.time.sleep'):
            call=client.return_value.__enter__.return_value.chat.completions.create
            call.side_effect=[error,good]
            self.assertEqual(GeminiService()._generate('test'),'answer')
            self.assertEqual(call.call_count,2)
            self.assertEqual(call.call_args.kwargs['extra_body']['reasoning']['effort'],'none')
            self.assertEqual(call.call_args.kwargs['max_tokens'],4096)

    def test_rate_limit_is_not_retried_immediately(self):
        error=MagicMock();error.model_dump.return_value={'error':{'code':429}}
        with patch('services.gemini_service.Config.get_api_keys',return_value=['test-key']), patch('services.gemini_service.OpenAI') as client:
            call=client.return_value.__enter__.return_value.chat.completions.create
            call.return_value=error
            with self.assertRaisesRegex(AIServiceError,'rate limited'): GeminiService()._generate('test')
            self.assertEqual(call.call_count,1)

    def test_incompatible_reasoning_setting_retries_with_model_defaults(self):
        with patch('services.gemini_service.Config.get_api_keys',return_value=['test-key']), patch('services.gemini_service.OpenAI') as client:
            call=client.return_value.__enter__.return_value.chat.completions.create
            call.side_effect=[{'error':{'code':400}}, {'choices':[{'message':{'content':'answer'},'finish_reason':'stop'}]}]
            self.assertEqual(GeminiService()._generate('test'),'answer')
            self.assertEqual(call.call_count,2)
            self.assertEqual(call.call_args.kwargs['extra_body'],{})
            self.assertEqual(call.call_args.kwargs['max_tokens'],16384)

    def test_output_exhaustion_gets_one_larger_budget(self):
        with patch('services.gemini_service.Config.get_api_keys',return_value=['test-key']), patch('services.gemini_service.OpenAI') as client:
            call=client.return_value.__enter__.return_value.chat.completions.create
            call.side_effect=[{'choices':[{'message':{'content':None},'finish_reason':'length'}]}, {'choices':[{'message':{'content':'answer'},'finish_reason':'stop'}]}]
            self.assertEqual(GeminiService()._generate('test'),'answer')
            self.assertEqual(call.call_args.kwargs['max_tokens'],16384)

    def test_gateway_timeout_is_retryable(self):
        with self.assertRaises(AIServiceError) as caught:
            response_text({'error':{'code':504}})
        self.assertTrue(caught.exception.retryable)
        self.assertIn('timed out',str(caught.exception))

    def test_safety_classifier_output_is_not_a_completed_answer(self):
        with self.assertRaises(AIServiceError) as caught:
            response_text({'choices':[{'message':{'content':'User Safety: safe'},'finish_reason':'stop'}]})
        self.assertTrue(caught.exception.retryable)

    def test_report_details_preserve_complete_observed_evidence(self):
        from agents.reporting_agent import ReportingAgent
        evidence='Observed image difference. ' * 20
        with patch('agents.reporting_agent.gemma_service.generate_text') as provider:
            text=ReportingAgent()._generate_detailed_analysis([{'description':evidence,'category':'Water Surface Change','confidence':0.7}])
        self.assertIn(evidence.strip(),text)
        self.assertIn('uncalibrated',text)
        provider.assert_not_called()

if __name__=='__main__':unittest.main()
