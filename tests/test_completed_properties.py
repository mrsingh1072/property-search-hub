import unittest
from unittest.mock import Mock,patch
from fastapi.testclient import TestClient
from api.main import app
import test_verified_brokers as brokers_fixture

class CompletedPropertyTests(unittest.TestCase):
    setUp=brokers_fixture.VerifiedBrokerTests.setUp
    token=brokers_fixture.VerifiedBrokerTests.token
    headers=brokers_fixture.VerifiedBrokerTests.headers
    admin_headers=brokers_fixture.VerifiedBrokerTests.admin_headers
    get_user=brokers_fixture.VerifiedBrokerTests.get_user
    def customer(self):return {'id':'customer-a','name':'Buyer','email':'buyer@example.invalid','favourites':[]}
    def payload(self):return {'customer_email':'buyer@example.invalid','transaction_type':'purchase','completed_on':'2020-01-02'}
    def prepare_completion(self):
        self.db.rows['properties'][0]['city']='Patna'
        self.db.rows['customers']=[{'id':'customer-a','email':'buyer@example.invalid'}]
    def test_customer_only_reads_their_completed_records(self):
        self.db.rows['property_transactions']=[{'id':'own','customer_id':'customer-a','transaction_type':'purchase','completed_on':'2020-01-02','property_snapshot':{'area_name':'Boring Road'}},
            {'id':'other','customer_id':'customer-b','transaction_type':'rent','completed_on':'2020-01-02','property_snapshot':{}}]
        with patch('api.main._current_customer',return_value=self.customer()):
            response=self.client.get('/me/properties?customer_id=customer-b',headers={'Authorization':'Bearer customer'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual([r['id'] for r in response.json()['properties']],['own'])
    def test_favourites_and_visits_do_not_count_as_owned_properties(self):
        self.db.rows['property_transactions']=[]
        customer={**self.customer(),'favourites':['properties-a']}
        with patch('api.main._current_customer',return_value=customer):
            response=self.client.get('/me/properties')
        self.assertEqual(response.json(),{'properties':[]})
    def test_customer_property_data_requires_customer_login(self):
        for headers in ({},self.headers(),self.admin_headers()):
            self.assertEqual(self.client.get('/me/properties',headers=headers).status_code,401)
    def test_missing_migration_is_an_error_instead_of_false_empty_result(self):
        self.db.table=Mock(side_effect=RuntimeError('table unavailable'))
        with patch('api.main._current_customer',return_value=self.customer()):
            response=self.client.get('/me/properties')
        self.assertEqual(response.status_code,503)
        self.assertIn('008',response.json()['detail'])
    def test_broker_can_record_completion_only_for_own_listing(self):
        self.prepare_completion()
        self.db.rpc=Mock(wraps=self.db.rpc)
        response=self.client.post('/broker/properties/properties-a/completion',headers=self.headers(),json={**self.payload(),'broker_id':'b','customer_id':'customer-b'})
        self.assertEqual(response.status_code,200,response.text)
        name,params=self.db.rpc.call_args.args
        self.assertEqual(name,'record_property_transaction')
        self.assertEqual(params['p_broker_id'],'a')
        self.assertEqual(params['p_customer_id'],'customer-a')
        self.assertEqual(params['p_recorded_by'],'user-a')
    def test_other_broker_completion_is_denied_before_rpc(self):
        self.prepare_completion();self.db.rpc=Mock()
        response=self.client.post('/broker/properties/properties-b/completion',headers=self.headers(),json=self.payload())
        self.assertEqual(response.status_code,404);self.db.rpc.assert_not_called()
    def test_customer_cannot_record_their_own_purchase(self):
        response=self.client.post('/broker/properties/properties-a/completion',json=self.payload())
        self.assertEqual(response.status_code,401)
    def test_customer_must_have_an_account(self):
        self.prepare_completion();self.db.rows['customers']=[];self.db.rpc=Mock()
        response=self.client.post('/broker/properties/properties-a/completion',headers=self.headers(),json=self.payload())
        self.assertEqual(response.status_code,400);self.db.rpc.assert_not_called()
    def test_bad_type_invalid_or_future_date_is_rejected(self):
        self.prepare_completion();self.db.rpc=Mock()
        for fields in ({'transaction_type':'saved'},{'completed_on':'2020-99-99'},{'completed_on':'2999-01-01'}):
            response=self.client.post('/broker/properties/properties-a/completion',headers=self.headers(),json={**self.payload(),**fields})
            self.assertEqual(response.status_code,400,response.text)
        self.db.rpc.assert_not_called()
    def test_rental_type_is_passed_to_atomic_completion(self):
        self.prepare_completion();self.db.rpc=Mock(wraps=self.db.rpc)
        response=self.client.post('/broker/properties/properties-a/completion',headers=self.headers(),json={**self.payload(),'transaction_type':'rent'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.db.rpc.call_args.args[1]['p_transaction_type'],'rent')
    def test_completion_failure_is_not_reported_as_success(self):
        self.prepare_completion();self.db.rpc=Mock(side_effect=RuntimeError('RPC missing'))
        response=self.client.post('/broker/properties/properties-a/completion',headers=self.headers(),json=self.payload())
        self.assertEqual(response.status_code,503)
    def test_standalone_page_and_completion_form_are_available(self):
        response=self.client.get('/my-properties')
        self.assertEqual(response.status_code,200)
        self.assertIn('No properties yet',response.text)
        self.assertIn('Browse homes to buy or rent',response.text)
        self.assertIn('/static/my-properties.js',response.text)
        response=self.client.get('/broker/properties/properties-a/complete',headers=self.headers())
        self.assertEqual(response.status_code,200,response.text)
        self.assertIn('completion-form',response.text)
        self.assertEqual(self.client.get('/broker/properties/properties-b/complete',headers=self.headers()).status_code,404)
    def test_missing_customer_does_not_expose_transactions(self):
        with patch('api.main._current_customer',return_value=None):
            self.assertEqual(self.client.get('/me/properties').status_code,401)

if __name__=='__main__':unittest.main()
