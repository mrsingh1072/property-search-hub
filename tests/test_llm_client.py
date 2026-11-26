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


    @patch.object(llm, 'GEMINI_MODEL', 'gemini-3.5-flash-lite')
    @patch.object(llm.requests, 'post')
    def test_flash_lite_uses_supported_minimal_thinking(self, post):
        post.return_value.json.return_value = {'candidates': [{'content': {'parts': [{'text': 'OK'}]}, 'finishReason': 'STOP'}]}
        self.assertEqual(llm._gemini_complete([{'role': 'user', 'content': 'hi'}], 0, 24, False, 'key'), 'OK')
        config = post.call_args.kwargs['json']['generationConfig']
        self.assertEqual(config['thinkingConfig'], {'thinkingLevel': 'MINIMAL'})
        self.assertGreaterEqual(config['maxOutputTokens'], 512)

    @patch.object(llm, 'GEMINI_MODEL', 'gemini-3.8-flash')
    @patch.object(llm.requests, 'post')
    def test_current_flash_uses_low_thinking_with_output_headroom(self, post):
        post.return_value.json.return_value = {'candidates': [{'content': {'parts': [{'text': 'OK'}]}}]}
        llm._gemini_complete([{'role': 'user', 'content': 'hi'}], 0, 24, False, 'key')
        config = post.call_args.kwargs['json']['generationConfig']
        self.assertEqual(config['thinkingConfig'], {'thinkingLevel': 'LOW'})
        self.assertGreaterEqual(config['maxOutputTokens'], 1024)

    @patch.object(llm.requests, 'post')
    def test_incomplete_response_is_rejected(self, post):
        post.return_value.json.return_value = {'candidates': [{'finishReason': 'MAX_TOKENS', 'content': {'parts': [{'text': '{'}]}}]}
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            llm._gemini_complete([{'role': 'user', 'content': 'hi'}], 0, 100, True, 'key')

    @patch.object(llm.requests, 'post')
    def test_thought_parts_are_excluded_from_user_reply(self, post):
        post.return_value.json.return_value = {'candidates': [{'content': {'parts': [
            {'text': 'Internal placeholder', 'thought': True}, {'text': 'Visible answer'}]}}]}
        self.assertEqual(llm._gemini_complete([{'role': 'user', 'content': 'hi'}], 0, 100, False, 'key'), 'Visible answer')


if __name__ == '__main__':
    unittest.main()
