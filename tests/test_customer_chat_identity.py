import copy
import re
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app
from agent.property_agent import process_message

class CustomerChatIdentityTests(unittest.TestCase):
    def customer(self,name='Prajwal'):
        return {'id':'customer-p','name':name,'email':'buyer@example.invalid'}
    def test_signed_in_greeting_replaces_previous_browser_profile(self):
        previous={'messages':[{'role':'user','content':'old private message'}],
            'requirements':{'_profile':{'name':'Saurabh','phone':'9999999999','onboarding_step':'complete'},'_shortlist':['old-property']}}
        original=copy.deepcopy(previous)
        with patch('agent.conversation_manager.get_session',return_value=previous),patch('agent.conversation_manager.save_session') as save:
            response=process_message('test-chat','__init__',customer_profile=self.customer())
        self.assertIn('Welcome back, Prajwal!',response['reply'])
        self.assertNotIn('Saurabh',response['reply'])
        saved=save.call_args.kwargs
        self.assertEqual(saved['requirements']['_profile']['customer_id'],'customer-p')
        self.assertNotIn('phone',saved['requirements']['_profile'])
        self.assertNotIn('_shortlist',saved['requirements'])
        self.assertEqual(saved['messages'],[])
        self.assertEqual(original['requirements']['_profile']['name'],'Saurabh')
    def test_nameless_account_does_not_borrow_previous_name(self):
        with patch('agent.conversation_manager.get_session',return_value={'requirements':{'_profile':{'name':'Saurabh','onboarding_step':'complete'}}}),patch('agent.conversation_manager.save_session'):
            response=process_message('test-chat','__init__',customer_profile=self.customer(None))
        self.assertNotIn('Saurabh',response['reply'])
        self.assertIn('Hello!',response['reply'])
    def test_same_customer_keeps_their_own_contact_and_shortlist(self):
        state={'requirements':{'_profile':{'customer_id':'customer-p','name':'Old name','phone':'9000000000','onboarding_step':'complete'},'_shortlist':['own-property']}}
        with patch('agent.conversation_manager.get_session',return_value=state),patch('agent.conversation_manager.save_session') as save:
            response=process_message('test-chat','__init__',customer_profile=self.customer())
        self.assertIn('Prajwal',response['reply'])
        self.assertEqual(save.call_args.kwargs['requirements']['_shortlist'],['own-property'])
        self.assertEqual(save.call_args.kwargs['requirements']['_profile']['phone'],'9000000000')
    def test_property_deeplink_greets_current_account(self):
        with patch('agent.conversation_manager.get_session',return_value={}),patch('agent.conversation_manager.save_session'):
            response=process_message('test-chat','__init_prop__:prop-1:2 BHK in Patna',customer_profile=self.customer())
        self.assertIn('Hi Prajwal!',response['reply'])
    def test_guest_onboarding_still_asks_for_name(self):
        with patch('agent.conversation_manager.get_session',return_value={}),patch('agent.conversation_manager.save_session'):
            response=process_message('test-guest','__init__')
        self.assertIn('what should I call you?',response['reply'])
    def test_chat_uses_verified_account_not_request_body_name(self):
        client=TestClient(app);self.addCleanup(client.close)
        with patch('scripts.check_config.configuration_status',return_value={'required':{'database':True,'ai_provider':True}}),patch('api.main._current_customer',return_value=self.customer()),patch('api.main.process_message',return_value={'reply':'Hello','properties':[]}) as agent,patch('api.main.get_session',return_value={}):
            response=client.post('/chat',headers={'Authorization':'Bearer user-session'},json={'session_id':'test-chat','message':'__init__','customer_profile':{'name':'Saurabh'}})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(agent.call_args.kwargs['customer_profile'],self.customer())
    def test_invalid_account_session_does_not_use_old_chat_identity(self):
        client=TestClient(app);self.addCleanup(client.close)
        with patch('scripts.check_config.configuration_status',return_value={'required':{'database':True,'ai_provider':True}}),patch('api.main._current_customer',return_value=None),patch('api.main.process_message') as agent:
            response=client.post('/chat',headers={'Authorization':'Bearer expired-session'},json={'session_id':'test-chat','message':'__init__'})
        self.assertEqual(response.status_code,401);agent.assert_not_called()
    @unittest.skipUnless(shutil.which('node'),'Node required for browser session regression')
    def test_browser_waits_for_auth_and_separates_accounts_and_guest(self):
        source=Path('api/templates/chat.html').read_text(encoding='utf-8')
        select=source[source.index('function selectChatSession(){'):source.index('\n\nconst feed')]
        start=source.index("window.addEventListener('load', async () => {")
        end=source.index('\n});',start)+4
        bootstrap=source[start:end]
        harness=r'''
const assert=require('assert');
let SID=null,CUST=null,boot;
const store=new Map([['apnaghar_patna_sid','old-shared-session']]);
const localStorage={getItem:key=>store.get(key)||null,setItem:(key,value)=>store.set(key,value)};
let sequence=0;
const crypto={randomUUID:()=>String(++sequence)};
const window={addEventListener:(event,fn)=>{boot=fn;}};
const sendBtn={disabled:false},location={search:''};
const calls=[];
async function refreshAuthUI(){await Promise.resolve();CUST={id:'prajwal',name:'Prajwal'};calls.push('auth');}
function initGoogle(){}
async function openMine(){calls.push('mine');}
async function openShortlist(){calls.push('saved');}
async function sendSilent(message){assert.equal(CUST.name,'Prajwal');assert.notEqual(SID,'old-shared-session');calls.push('greeting');}
'''+select+'\n'+bootstrap+r'''
(async()=>{
 await boot();assert.deepEqual(calls,['auth','greeting']);assert.equal(sendBtn.disabled,false);
 const prajwal=SID;
 CUST={id:'saurabh'};selectChatSession();const saurabh=SID;assert.notEqual(prajwal,saurabh);
 CUST=null;selectChatSession();assert.notEqual(SID,prajwal);assert.notEqual(SID,saurabh);
 CUST={id:'prajwal'};selectChatSession();assert.equal(SID,prajwal);
 calls.length=0;location.search='?view=mine';await boot();assert.deepEqual(calls,['auth','greeting','mine']);
 calls.length=0;location.search='?view=saved';await boot();assert.deepEqual(calls,['auth','greeting','saved']);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        result=subprocess.run([shutil.which('node')],input=harness,text=True,encoding='utf-8',capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
