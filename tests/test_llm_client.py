import os
import unittest
from unittest.mock import Mock, patch

from agent import llm_client as llm


class LlmClientTests(unittest.TestCase):
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'gemini-test', 'OPENROUTER_API_KEY': 'router-test'}, clear=True)
    @patch.object(llm, '_openrouter_complete', return_value='fallback answer')
    @patch.object(llm, '_groq_complete', side_effect=RuntimeError('unavailable'))
    @patch.object(llm, '_gemini_complete', side_effect=RuntimeError('unavailable'))
    def test_provider_failure_falls_back(self, gemini, groq, router):
        self.assertEqual(llm.complete([{'role': 'user', 'content': 'hi'}]), 'fallback answer')
        gemini.assert_called_once()
        groq.assert_called_once()
        router.assert_called_once()

    @patch.object(llm.requests, 'post')
    def test_gemini_key_is_in_header_and_response_is_parsed(self, post):
        response = Mock()
        response.json.return_value = {'candidates': [{'content': {'parts': [{'text': 'Hello'}]}}]}
        post.return_value = response
        answer = llm._gemini_complete([{'role': 'system', 'content': 'Be helpful'},
                                      {'role': 'user', 'content': 'hi'}], 0.2, 100, True, 'private-key')
        self.assertEqual(answer, 'Hello')
        self.assertNotIn('private-key', post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs['headers']['x-goog-api-key'], 'private-key')
        self.assertEqual(post.call_args.kwargs['json']['generationConfig']['responseMimeType'], 'application/json')

    @patch.object(llm.requests, 'post')
    def test_empty_provider_response_is_a_failure(self, post):
        post.return_value.json.return_value = {'candidates': []}
        with self.assertRaises(RuntimeError):
            llm._gemini_complete([{'role': 'user', 'content': 'hi'}], 0.2, 100, False, 'key')


if __name__ == '__main__':
    unittest.main()
