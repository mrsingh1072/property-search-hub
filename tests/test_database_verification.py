import unittest
from unittest.mock import patch

from scripts.verify_services import main


class DatabaseVerificationTests(unittest.TestCase):
    @patch('agent.llm_client.complete')
    @patch('database.supabase_client.get_client')
    @patch('scripts.check_config.configuration_status', return_value={
        'ready': False, 'required': {'database': True, 'ai_provider': False}})
    def test_database_only_does_not_require_or_call_ai(self, status, client, complete):
        self.assertEqual(main(['--database-only']), 0)
        self.assertEqual(client.return_value.table.call_count, 7)
        client.return_value.rpc.assert_called_once()
        complete.assert_not_called()

    @patch('database.supabase_client.get_client')
    @patch('scripts.check_config.configuration_status', return_value={
        'ready': False, 'required': {'database': False}})
    def test_missing_database_does_not_attempt_connection(self, status, client):
        self.assertEqual(main(['--database-only']), 1)
        client.assert_not_called()


if __name__ == '__main__':
    unittest.main()
