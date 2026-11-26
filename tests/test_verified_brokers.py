"""Broker access regression tests using an isolated database and Auth adapter."""
import copy
import os
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import jwt
from fastapi import HTTPException
from fastapi.testclient import TestClient
from api.main import app
from api import staff_auth
from database.staff_scope import ScopedClient, StaffPrincipal, current_staff


class Query:
    def __init__(self, client, table, op='select', payload=None):
        self.client, self.table, self.op, self.payload = client, table, op, payload
        self.filters = []
        self.maximum = None
    def eq(self, key, value): self.filters.append(lambda row: row.get(key) == value); return self
    def in_(self, key, values): self.filters.append(lambda row: row.get(key) in values); return self
    def neq(self, key, value): self.filters.append(lambda row: row.get(key) != value); return self
    def order(self, *a, **k): return self
    def limit(self, maximum): self.maximum = maximum; return self
    def execute(self):
        rows = self.client.rows.setdefault(self.table, [])
        selected = [row for row in rows if all(f(row) for f in self.filters)]
        if self.maximum is not None: selected = selected[:self.maximum]
        if self.op in {'insert', 'upsert'}:
            if self.client.fail_insert: raise RuntimeError('test database failure')
            items = self.payload if isinstance(self.payload, list) else [self.payload]
            for item in items:
                existing = next((r for r in rows if r.get('id') == item.get('id')), None)
                if existing is not None and self.op == 'upsert': existing.update(copy.deepcopy(item))
                else: rows.append(copy.deepcopy(item))
            selected = items
        if self.op == 'update':
            for row in selected: row.update(copy.deepcopy(self.payload))
        if self.op == 'delete':
            self.client.rows[self.table] = [row for row in rows if row not in selected]
        return NS(data=copy.deepcopy(selected))


class Table:
    def __init__(self, client, name): self.client, self.name = client, name
    def select(self, *a, **k): return Query(self.client, self.name)
    def insert(self, data, **k): return Query(self.client, self.name, 'insert', data)
    def upsert(self, data, **k): return Query(self.client, self.name, 'upsert', data)
    def update(self, data, **k): return Query(self.client, self.name, 'update', data)
    def delete(self, **k): return Query(self.client, self.name, 'delete')


class Database:
    def __init__(self):
        self.rows = {'brokers': [], 'broker_reviews': []}
        self.fail_insert = False
        self.fail_review = False
        self.auth = NS(admin=NS(create_user=Mock(return_value=NS(user=NS(id='new-user'))),
                               delete_user=Mock(), update_user_by_id=Mock()))
    def table(self, name): return Table(self, name)
    def rpc(self, name, params):
        def execute():
            if self.fail_review: raise RuntimeError('test RPC failure')
            if name == 'review_broker_application':
                row = next(r for r in self.rows['brokers'] if r['id'] == params['target_broker_id'])
                row.update(approval_status=params['next_status'], is_active=params['next_status'] == 'approved')
                self.rows['broker_reviews'].append(copy.deepcopy(params))
                return NS(data=row)
            return NS(data=[])
        return NS(execute=execute)


class VerifiedBrokerTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        for letter in ('a', 'b'):
            self.db.rows['brokers'].append({'id': letter, 'auth_user_id': 'user-' + letter,
                'name': 'Broker ' + letter, 'email': letter + '@example.invalid',
                'phone': '987654321' + ('0' if letter == 'a' else '1'),
                'approval_status': 'approved', 'is_active': True})
        for table in ('properties', 'leads', 'meetings'):
            self.db.rows[table] = [{'id': table + '-' + b, 'broker_id': b, 'session_id': 'session-' + b,
                'data': {'source_ids': {'broker_id': b}}, 'status': 'available'} for b in ('a', 'b')]
        self.db.rows['sessions'] = [{'session_id': 'session-' + b} for b in ('a', 'b')]
        self.auth = NS(auth=NS(get_user=Mock(side_effect=self.get_user),
            sign_in_with_password=Mock(return_value=NS(user=NS(id='user-a'), session=NS(access_token=self.token('a'))))))
        for target, value in [('database.supabase_client.get_service_client', self.db), ('api.staff_auth.auth_client', self.auth)]:
            p = patch(target, return_value=value); p.start(); self.addCleanup(p.stop)
        p = patch.dict(os.environ, {'ADMIN_USERNAME': 'owner', 'ADMIN_PASSWORD': 'owner-password-for-test',
                                   'ADMIN_SESSION_SECRET': 'admin-signing-key-for-tests-only-123456789'})
        p.start(); self.addCleanup(p.stop)
        staff_auth._ATTEMPTS.clear()
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.principal = StaffPrincipal('broker', broker_id='a', user_id='user-a', name='Broker a', phone='9876543210')
        self.scoped = ScopedClient(self.db, self.principal)
    def token(self, broker): return jwt.encode({'sub': 'user-' + broker, 'aud': 'authenticated'}, 'fake-provider-signing-key-123456789', algorithm='HS256')
    def get_user(self, token):
        for broker in ('a', 'b'):
            if token == self.token(broker): return NS(user=NS(id='user-' + broker))
        raise ValueError('Invalid user token')
    def headers(self): return {'Authorization': 'Bearer ' + self.token('a')}
    def admin_headers(self): return {'Authorization': 'Bearer ' + staff_auth.admin_sign_in('owner', 'owner-password-for-test')}
    def application(self):
        return {'name': 'New Broker', 'email': 'new@example.invalid', 'phone': '9876543299',
                'password': 'applicant-password-for-test', 'areas': ['Boring Road']}

    def test_application_always_pending_and_password_only_in_auth(self):
        payload = {**self.application(), 'approval_status': 'approved', 'is_active': True, 'role': 'admin'}
        response = self.client.post('/broker/apply', json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        row = self.db.rows['brokers'][-1]
        self.assertEqual(row['approval_status'], 'pending'); self.assertFalse(row['is_active'])
        self.assertNotIn('password', row); self.assertNotIn('password', response.text)
        self.assertFalse(self.db.auth.admin.create_user.call_args.args[0]['email_confirm'])
    def test_application_rollback_deletes_only_new_auth_user(self):
        self.db.fail_insert = True
        self.assertEqual(self.client.post('/broker/apply', json=self.application()).status_code, 400)
        self.db.auth.admin.delete_user.assert_called_once_with('new-user')
    def test_duplicate_application_does_not_create_auth_user(self):
        payload = {**self.application(), 'email': 'a@example.invalid'}
        self.assertEqual(self.client.post('/broker/apply', json=payload).status_code, 409)
        self.db.auth.admin.create_user.assert_not_called()
    def test_unapproved_states_block_sign_in_and_existing_sessions(self):
        for status in ('pending', 'rejected', 'suspended'):
            self.db.rows['brokers'][0].update(approval_status=status, is_active=False)
            self.assertEqual(self.client.post('/broker/auth', json={'email':'a@example.invalid','password':'test'}).status_code, 403)
            self.assertEqual(self.client.get('/broker/me', headers=self.headers()).status_code, 403)
        self.auth.auth.sign_in_with_password.assert_not_called()
    def test_approved_login_sets_http_only_cookie(self):
        response = self.client.post('/broker/auth', json={'email':'a@example.invalid','password':'test'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('HttpOnly', response.headers['set-cookie'])
        self.assertIn('SameSite=strict', response.headers['set-cookie'])
        self.assertEqual(self.client.get('/broker/me').json()['broker_id'], 'a')
    def test_inactive_approved_account_is_blocked(self):
        self.db.rows['brokers'][0]['is_active'] = False
        self.assertEqual(self.client.get('/broker/me', headers=self.headers()).status_code, 403)
    def test_broker_cannot_review_or_list_other_accounts(self):
        self.assertEqual(self.client.get('/admin/brokers', headers=self.headers()).status_code, 403)
        self.assertEqual(self.client.post('/admin/brokers/b/review', headers=self.headers(), json={'action':'approved'}).status_code, 403)
        self.assertEqual(len(self.db.rows['broker_reviews']), 0)
    def test_admin_approval_confirms_account_and_records_review(self):
        self.db.rows['brokers'][0].update(approval_status='pending', is_active=False)
        response = self.client.post('/admin/brokers/a/review', headers=self.admin_headers(), json={'action':'approved','note':'Contact verified'})
        self.assertEqual(response.status_code, 200, response.text)
        self.db.auth.admin.update_user_by_id.assert_called_once_with('user-a', {'email_confirm':True})
        self.assertEqual(self.db.rows['brokers'][0]['approval_status'], 'approved')
        self.assertEqual(self.db.rows['broker_reviews'][0]['reviewer_name'], 'owner')
    def test_failed_approval_does_not_grant_access(self):
        self.db.rows['brokers'][0].update(approval_status='pending', is_active=False)
        self.db.fail_review = True
        self.assertEqual(self.client.post('/admin/brokers/a/review', headers=self.admin_headers(), json={'action':'approved'}).status_code, 503)
        self.assertEqual(self.client.get('/broker/me', headers=self.headers()).status_code, 403)
    def test_admin_suspension_blocks_existing_session(self):
        self.assertEqual(self.client.get('/broker/me', headers=self.headers()).status_code, 200)
        self.assertEqual(self.client.post('/admin/brokers/a/review', headers=self.admin_headers(), json={'action':'suspended'}).status_code, 200)
        self.assertEqual(self.client.get('/broker/me', headers=self.headers()).status_code, 403)
    def test_local_admin_does_not_use_supabase_auth(self):
        token = staff_auth.admin_sign_in('owner', 'owner-password-for-test')
        self.assertEqual(staff_auth.authenticate_token(token).role, 'admin')
        self.auth.auth.get_user.assert_not_called()
        with self.assertRaises(HTTPException): staff_auth.admin_sign_in('owner', 'wrong')
    def test_admin_password_change_invalidates_existing_session(self):
        token = staff_auth.admin_sign_in('owner', 'owner-password-for-test')
        with patch.dict(os.environ, {'ADMIN_PASSWORD':'different-password-for-test'}):
            with self.assertRaises(HTTPException): staff_auth.authenticate_token(token)
    def test_forged_admin_and_old_shared_secret_are_rejected(self):
        forged = jwt.encode({'sub':'owner','role':'admin','aud':'apnaghar-admin'}, 'attacker-signing-key-123456789123456', algorithm='HS256')
        for token in (forged, 'old-shared-broker-secret'):
            self.assertEqual(self.client.get('/broker/me', headers={'Authorization':'Bearer '+token}).status_code, 401)
    def test_expired_admin_session_is_rejected(self):
        token = jwt.encode({'sub':'owner','role':'admin','aud':'apnaghar-admin','exp':1,'credential_version':'x'}, os.environ['ADMIN_SESSION_SECRET'], algorithm='HS256')
        with self.assertRaises(HTTPException): staff_auth.authenticate_token(token)
    def test_rate_limit_blocks_repeated_attempts(self):
        for _ in range(10): self.assertEqual(self.client.post('/admin/auth', json={'username':'owner','password':'wrong'}).status_code, 401)
        self.assertEqual(self.client.post('/admin/auth', json={'username':'owner','password':'wrong'}).status_code, 429)
    def test_cookie_write_from_other_origin_is_rejected(self):
        self.client.cookies.set(staff_auth.COOKIE_NAME, self.token('a'))
        response = self.client.post('/broker/property', headers={'Origin':'https://another.example'}, json={})
        self.assertEqual(response.status_code, 403)
    def test_private_html_requires_login(self):
        response = self.client.get('/broker', headers={'Accept':'text/html'}, follow_redirects=False)
        self.assertEqual(response.status_code, 303); self.assertEqual(response.headers['location'], '/broker/login')
    def test_private_responses_are_not_cached(self):
        self.assertEqual(self.client.get('/broker/me', headers=self.headers()).headers['cache-control'], 'no-store')
    def test_other_broker_resources_are_denied_before_side_effects(self):
        requests = [('POST','/broker/properties/properties-b/update', {'price_inr':1}),
                    ('DELETE','/broker/properties/properties-b', {}),
                    ('POST','/broker/properties/properties-b/sold', {}),
                    ('POST','/broker/leads/leads-b/status', {'status':'won'}),
                    ('POST','/broker/meetings/meetings-b/confirm', {}),
                    ('POST','/properties/properties-b/images/reorder', {'urls':[]})]
        before = copy.deepcopy(self.db.rows)
        for method, path, data in requests:
            response = self.client.request(method, path, headers=self.headers(), json=data)
            self.assertEqual(response.status_code, 404, path + response.text)
        for path in ('/broker/edit/properties-b','/broker/images/properties-b','/broker/properties/properties-b/documents'):
            self.assertEqual(self.client.get(path, headers=self.headers()).status_code, 404)
        self.assertEqual(self.db.rows, before)
    def test_reads_updates_and_deletes_always_enforce_ownership(self):
        for table in ('properties','leads','meetings'):
            self.assertEqual([r['broker_id'] for r in self.scoped.table(table).select('*').execute().data], ['a'])
            self.assertEqual(self.scoped.table(table).update({'status':'sold'}).eq('broker_id','b').execute().data, [])
            self.assertEqual(self.scoped.table(table).delete().eq('id',table+'-b').execute().data, [])
            self.assertEqual(self.scoped.table(table).update({'status':'booked'}).eq('id',table+'-a').execute().data[0]['status'], 'booked')
    def test_cannot_steal_other_broker_record_through_upsert(self):
        for table in ('properties','leads','meetings'):
            with self.assertRaises(HTTPException): self.scoped.table(table).upsert({'id':table+'-b'}).execute()
    def test_cannot_change_owner_or_approve_self(self):
        with self.assertRaises(HTTPException): self.scoped.table('properties').update({'broker_id':'b'}).execute()
        with self.assertRaises(HTTPException): self.scoped.table('brokers').update({'approval_status':'approved'}).execute()
        with self.assertRaises(HTTPException): self.scoped.rpc('review_broker_application', {})
        with self.assertRaises(HTTPException): self.scoped.table('customers').select('*').execute()
        with self.assertRaises(HTTPException): self.scoped.table('properties').insert({'id':'spoof','data':{'source_ids':{'broker_id':'b'}}}).execute()
    def test_sessions_brokers_and_booking_rpc_are_scoped(self):
        self.assertEqual(self.scoped.table('sessions').select('*').execute().data, [{'session_id':'session-a'}])
        self.assertEqual([r['id'] for r in self.scoped.table('brokers').select('*').execute().data], ['a'])
        with self.assertRaises(HTTPException): self.scoped.rpc('mark_property_booked', {'prop_id':'properties-b'})
        self.scoped.rpc('mark_property_booked', {'prop_id':'properties-a'}).execute()
    def test_new_listing_publishes_immediately_under_own_account(self):
        from database.supabase_client import upsert_property
        handle = current_staff.set(self.principal)
        try:
            upsert_property({'doc_id':'new-property','source_ids':{'property_id':'p1','broker_id':'a'},
                             'location':{'city':'Patna','state':'Bihar'},'property_profile':{},'pricing':{}}, 'test', [0.0]*384)
        finally: current_staff.reset(handle)
        row = self.db.rows['properties'][-1]
        self.assertEqual(row['broker_id'],'a'); self.assertEqual(row['status'],'available')
        self.assertNotIn('approval_status',row)
    def test_add_property_ignores_spoofed_broker_contact(self):
        with patch('api.main.create_property_from_fields', return_value={'ok':True}) as create:
            response = self.client.post('/broker/property', headers=self.headers(), json={
                'property_type':'Flat','price_inr':5000000,'address':'Boring Road',
                'broker_name':'Another person','broker_phone':'9876543211'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(create.call_args.kwargs['broker_id'],'a')
        self.assertEqual(create.call_args.args[0]['broker_phone'],'9876543210')
    def test_import_cannot_assign_another_broker_and_jobs_stay_private(self):
        from api.main import _UPLOAD_JOBS
        def run_import(job_id, filename, broker_id, column_map):
            Path(filename).unlink(missing_ok=True)
        from pathlib import Path
        try:
            with patch('api.main._run_upload', side_effect=run_import) as run:
                response = self.client.post('/upload', headers=self.headers(), data={'broker_id':'b'},
                    files={'file':('listings.csv',b'property_type,price_inr,address\nFlat,5000000,Boring Road','text/csv')})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(run.call_args.args[2],'a')
            job_id=response.json()['job_id']
            self.assertEqual(self.client.get('/upload/status/'+job_id,headers=self.headers()).status_code,200)
            self.assertEqual(self.client.get('/upload/status/'+job_id,headers={'Authorization':'Bearer '+self.token('b')}).status_code,404)
        finally: _UPLOAD_JOBS.clear()
    def test_other_broker_image_and_document_uploads_are_denied(self):
        for path in ('/properties/properties-b/images','/broker/properties/properties-b/documents'):
            response=self.client.post(path,headers=self.headers(),files={'file':('image.jpg',b'test','image/jpeg')})
            self.assertEqual(response.status_code,404,path+response.text)
    def test_same_buyer_gets_separate_leads_for_different_brokers(self):
        from agent.lead_collector import create_lead
        previous={'id':'old-lead','broker_id':'b','status':'won'}
        with patch('agent.lead_collector.get_user_profile',return_value={}), \
             patch('agent.lead_collector.get_recent_lead_by_phone',return_value=previous), \
             patch('agent.lead_collector.get_broker_for_area',return_value=self.db.rows['brokers'][0]), \
             patch('agent.lead_collector.save_lead',return_value={'id':'new-lead','broker_id':'a'}) as save, \
             patch('agent.lead_collector.update_lead') as update, \
             patch('agent.lead_collector._send_lead_notifications'):
            result=create_lead('buyer-session',{'area':'Boring Road'},'Buyer','9867245310')
        self.assertEqual(result['broker_id'],'a'); save.assert_called_once(); update.assert_not_called()
    def test_own_property_update_is_allowed_without_admin_review(self):
        with patch('api.main.update_property',return_value=True) as update, \
             patch('api.main.refresh_property_index',return_value={'ok':True}):
            response=self.client.post('/broker/properties/properties-a/update',headers=self.headers(),json={'price_inr':6000000})
        self.assertEqual(response.status_code,200,response.text)
        update.assert_called_once()

    def test_admin_listing_filters_and_safe_profiles(self):
        response = self.client.get('/admin/brokers?status=approved', headers=self.admin_headers())
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(len(response.json()['brokers']),2)
        self.assertNotIn('auth_user_id',response.text)


if __name__ == '__main__': unittest.main()
