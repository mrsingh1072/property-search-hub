(()=>{
 const guestKey='apnaghar_patna_saved:guest',sidKey='apnaghar_patna_sid:guest';
 const token=()=>localStorage.getItem('riya_token')||'';
 function guestIds(){try{const value=JSON.parse(localStorage.getItem(guestKey)||'[]');return Array.isArray(value)?value.filter(id=>typeof id==='string'):[];}catch(error){return [];}}
 async function request(url,options={}){const response=await fetch(url,{cache:'no-store',...options});let data={};try{data=await response.json();}catch(error){}if(!response.ok){const error=new Error(typeof data.detail==='string'?data.detail:'Could not update saved homes. Please try again.');error.status=response.status;throw error;}return data;}
 async function list(){const session=token();if(session){const data=await request('/me/favourites',{headers:{Authorization:'Bearer '+session}});return{...data,token:session};}const sid=localStorage.getItem(sidKey);if(!sid)return{properties:[],token:''};const data=await request('/shortlist/'+encodeURIComponent(sid));return{...data,token:''};}
 async function set(id,saved,expectedToken=token()){
  if(expectedToken!==token())throw new Error('Your account changed. Refresh and try again.');
  const session=expectedToken;let body={property_id:id},url='/me/favourites';
  const headers={'Content-Type':'application/json'};
  if(session)headers.Authorization='Bearer '+session;
  else{let sid=localStorage.getItem(sidKey);if(!sid){sid='web_patna_'+crypto.randomUUID();localStorage.setItem(sidKey,sid);}body.session_id=sid;url='/shortlist';}
  await request(url,{method:saved?'POST':'DELETE',headers,body:JSON.stringify(body)});
  if(!session){const ids=new Set(guestIds());saved?ids.add(id):ids.delete(id);localStorage.setItem(guestKey,JSON.stringify([...ids]));}
  localStorage.setItem('apnaghar_saved_updated',Date.now()+':'+Math.random());
  window.dispatchEvent(new CustomEvent('apnaghar:savedchange',{detail:{id,saved}}));
 }
 async function mergeGuest(session){
  const ids=new Set(guestIds()),sid=localStorage.getItem(sidKey);
  if(sid){const data=await request('/shortlist/'+encodeURIComponent(sid));(data.properties||[]).forEach(p=>ids.add(p.id));}
  for(const id of ids)await set(id,true,session);
  localStorage.removeItem(guestKey);localStorage.removeItem(sidKey);
 }
 window.ApnaGharSaved={list,set,guestIds,mergeGuest};
})();
