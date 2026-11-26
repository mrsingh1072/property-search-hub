import re
import shutil
import subprocess
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from api.main import app

class BrowseAccountNavigationTests(unittest.TestCase):
    def test_navigation_assets_and_account_destinations(self):
        client=TestClient(app);self.addCleanup(client.close)
        response=client.get('/properties/browse')
        self.assertEqual(response.status_code,200)
        self.assertIn('src="/static/customer-nav.js"',response.text)
        self.assertIn('/saved',response.text)
        self.assertIn('/my-properties',response.text)
        response=client.get('/static/customer-nav.js')
        self.assertEqual(response.status_code,200)
        self.assertIn('javascript',response.headers['content-type'])
    @unittest.skipUnless(shutil.which('node'),'Node required for browser navigation regression')
    def test_guest_signed_in_expired_retry_logout_and_account_switch(self):
        source=Path('api/static/customer_nav.js').read_text(encoding='utf-8')
        harness=r'''
const vm=require('vm'),assert=require('assert'),fs=require('fs');
const source=fs.readFileSync('api/static/customer_nav.js','utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function setup(token,code=200){
 const elements=new Map();
 const document={getElementById:id=>{if(!elements.has(id))elements.set(id,{hidden:false,textContent:'',firstChild:{textContent:''},open:false,href:''});return elements.get(id);}};
 const store=new Map([['btok','independent-broker-token'],['apnaghar_patna_sid:customer-1','own-chat-session']]);if(token)store.set('riya_token',token);
 const storage={getItem:key=>store.get(key)||null,setItem:(key,value)=>store.set(key,value),removeItem:key=>store.delete(key)};
 const events={},requests=[];
 let status=code,redirect='';
 const context={document,localStorage:storage,location:{pathname:'/properties/browse',search:'?area=Danapur',assign:url=>{redirect=url;}},window:{addEventListener:(event,fn)=>events[event]=fn},encodeURIComponent,
 fetch:async(url,options)=>{requests.push({url,options});const name=options.headers.Authorization==='Bearer second-user'?'Anjali':'Prajwal';return{status,ok:status===200,json:async()=>({name,email:name.toLowerCase()+'@example.com'})};}};
 vm.runInNewContext(source,context);
 return {elements,store,events,requests,setStatus:value=>status=value,redirect:()=>redirect};
}
(async()=>{
 let env=setup('signed-in-user');await flush();
 const el=id=>env.elements.get(id);
 assert.equal(el('customer-name').textContent,'Prajwal');assert.equal(el('customer-account').hidden,false);
 assert.equal(el('customer-saved').hidden,false);assert.equal(el('customer-properties').hidden,false);
 assert.equal(el('guest-broker').hidden,true);assert.equal(el('customer-login').hidden,true);
 assert.equal(env.store.get('riya_token'),'signed-in-user');assert.equal(env.requests[0].url,'/me');
 assert.equal(env.requests[0].options.headers.Authorization,'Bearer signed-in-user');
 assert.equal(el('customer-home').href,'/chat');
 env.store.set('riya_token','second-user');env.events.storage({key:'riya_token'});await flush();
 assert.equal(el('customer-name').textContent,'Anjali');
 el('customer-logout').onclick();assert.equal(env.store.has('riya_token'),false);
 assert.equal(env.store.get('btok'),'independent-broker-token');assert.equal(env.store.get('apnaghar_patna_sid:customer-1'),'own-chat-session');
 assert.equal(env.redirect(),'/login?next=%2Fproperties%2Fbrowse%3Farea%3DDanapur');
 env=setup('expired-user',401);await flush();assert.equal(env.store.has('riya_token'),false);
 assert.equal(env.elements.get('customer-account').hidden,true);assert.equal(env.elements.get('customer-login').hidden,false);
 env=setup(null);await flush();assert.equal(env.requests.length,0);assert.equal(env.elements.get('guest-broker').hidden,false);
 env=setup('valid-user',503);await flush();assert.equal(env.store.get('riya_token'),'valid-user');
 assert.equal(env.elements.get('customer-retry').hidden,false);assert.equal(env.elements.get('guest-broker').hidden,true);
 env.setStatus(200);env.elements.get('customer-retry').onclick();await flush();assert.equal(env.elements.get('customer-account').hidden,false);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        result=subprocess.run([shutil.which('node')],input=harness,text=True,encoding='utf-8',capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
    @unittest.skipUnless(shutil.which('node'),'Node required for JavaScript syntax checks')
    def test_changed_templates_have_valid_javascript(self):
        for filename in ('browse.html','chat.html'):
            source=Path('api/templates',filename).read_text(encoding='utf-8')
            for block in re.findall(r'<script[^>]*>(.*?)</script>',source,re.S):
                result=subprocess.run([shutil.which('node'),'--check'],input=block,text=True,encoding='utf-8',capture_output=True)
                self.assertEqual(result.returncode,0,filename+result.stderr)

if __name__=='__main__':unittest.main()
