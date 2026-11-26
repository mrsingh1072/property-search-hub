import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from api import auth

class EmailCodeTests(unittest.TestCase):
    def setUp(self):
        auth._otp_store.clear();auth._otp_attempts.clear();auth._otp_last_sent.clear()
        sender=patch('notifications.email_notifier._send',return_value=True)
        self.send=sender.start();self.addCleanup(sender.stop)
    def test_expired_code_is_rejected(self):
        with patch('api.auth.time.time',return_value=1000):
            self.assertTrue(auth.request_otp('buyer@example.com'))
        code=auth._otp_store['buyer@example.com'][0]
        with patch('api.auth.time.time',return_value=1600):
            self.assertFalse(auth.verify_otp('buyer@example.com',code))
    def test_email_normalization_and_invalid_email(self):
        self.assertFalse(auth.request_otp('abc@'))
        self.assertTrue(auth.request_otp('  BUYER@example.com '))
        code=auth._otp_store['buyer@example.com'][0]
        self.assertTrue(auth.verify_otp('Buyer@Example.com',code))
    def test_resend_invalidates_previous_code(self):
        with patch('api.auth.time.time',return_value=1000),patch('api.auth.secrets.randbelow',return_value=123456):
            self.assertTrue(auth.request_otp('buyer@example.com'))
        with patch('api.auth.time.time',return_value=1061),patch('api.auth.secrets.randbelow',return_value=654321):
            self.assertTrue(auth.request_otp('buyer@example.com'))
            self.assertFalse(auth.verify_otp('buyer@example.com','123456'))
            self.assertTrue(auth.verify_otp('buyer@example.com','654321'))
    def test_success_does_not_reset_resend_delay(self):
        auth.request_otp('buyer@example.com')
        code=auth._otp_store['buyer@example.com'][0]
        self.assertTrue(auth.verify_otp('buyer@example.com',code))
        self.assertFalse(auth.request_otp('buyer@example.com'))
        self.assertEqual(self.send.call_count,1)
    def test_failed_resend_does_not_leave_an_active_code(self):
        with patch('api.auth.time.time',return_value=1000):auth.request_otp('buyer@example.com')
        with patch('api.auth.time.time',return_value=1061):
            self.send.return_value=False
            self.assertFalse(auth.request_otp('buyer@example.com'))
            self.assertNotIn('buyer@example.com',auth._otp_store)
    def test_wrong_guesses_lock_broker_code(self):
        auth.request_otp('broker@example.com',purpose='broker')
        code=auth._otp_store['broker:broker@example.com'][0]
        wrong='000000' if code!='000000' else '111111'
        for _ in range(5):self.assertFalse(auth.verify_otp('broker@example.com',wrong,purpose='broker'))
        self.assertFalse(auth.verify_otp('broker@example.com',code,purpose='broker'))
    def test_non_ascii_digits_fail_without_crashing(self):
        auth.request_otp('buyer@example.com')
        self.assertFalse(auth.verify_otp('buyer@example.com','１２３４５６'))
    def test_only_one_concurrent_verification_succeeds(self):
        auth.request_otp('buyer@example.com')
        code=auth._otp_store['buyer@example.com'][0]
        with ThreadPoolExecutor(max_workers=8) as executor:
            outcomes=list(executor.map(lambda _:auth.verify_otp('buyer@example.com',code),range(8)))
        self.assertEqual(sum(outcomes),1)

if __name__=='__main__':unittest.main()
