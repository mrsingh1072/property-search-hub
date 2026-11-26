/* Only completed account-linked transactions are displayed here. */
(()=>{
 const get=id=>document.getElementById(id),records=get('records');
 const login=()=>location.replace('/login?next=%2Fmy-properties');
 function text(parent,tag,value,className){const el=document.createElement(tag);el.textContent=value;if(className)el.className=className;parent.appendChild(el);return el;}
 function card(record){
  const snapshot=record.property_snapshot||{},card=document.createElement('article');card.className='home-card';
  const image=document.createElement('div');image.className='home-image';image.textContent='⌂';
  const first=(snapshot.images||[])[0],url=typeof first==='string'?first:first?.url;
  if(url){try{const parsed=new URL(url,location.origin);if(['https:','http:'].includes(parsed.protocol)){const img=document.createElement('img');img.src=parsed.href;img.alt='Property in '+(snapshot.area_name||'Patna');img.loading='lazy';img.onerror=()=>{image.textContent='⌂';};image.replaceChildren(img);}}catch(error){}}
  card.appendChild(image);const body=document.createElement('div');body.className='home-body';card.appendChild(body);
  text(body,'span',record.transaction_type==='purchase'?'Purchased':'Rented','home-badge');
  text(body,'h2',[(snapshot.bhk?snapshot.bhk+' BHK':''),snapshot.property_type||'Home'].filter(Boolean).join(' '));
  text(body,'p',snapshot.address||[snapshot.area_name,snapshot.city||'Patna'].filter(Boolean).join(', '));
  const date=new Date(record.completed_on+'T12:00:00');
  text(body,'p','Completed '+(Number.isNaN(date.getTime())?record.completed_on:date.toLocaleDateString('en-IN',{day:'numeric',month:'long',year:'numeric'})),'record-date');
  return card;
 }
 async function load(){
  const token=localStorage.getItem('riya_token');if(!token){login();return;}
  get('properties-loading').hidden=false;get('properties-empty').hidden=true;get('properties-error').hidden=true;get('record-note').hidden=true;records.replaceChildren();
  try{
   const response=await fetch('/me/properties',{headers:{Authorization:'Bearer '+token},cache:'no-store'});
   if(response.status===401){login();return;}
   const data=await response.json();
   if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Could not load your properties. Please try again.');
   if(localStorage.getItem('riya_token')!==token){login();return;}
   const rows=data.properties||[];
   get('properties-empty').hidden=rows.length>0;
   rows.forEach(row=>records.appendChild(card(row)));get('record-note').hidden=!rows.length;
  }catch(error){get('properties-error-message').textContent=error.message;get('properties-error').hidden=false;}
  finally{get('properties-loading').hidden=true;}
 }
 get('properties-retry').onclick=load;
 window.addEventListener('storage',event=>{if(event.key==='riya_token'||event.key===null)load();});
 window.addEventListener('pageshow',event=>{if(event.persisted)load();});
 load();
})();
