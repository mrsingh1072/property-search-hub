import unittest
from unittest.mock import patch
from api import auth

class GoogleSignInTests(unittest.TestCase):
    def setUp(self):
        self.client=patch.object(auth,'GOOGLE_CLIENT_ID','test-web-client.apps.googleusercontent.com')
        self.client.start();self.addCleanup(self.client.stop)
    @patch('google.oauth2.id_token.verify_oauth2_token')
    def test_valid_verified_google_identity(self,verify):
        verify.return_value={'sub':'google-user','email':'Buyer@Example.com','email_verified':True,'name':'Buyer'}
        self.assertEqual(auth.verify_google('test-id-token'),{'sub':'google-user','email':'buyer@example.com','name':'Buyer'})
        self.assertEqual(verify.call_args.args[2],'test-web-client.apps.googleusercontent.com')
    @patch('google.oauth2.id_token.verify_oauth2_token')
    def test_unverified_or_incomplete_identity_is_rejected(self,verify):
        for info in [{'sub':'u','email':'buyer@example.com'}, {'sub':'u','email':'buyer@example.com','email_verified':False},
                     {'email':'buyer@example.com','email_verified':True}, {'sub':'u','email':'broken','email_verified':True}]:
            verify.return_value=info
            self.assertIsNone(auth.verify_google('test-id-token'))
    @patch('google.oauth2.id_token.verify_oauth2_token',side_effect=ValueError('Wrong audience or expired token'))
    def test_invalid_google_token_is_rejected(self,verify):
        self.assertIsNone(auth.verify_google('invalid-id-token'))
    @patch('google.oauth2.id_token.verify_oauth2_token')
    def test_missing_configuration_or_token_does_not_verify(self,verify):
        self.assertIsNone(auth.verify_google(''))
        with patch.object(auth,'GOOGLE_CLIENT_ID',''):
            self.assertIsNone(auth.verify_google('token'))
        verify.assert_not_called()

if __name__=='__main__':unittest.main()
