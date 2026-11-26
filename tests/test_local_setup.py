import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from api.main import app
from api import auth
from scripts.setup_local import create_env
from scripts.check_config import configuration_status


class LocalSetupTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.client = TestClient(app)
        auth._otp_store.clear()
        auth._otp_attempts.clear()
        auth._otp_last_sent.clear()
        from api.staff_auth import _ATTEMPTS
        _ATTEMPTS.clear()

    def tearDown(self):
        self.env.stop()

    def test_health_is_alive_but_not_ready_without_credentials(self):
        self.assertEqual(self.client.get('/health').json(), {'status': 'ok'})
        response = self.client.get('/ready')
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()['ready'])

    def test_chat_explains_missing_configuration(self):
        response = self.client.post('/chat', json={'session_id': 'test', 'message': 'Hello'})
        self.assertEqual(response.status_code, 503)
        self.assertIn('credentials', response.json()['detail'])

    def test_empty_chat_is_rejected(self):
        response = self.client.post('/chat', json={'session_id': '', 'message': ''})
        self.assertEqual(response.status_code, 422)

    def test_setup_generates_unique_secrets_and_preserves_existing_env(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / '.env'
            self.assertTrue(create_env(destination))
            original = destination.read_text(encoding='utf-8')
            secrets = [line.split('=', 1)[1] for line in original.splitlines()
                       if line.startswith(('JWT_SECRET=', 'ADMIN_SESSION_SECRET=', 'ADMIN_PASSWORD='))]
            self.assertEqual(len(set(secrets)), 3)
            self.assertTrue(all(len(value) >= 32 for value in secrets))
            self.assertFalse(create_env(destination))
            self.assertEqual(destination.read_text(encoding='utf-8'), original)

    def test_readiness_does_not_expose_secrets_or_require_optional_channels(self):
        os.environ.update(SUPABASE_URL='https://test.supabase.co',
                          SUPABASE_SERVICE_ROLE_KEY='private-db-key', GROQ_API_KEY='private-ai-key',
                          JWT_SECRET='j' * 40, ADMIN_SESSION_SECRET='t' * 40, ADMIN_PASSWORD='p' * 40, ADMIN_USERNAME='admin')
        status = configuration_status()
        self.assertTrue(status['ready'])
        self.assertFalse(status['optional']['whatsapp'])
        response = self.client.get('/ready')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('private-db-key', response.text)
        self.assertNotIn('private-ai-key', response.text)

    @patch('notifications.email_notifier._send', return_value=False)
    def test_failed_email_does_not_issue_otp(self, send):
        self.assertFalse(auth.request_otp('buyer@example.com'))
        self.assertNotIn('buyer@example.com', auth._otp_store)

    @patch('notifications.email_notifier._send', return_value=True)
    def test_otp_is_single_use_and_resend_is_throttled(self, send):
        self.assertTrue(auth.request_otp('buyer@example.com'))
        code = auth._otp_store['buyer@example.com'][0]
        self.assertFalse(auth.request_otp('buyer@example.com'))
        self.assertEqual(send.call_count, 1)
        self.assertTrue(auth.verify_otp('buyer@example.com', code))
        self.assertFalse(auth.verify_otp('buyer@example.com', code))

    @patch('notifications.email_notifier._send', return_value=True)
    def test_otp_locks_after_five_wrong_guesses(self, send):
        auth.request_otp('buyer@example.com')
        code = auth._otp_store['buyer@example.com'][0]
        wrong = '000000' if code != '000000' else '111111'
        for _ in range(5):
            self.assertFalse(auth.verify_otp('buyer@example.com', wrong))
        self.assertFalse(auth.verify_otp('buyer@example.com', code))

    def test_admin_sign_in_and_invalid_password(self):
        os.environ.update(ADMIN_USERNAME='admin', ADMIN_PASSWORD='long-test-password', ADMIN_SESSION_SECRET='s' * 40)
        response = self.client.post('/admin/auth', json={'username': 'admin', 'password': 'long-test-password'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['role'], 'admin')
        self.assertIn('token', response.json())
        self.assertEqual(self.client.post('/admin/auth', json={
            'username': 'admin', 'password': 'wrong'}).status_code, 401)

    def test_optional_webhooks_fail_closed_without_configuration(self):
        self.assertEqual(self.client.post('/webhook/whatsapp', json={}).status_code, 503)
        self.assertEqual(self.client.post('/webhook/telegram', json={}).status_code, 503)

    def test_telegram_rejects_missing_secret_header(self):
        os.environ.update(TELEGRAM_BOT_TOKEN='test-token', TELEGRAM_WEBHOOK_SECRET='test-secret')
        self.assertEqual(self.client.post('/webhook/telegram', json={}).status_code, 403)

    @patch('api.main.process_message', return_value={'reply': 'Hello from ApnaGhar', 'properties': []})
    @patch('api.main.get_session', return_value={})
    def test_configured_chat_returns_agent_response(self, session, process):
        os.environ.update(SUPABASE_URL='https://test.supabase.co',
                          SUPABASE_SERVICE_ROLE_KEY='test-key', GROQ_API_KEY='test-ai')
        response = self.client.post('/chat', json={'session_id': 'test', 'message': 'hello'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['reply'], 'Hello from ApnaGhar')


if __name__ == '__main__':
    unittest.main()
