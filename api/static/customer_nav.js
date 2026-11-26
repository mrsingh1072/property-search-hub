/* Preserve the buyer account context on Browse without changing public access. */
(()=>{
  const get=id=>document.getElementById(id);
  const account=get('customer-account'),saved=get('customer-saved'),properties=get('customer-properties');
  const login=get('customer-login'),broker=get('guest-broker'),status=get('customer-status');
  const retry=get('customer-retry'),home=get('customer-home');
  const destination=location.pathname+location.search;
  login.href='/login?next='+encodeURIComponent(destination);
  function hideAccount(){account.hidden=true;saved.hidden=true;properties.hidden=true;account.open=false;get('customer-name').textContent='';get('customer-email').textContent='';}
  function guest(){hideAccount();login.hidden=false;broker.hidden=false;status.hidden=true;home.href='/';saved.hidden=location.pathname!=='/saved';}
  async function refresh(){
    const token=localStorage.getItem('riya_token')||'';
    if(!token){guest();return;}
    hideAccount();login.hidden=true;broker.hidden=true;status.hidden=false;retry.hidden=true;
    status.firstChild.textContent='Loading account… ';
    try{
      const response=await fetch('/me',{headers:{Authorization:'Bearer '+token},cache:'no-store'});
      if((localStorage.getItem('riya_token')||'')!==token){return refresh();}
      if(response.status===401){localStorage.removeItem('riya_token');guest();return;}
      if(!response.ok)throw new Error('Account unavailable');
      const customer=await response.json();
      if((localStorage.getItem('riya_token')||'')!==token){return refresh();}
      get('customer-name').textContent=(customer.name||customer.email||'My account').trim().split(/\s+/)[0];
      get('customer-email').textContent=customer.email||'';
      account.hidden=false;saved.hidden=false;properties.hidden=false;status.hidden=true;home.href='/chat';
    }catch(error){status.firstChild.textContent='Account unavailable. ';retry.hidden=false;}
  }
  get('customer-logout').onclick=()=>{localStorage.removeItem('riya_token');hideAccount();location.assign(login.href);};
  retry.onclick=refresh;
  window.addEventListener('storage',event=>{if(event.key==='riya_token'||event.key===null)refresh();});
  window.addEventListener('pageshow',event=>{if(event.persisted)refresh();});
  refresh();
})();
