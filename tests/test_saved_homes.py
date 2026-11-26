import shutil,subprocess,unittest
from unittest.mock import patch
from pathlib import Path
import test_verified_brokers as fixture
from agent.property_agent import _handle_save_favourite
from types import SimpleNamespace

class SavedHomesTests(unittest.TestCase):
 setUp=fixture.VerifiedBrokerTests.setUp
 token=fixture.VerifiedBrokerTests.token
 headers=fixture.VerifiedBrokerTests.headers
 admin_headers=fixture.VerifiedBrokerTests.admin_headers
 get_user=fixture.VerifiedBrokerTests.get_user
 def test_saved_is_its_own_page_without_chat_overlay(self):
  response=self.client.get('/saved')
  self.assertEqual(response.status_code,200)
  self.assertIn('Saved homes',response.text)
  self.assertIn('saved-toolbar',response.text)
  self.assertIn('A place for your next home',response.text)
  self.assertNotIn('id="feed"',response.text)
  legacy=self.client.get('/chat?view=saved',follow_redirects=False)
  self.assertEqual(legacy.status_code,303);self.assertEqual(legacy.headers['location'],'/saved')
  for url in ('/static/saved.js','/static/saved-store.js'):
   self.assertEqual(self.client.get(url).status_code,200)
  chat=Path('api/templates/chat.html').read_text(encoding='utf-8')
  self.assertNotIn('id="sl-panel"',chat)
  self.assertIn("function openShortlist(){location.assign('/saved');}",chat)
 def test_saved_cards_use_current_account_order_and_live_availability(self):
  for row in self.db.rows['properties']:row['city']='Patna'
  self.db.rows['properties'][0]['status']='available';self.db.rows['properties'][1]['status']='sold'
  customer={'id':'customer-a','email':'buyer@example.invalid','favourites':['properties-b','properties-a']}
  with patch('api.main._current_customer',return_value=customer):
   response=self.client.get('/me/favourites?customer_id=another-user')
  self.assertEqual(response.status_code,200,response.text)
  homes=response.json()['properties']
  self.assertEqual([p['id'] for p in homes],['properties-a','properties-b'])
  self.assertEqual([p['status'] for p in homes],['available','sold'])
 def test_removing_favourite_only_changes_current_customer(self):
  customer={'id':'customer-a','email':'a@example.invalid','favourites':['home-a','home-b']}
  with patch('api.main._current_customer',return_value=customer),patch('api.auth.set_customer_favourites') as save:
   response=self.client.request('DELETE','/me/favourites',json={'property_id':'home-a','customer_id':'customer-b'})
  self.assertEqual(response.status_code,200)
  save.assert_called_once_with('customer-a',['home-b'])
 def test_saved_data_requires_customer_session(self):
  for headers in ({},self.headers(),self.admin_headers()):
   self.assertEqual(self.client.get('/me/favourites',headers=headers).status_code,401)
 def test_chat_save_persists_only_verified_customer_identity(self):
  conv=SimpleNamespace(requirements={'_last_shown_cards':[{'id':'home-a','area':'Patna'}]},authenticated_customer_id='customer-a')
  with patch('api.auth.set_customer_favourites') as save:
   reply=_handle_save_favourite(conv,'save first one','Buyer')
  save.assert_called_once_with('customer-a',['home-a']);self.assertIn('Saved',reply)
 def test_chat_save_failure_does_not_falsely_claim_success(self):
  conv=SimpleNamespace(requirements={'_last_shown_cards':[{'id':'home-a'}]},authenticated_customer_id='customer-a')
  with patch('api.auth.set_customer_favourites',side_effect=RuntimeError('DB unavailable')):
   reply=_handle_save_favourite(conv,'save first one','Buyer')
  self.assertIn("couldn't save",reply);self.assertNotIn('_shortlist',conv.requirements)
 def test_stored_profile_id_alone_cannot_write_an_account_favourite(self):
  conv=SimpleNamespace(requirements={'_profile':{'customer_id':'someone-else'},'_last_shown_cards':[{'id':'home-a'}]})
  with patch('api.auth.set_customer_favourites') as save:
   _handle_save_favourite(conv,'save first one','Guest')
  save.assert_not_called()
 @unittest.skipUnless(shutil.which('node'),'Node required for saved store checks')
 def test_store_keeps_guest_and_customer_saves_separate_and_checks_errors(self):
  js=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('api/static/saved_store.js','utf8');
const values=new Map([['riya_token','customer-token'],['apnaghar_patna_saved:guest','["guest-one"]'],['apnaghar_patna_sid:guest','guest-session'],['apnaghar_patna_saved','["old-account-home"]']]);
const localStorage={getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)};
const events=[],calls=[];let fail=false;
const window={dispatchEvent:event=>events.push(event)},context={window,localStorage,Date,Math,crypto:{randomUUID:()=> 'new-session'},CustomEvent:class{constructor(name,options){this.type=name;this.detail=options.detail;}},
fetch:async(url,options)=>{calls.push({url,options});if(fail)return{ok:false,status:503,json:async()=>({detail:'Try later'})};return{ok:true,status:200,json:async()=>url.startsWith('/shortlist/')?{properties:[{id:'guest-two'}]}:{properties:[{id:'own-home'}]}};}};
vm.runInNewContext(source,context);const store=window.ApnaGharSaved;
(async()=>{
 const data=await store.list();assert.equal(data.token,'customer-token');assert.equal(calls[0].url,'/me/favourites');assert.equal(calls[0].options.headers.Authorization,'Bearer customer-token');
 await store.mergeGuest('customer-token');const posts=calls.filter(c=>c.options.method==='POST');assert.equal(posts.length,2);assert.deepEqual(posts.map(c=>JSON.parse(c.options.body).property_id).sort(),['guest-one','guest-two']);assert.equal(values.has('apnaghar_patna_saved:guest'),false);assert.equal(values.has('apnaghar_patna_sid:guest'),false);
 await assert.rejects(store.set('home',true,'wrong-account'));
 values.delete('riya_token');calls.length=0;await store.set('new-guest-home',true);assert.equal(calls[0].url,'/shortlist');assert.equal(calls[0].options.headers.Authorization,undefined);assert.equal(JSON.parse(calls[0].options.body).session_id,'web_patna_new-session');
 fail=true;await assert.rejects(store.set('failed-home',true));assert.equal(JSON.parse(values.get('apnaghar_patna_saved:guest')).includes('failed-home'),false);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
  result=subprocess.run([shutil.which('node')],input=js,text=True,encoding='utf-8',capture_output=True)
  self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
