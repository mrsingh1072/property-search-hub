import shutil,subprocess,unittest

class CustomerPropertyPageTests(unittest.TestCase):
 @unittest.skipUnless(shutil.which('node'),'Node required for page interaction checks')
 def test_private_page_empty_records_errors_and_sign_in(self):
  script=r'''
const vm=require('vm'),fs=require('fs'),assert=require('assert');
const source=fs.readFileSync('api/static/my_properties.js','utf8');
function node(tag='div'){
 const value={tagName:tag,hidden:false,className:'',textContent:'',children:[],appendChild(child){this.children.push(child);return child;},replaceChildren(...children){this.children=children;}};
 Object.defineProperty(value,'innerHTML',{set(){throw new Error('Unsafe HTML rendering');}});return value;
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function setup(token,status=200,rows=[]){
 const elements=new Map(),events={};let current=token,redirect='',calls=0,code=status;
 const document={getElementById:id=>{if(!elements.has(id))elements.set(id,node());return elements.get(id);},createElement:node};
 vm.runInNewContext(source,{document,localStorage:{getItem:()=>current},location:{origin:'http://localhost:8000',replace:url=>redirect=url},URL,Date,window:{addEventListener:(event,fn)=>events[event]=fn},
 fetch:async(url,options)=>{assert.equal(url,'/me/properties');assert.equal(options.headers.Authorization,'Bearer '+current);calls++;return{status:code,ok:code===200,json:async()=>code===200?{properties:rows}:{detail:'Service temporarily unavailable'}};}});
 return{elements,events,calls:()=>calls,redirect:()=>redirect,status:value=>code=value};
}
function text(element){return element.textContent+element.children.map(text).join(' ');}
(async()=>{
 let env=setup(null);await flush();assert.equal(env.redirect(),'/login?next=%2Fmy-properties');assert.equal(env.calls(),0);
 env=setup('customer');await flush();assert.equal(env.elements.get('properties-empty').hidden,false);assert.equal(env.elements.get('records').children.length,0);
 env=setup('customer',200,[{transaction_type:'purchase',completed_on:'2020-01-02',property_snapshot:{property_type:'Flat',area_name:'<script>test</script>',city:'Patna'}},{transaction_type:'rent',completed_on:'2020-02-03',property_snapshot:{property_type:'House',city:'Patna'}}]);await flush();
 assert.equal(env.elements.get('properties-empty').hidden,true);assert.equal(env.elements.get('records').children.length,2);
 const contents=text(env.elements.get('records'));assert(contents.includes('Purchased'));assert(contents.includes('Rented'));assert(contents.includes('<script>test</script>'));
 env=setup('customer',503);await flush();assert.equal(env.elements.get('properties-empty').hidden,true);assert.equal(env.elements.get('properties-error').hidden,false);
 env.status(200);env.elements.get('properties-retry').onclick();await flush();assert.equal(env.elements.get('properties-error').hidden,true);assert.equal(env.elements.get('properties-empty').hidden,false);
 env=setup('expired',401);await flush();assert.equal(env.redirect(),'/login?next=%2Fmy-properties');assert.equal(env.elements.get('records').children.length,0);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
  result=subprocess.run([shutil.which('node')],input=script,text=True,encoding='utf-8',capture_output=True)
  self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
