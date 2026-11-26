/* Shared buyer/broker email-code interaction. No code or token is logged. */
(()=>{
  const broker=location.pathname.startsWith('/broker/');
  const prefix=broker?'/broker/otp':'/auth/otp';
  const email=document.getElementById('email'),code=document.getElementById('otp');
  const go=document.getElementById('go'),msg=document.getElementById('msg');
  const row=document.getElementById('otp-row'),actions=document.getElementById('code-actions');
  const resend=document.getElementById('resend'),change=document.getElementById('change-email');
  let sentEmail='',busy=false,remaining=0,timer;
  function message(text,error=false){msg.style.color=error?'#c0492f':'#0f7a52';msg.textContent=text;}
  function button(){go.innerHTML=sentEmail?'<i class="ph ph-sign-in"></i> Verify & sign in':'<i class="ph ph-paper-plane-tilt"></i> Send code';}
  function countdown(){clearInterval(timer);remaining=60;const tick=()=>{resend.disabled=busy||remaining>0;resend.textContent=remaining>0?'Resend in '+remaining+'s':'Resend code';};tick();timer=setInterval(()=>{remaining=Math.max(0,remaining-1);tick();if(!remaining)clearInterval(timer);},1000);}
  async function post(path,body){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify(body)});const data=await response.json();if(!response.ok||data.ok===false)throw new Error(typeof data.detail==='string'?data.detail:'Could not complete sign-in. Please try again.');return data;}
  async function send(){
    if(!email.reportValidity())return;
    const address=email.value.trim().toLowerCase();
    busy=true;go.disabled=true;resend.disabled=true;change.disabled=true;message('Sending code…');
    try{await post(prefix+'/request',{email:address});sentEmail=address;email.value=address;email.readOnly=true;row.style.display='';actions.hidden=false;code.value='';button();countdown();message('Code sent to '+address+'. It expires in 10 minutes. Check your spam folder too.');code.focus();}
    catch(error){message(error.message,true);}
    finally{busy=false;go.disabled=false;change.disabled=false;resend.disabled=remaining>0;}
  }
  window.loginAction=async function(){
    if(busy)return;
    if(!sentEmail){await send();return;}
    if(!/^[0-9]{6}$/.test(code.value.trim())){message('Enter the 6-digit code from your email.',true);code.focus();return;}
    busy=true;go.disabled=true;resend.disabled=true;change.disabled=true;message('Verifying…');
    try{const data=await post(prefix+'/verify',{email:sentEmail,code:code.value.trim()});
      if(broker){localStorage.setItem('btok',data.token);location.replace('/broker');}
      else{await window.onLoggedIn(data.token);}
    }catch(error){message(error.message,true);}
    finally{busy=false;go.disabled=false;change.disabled=false;resend.disabled=remaining>0;}
  };
  resend.onclick=()=>{if(!busy&&remaining===0)send();};
  change.onclick=()=>{if(busy)return;sentEmail='';email.readOnly=false;code.value='';row.style.display='none';actions.hidden=true;clearInterval(timer);remaining=0;button();message('Enter your email to receive a new code.');email.focus();};
  [email,code].forEach(field=>field.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();window.loginAction();}}));
})();
