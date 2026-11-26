(()=>{
 const get=id=>document.getElementById(id),store=window.ApnaGharSaved;
 const grid=get('saved-grid'),search=get('saved-search'),availability=get('saved-availability'),sort=get('saved-sort');
 let homes=[],activeToken='',version=0,toastTimer;
 const currentToken=()=>localStorage.getItem('riya_token')||'';
 const login=()=>location.assign('/login?next=%2Fsaved');
 const heart='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/></svg>';
 const house='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="m3 10 9-7 9 7M5 9v12h14V9M9 21v-7h6v7"/></svg>';
 function text(parent,tag,value,className){const element=document.createElement(tag);element.textContent=value;if(className)element.className=className;parent.appendChild(element);return element;}
 function toast(message,undo){clearTimeout(toastTimer);get('saved-toast-message').textContent=message;get('saved-toast').hidden=false;const button=get('saved-undo');button.hidden=!undo;button.disabled=false;button.onclick=undo||null;toastTimer=setTimeout(()=>{get('saved-toast').hidden=true;},7000);}
 function stats(){get('stat-saved').textContent=homes.length;get('stat-available').textContent=homes.filter(home=>home.status==='available').length;get('stat-areas').textContent=new Set(homes.map(home=>(home.area||'').trim().toLowerCase()).filter(Boolean)).size;}
 function card(home){
  const article=document.createElement('article');article.className='saved-card';
  const image=document.createElement('div');image.className='card-image';image.innerHTML=house;
  const raw=(home.images||[])[0],url=typeof raw==='string'?raw:raw?.url;
  if(url){try{const parsed=new URL(url,location.origin);if(['http:','https:'].includes(parsed.protocol)){const img=document.createElement('img');img.src=parsed.href;img.alt=[home.property_type||'Home',home.area].filter(Boolean).join(' in ');img.loading='lazy';img.onerror=()=>{img.remove();};image.appendChild(img);}}catch(error){}}
  const status=home.status||'unavailable',labels={available:'Available',booked:'Booked',sold:'Sold',rented:'Rented',unavailable:'Unavailable'};
  text(image,'span',labels[status]||'Unavailable','availability'+(status==='available'?'':' unavailable'));
  const remove=document.createElement('button');remove.type='button';remove.className='remove-saved';remove.innerHTML=heart;remove.title='Remove from Saved';remove.setAttribute('aria-label','Remove '+(home.property_type||'home')+' in '+(home.area||'Patna')+' from Saved');remove.onclick=()=>removeHome(home,remove);image.appendChild(remove);article.appendChild(image);
  const body=document.createElement('div');body.className='card-content';article.appendChild(body);
  text(body,'p',(home.price_str||'Price on request').replace(/^Rs\.?\s*/,'₹'),'home-price');
  text(body,'h2',[home.bhk?home.bhk+' BHK':'',home.property_type||'Home'].filter(Boolean).join(' '));
  text(body,'p',[home.area,home.city||'Patna'].filter(Boolean).join(', '),'home-area');
  const specs=document.createElement('div');specs.className='home-specs';if(home.sqft)text(specs,'span',Number(home.sqft).toLocaleString('en-IN')+' sq ft');if(home.furnishing)text(specs,'span',home.furnishing);body.appendChild(specs);
  const link=text(body,'a',status==='available'?'Ask about this home →':'Explore other homes →',status==='available'?'primary-link':'secondary-link');
  const params=new URLSearchParams({prop:home.id,area:home.area||'',bhk:home.bhk||'',price:home.price_str||''});
  link.href=status==='available'?'/chat?'+params.toString():'/properties/browse';
  return article;
 }
 function render(){
  stats();grid.replaceChildren();get('saved-empty').hidden=homes.length>0;get('saved-toolbar').hidden=!homes.length;get('saved-summary').hidden=!homes.length;
  const query=search.value.trim().toLowerCase();let visible=homes.filter(home=>(availability.value!=='available'||home.status==='available')&&[home.area,home.city,home.property_type,home.furnishing,home.bhk?home.bhk+' bhk':''].join(' ').toLowerCase().includes(query));
  if(sort.value!=='recent')visible=visible.slice().sort((a,b)=>{const pa=Number(a.price_inr),pb=Number(b.price_inr);if(!(pa>0))return pb>0?1:0;if(!(pb>0))return-1;return sort.value==='low'?pa-pb:pb-pa;});
  visible.forEach(home=>grid.appendChild(card(home)));get('saved-no-results').hidden=!homes.length||visible.length>0;
  get('saved-summary').textContent=visible.length===homes.length?homes.length+' saved '+(homes.length===1?'home':'homes'):visible.length+' of '+homes.length+' saved homes';
 }
 async function removeHome(home,button){
  if(activeToken!==currentToken()){await load();return;}
  const session=activeToken;button.disabled=true;
  try{await store.set(home.id,false,session);if(session!==currentToken()){await load();return;}const originalIndex=homes.findIndex(item=>item.id===home.id);homes=homes.filter(item=>item.id!==home.id);render();
   toast('Home removed from Saved.',async()=>{get('saved-undo').disabled=true;try{await store.set(home.id,true,session);if(session!==currentToken()){await load();return;}if(!homes.some(item=>item.id===home.id))homes.splice(Math.max(0,originalIndex),0,home);render();toast('Home restored to Saved.');}catch(error){toast(error.message);}});
  }catch(error){if(error.status===401){login();return;}toast(error.message);button.disabled=false;}
 }
 async function load(){
  const request=++version;homes=[];grid.replaceChildren();['saved-empty','saved-toolbar','saved-summary','saved-no-results','saved-error','saved-toast'].forEach(id=>get(id).hidden=true);get('saved-loading').hidden=false;
  ['stat-saved','stat-available','stat-areas'].forEach(id=>get(id).textContent='—');
  try{const data=await store.list();if(request!==version)return;if(data.token!==currentToken()){await load();return;}activeToken=data.token;homes=data.properties||[];get('guest-notice').hidden=!!activeToken;render();}
  catch(error){if(request!==version)return;if(error.status===401){login();return;}get('saved-error-message').textContent=error.message;get('saved-error').hidden=false;}
  finally{if(request===version)get('saved-loading').hidden=true;}
 }
 search.addEventListener('input',render);availability.addEventListener('change',render);sort.addEventListener('change',render);
 get('saved-reset').onclick=()=>{search.value='';availability.value='all';sort.value='recent';render();};get('saved-retry').onclick=load;
 window.addEventListener('storage',event=>{if(event.key==='riya_token'||event.key==='apnaghar_saved_updated'||event.key===null)load();});window.addEventListener('pageshow',event=>{if(event.persisted)load();});
 load();
})();
