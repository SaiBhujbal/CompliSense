/* CompliSense engine: matte scroll-reactive background, scroll animations,
   page transitions, advanced chart builders, ask modal. */

const PAGES = [
  ['index.html','Overview'],['watchtower.html','Watchtower'],['agents.html','Live'],['compliance.html','Compliance'],
  ['pestel.html','PESTEL'],['swot.html','SWOT'],['trends.html','Trends'],['competitors.html','Market'],['gapfinder.html','Gap Finder'],
];
const here = (location.pathname.split('/').pop() || 'index.html');
document.body.insertAdjacentHTML('afterbegin',
  `<div id="bgbase"></div><div id="aurora"></div><div id="grid"></div>
   <div class="curtain" id="curtain"><div class="ld">CompliSense</div></div>
   <nav><div class="wrap">
     <a class="brand" href="index.html" data-link><span class="dot"></span>CompliSense</a>
     <div class="nav-links">${PAGES.filter(p=>p[0]!=='index.html').map(p=>`<a href="${p[0]}" data-link class="${p[0]===here?'active':''}">${p[1]}</a>`).join('')}</div>
   </div></nav>`);
addEventListener('load',()=>setTimeout(()=>document.getElementById('curtain').classList.add('gone'),220));

/* ============ Company profile: onboard once, hydrate every tab ============ */
(function company(){
  const KEY='cs_company';
  const SECTORS=[
    {label:'Consumer electronics', gfKey:'boat'},
    {label:'Beauty & personal care', gfKey:'himalaya'},
    {label:'Consumer fintech / lending', gfKey:'kreditbee'},
    {label:'Packaged food / FMCG', gfKey:'yogabar'},
    {label:'B2B SaaS', gfKey:'zoho'},
    {label:'Other / not listed', gfKey:''},
  ];
  const get=()=>{try{return JSON.parse(localStorage.getItem(KEY)||'null')}catch(e){return null}};
  window.csCompany=get;
  window.csCompanyContext=()=>{const c=get();return c&&c.name
    ?`Company context — name: ${c.name}; sector: ${c.sector}; region: ${c.region||'India'}${c.competitor?'; main competitor: '+c.competitor:''}. Tailor the analysis to THIS company.`:'';};
  const css=`
  .csonb{position:fixed;inset:0;z-index:200;display:grid;place-items:center;padding:20px;
    background:rgba(5,7,11,.72);backdrop-filter:blur(8px);animation:csfade .35s ease}
  @keyframes csfade{from{opacity:0}to{opacity:1}}
  .csonbcard{width:min(460px,100%);background:var(--panel,#0c0f15);border:1px solid var(--stroke);border-radius:20px;
    padding:26px 26px 22px;box-shadow:0 40px 100px -30px rgba(0,0,0,.8);animation:csrise .4s cubic-bezier(.2,.8,.2,1)}
  @keyframes csrise{from{opacity:0;transform:translateY(18px) scale(.98)}to{opacity:1;transform:none}}
  .csonbh{font-family:'Space Grotesk';font-size:20px;font-weight:700;letter-spacing:-.01em}
  .csonbp{font-size:12.5px;color:var(--muted);line-height:1.55;margin:7px 0 16px}
  .csonbcard label{display:block;font-size:11px;font-family:'Space Grotesk';letter-spacing:.06em;text-transform:uppercase;color:var(--faint);margin:12px 0 5px}
  .csonbcard input,.csonbcard select{width:100%;background:rgba(255,255,255,.04);border:1px solid var(--stroke);border-radius:11px;
    padding:10px 12px;color:var(--text);font-size:13.5px;font-family:inherit;outline:none}
  .csonbcard input:focus,.csonbcard select:focus{border-color:var(--teal)}
  .csonbrow{display:flex;gap:10px;margin-top:20px}
  .csonbskip{background:transparent;border:1px solid var(--stroke);color:var(--muted);border-radius:11px;padding:10px 16px;cursor:pointer;font-family:'Space Grotesk';font-size:12.5px}
  .csonbgo{flex:1;background:var(--teal);color:#06231a;border:none;border-radius:11px;padding:10px 16px;cursor:pointer;font-weight:700;font-family:'Space Grotesk';font-size:13px}
  .cscochip{margin-left:14px;background:rgba(76,195,182,.12);border:1px solid var(--teal);color:var(--teal);
    border-radius:16px;padding:5px 11px;font-family:'Space Grotesk';font-size:11px;cursor:pointer;white-space:nowrap;transition:.18s}
  .cscochip:hover{background:rgba(76,195,182,.2)}
  @media(max-width:640px){.cscochip{display:none}}`;
  document.head.insertAdjacentHTML('beforeend',`<style>${css}</style>`);
  function chip(){
    const c=get();if(!c||!c.name)return;
    const nav=document.querySelector('nav .wrap');if(!nav||document.getElementById('cscochip'))return;
    nav.insertAdjacentHTML('beforeend',
      `<button id="cscochip" class="cscochip" title="Edit company profile">${c.name} · ${c.sector.split(' ')[0]} ✎</button>`);
    document.getElementById('cscochip').addEventListener('click',open);
  }
  function open(){
    if(document.getElementById('csonb'))return;
    const c=get()||{};
    document.body.insertAdjacentHTML('beforeend',`<div class="csonb" id="csonb"><div class="csonbcard">
      <div class="csonbh">Tell CompliSense about your business</div>
      <p class="csonbp">Every tab, the Gap Finder and the AI adapt to your company and sector. Change it anytime from the top bar.</p>
      <label>Company name</label><input id="onbn" value="${(c.name||'').replace(/"/g,'&quot;')}" placeholder="e.g. Acme Audio" />
      <label>Sector</label><select id="onbs">${SECTORS.map(s=>`<option value="${s.gfKey}" ${c.sector===s.label?'selected':''}>${s.label}</option>`).join('')}</select>
      <label>Main competitor (optional)</label><input id="onbc" value="${(c.competitor||'').replace(/"/g,'&quot;')}" placeholder="e.g. boAt" />
      <label>Region</label><input id="onbr" value="${(c.region||'India').replace(/"/g,'&quot;')}" />
      <div class="csonbrow"><button class="csonbskip" id="onbskip">Skip</button><button class="csonbgo" id="onbgo">Start →</button></div>
    </div></div>`);
    const close=()=>{const e=document.getElementById('csonb');if(e)e.remove()};
    document.getElementById('onbskip').addEventListener('click',()=>{
      if(!get())localStorage.setItem(KEY,JSON.stringify({name:'',sector:'Other / not listed',gfKey:''}));close();});
    document.getElementById('onbgo').addEventListener('click',()=>{
      const sel=document.getElementById('onbs');const label=sel.options[sel.selectedIndex].text;
      const rec={name:document.getElementById('onbn').value.trim(),sector:label,gfKey:sel.value,
        competitor:document.getElementById('onbc').value.trim(),region:(document.getElementById('onbr').value.trim()||'India')};
      localStorage.setItem(KEY,JSON.stringify(rec));close();location.reload();});
  }
  window.csEditCompany=open;
  if(!get())setTimeout(open,700); else chip();
})();

/* ============ "Add to Slack" — preview the Block Kit a post would send ============ */
(function slackModal(){
  const css=`
  .csslk{position:fixed;inset:0;z-index:210;display:grid;place-items:center;padding:20px;background:rgba(5,7,11,.72);backdrop-filter:blur(8px);animation:csfade .3s ease}
  .csslkcard{width:min(460px,100%);background:var(--panel,#0c0f15);border:1px solid var(--stroke);border-radius:18px;overflow:hidden;animation:csrise .35s cubic-bezier(.2,.8,.2,1)}
  .csslkhead{display:flex;align-items:center;gap:9px;padding:13px 16px;border-bottom:1px solid var(--stroke);font-family:'Space Grotesk';font-size:13px}
  .csslkhead .slklogo{color:#e01e5a;font-size:15px}
  .csslkx{margin-left:auto;cursor:pointer;color:var(--faint)}
  .slkmsg{margin:14px 16px;border-left:3px solid #4a154b;padding:10px 14px;background:rgba(255,255,255,.02);border-radius:0 8px 8px 0}
  .slk-h{font-family:'Space Grotesk';font-weight:700;font-size:15px;margin-bottom:6px}
  .slk-s{font-size:13px;color:var(--text);line-height:1.55;margin:6px 0}
  .slk-fields{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0;font-size:12px;color:var(--muted)}
  .slk-fields b{color:var(--text)}
  .slk-ctx{font-size:11px;color:var(--faint);margin-top:8px}
  .slk-act{margin-top:10px}
  .slk-act a{display:inline-block;background:#007a5a;color:#fff;font-size:12px;font-family:'Space Grotesk';border-radius:8px;padding:6px 12px;text-decoration:none}
  .csslknote{padding:0 16px 16px;font-size:11px;color:var(--faint);line-height:1.55}
  .csslknote code{background:rgba(255,255,255,.08);padding:1px 5px;border-radius:4px;font-size:10.5px}
  .slackbtn{background:rgba(97,31,105,.1);border:1px solid #611f69;color:#c9a3ce;font-family:'Space Grotesk';font-size:11.5px;
    border-radius:14px;padding:7px 13px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;transition:.2s;white-space:nowrap}
  .slackbtn:hover{background:rgba(97,31,105,.2);color:#e6d3ea}
  .cslock{display:inline-flex;align-items:center;gap:8px;font-family:'Space Grotesk';font-size:12px;color:var(--muted);
    border:1px solid var(--teal);background:rgba(76,195,182,.1);border-radius:16px;padding:6px 13px}
  .cslock b{color:var(--teal)} .cslock .ed{cursor:pointer;color:var(--faint);border-left:1px solid var(--stroke);padding-left:8px}
  .cslock .ed:hover{color:var(--text)}
  .csnavslk{margin-left:12px;background:#4a154b;border:1px solid #611f69;color:#fff;font-family:'Space Grotesk';font-size:11.5px;font-weight:500;
    border-radius:16px;padding:6px 13px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;transition:.18s}
  .csnavslk:hover{background:#611f69}
  .slkhubbody{padding:14px 16px 18px}
  .slkhubintro{font-size:12px;color:var(--muted);line-height:1.55;margin-bottom:14px}
  .slkhubintro code{background:rgba(255,255,255,.08);padding:1px 5px;border-radius:4px;font-size:10.5px}
  .slkopt{display:block;width:100%;text-align:left;background:rgba(255,255,255,.02);border:1px solid var(--stroke);border-radius:12px;
    padding:12px 14px;margin-bottom:9px;cursor:pointer;transition:.18s}
  .slkopt:hover{border-color:#611f69;background:rgba(97,31,105,.1)}
  .slkopt b{display:block;font-family:'Space Grotesk';font-size:13.5px;margin-bottom:3px}
  .slkopt span{font-size:11.5px;color:var(--muted);line-height:1.5}
  .slkopt.connect{border-color:#611f69;background:rgba(97,31,105,.12)}
  .slkhubsep{height:1px;background:var(--stroke);margin:14px 0}
  .csslkinput{width:100%;background:rgba(255,255,255,.04);border:1px solid var(--stroke);border-radius:11px;padding:10px 12px;color:var(--text);font-size:12.5px;font-family:inherit;outline:none}
  .csslkinput:focus{border-color:#611f69}
  .csslkmsg{font-size:11.5px;margin-top:8px;min-height:14px;color:var(--muted)}
  .csslksend{width:100%;margin:12px 16px 4px;width:calc(100% - 32px);background:#007a5a;color:#fff;border:none;border-radius:11px;padding:10px;cursor:pointer;font-family:'Space Grotesk';font-weight:600;font-size:13px}
  .csslksend:hover{background:#0a8f6c} .csslksend:disabled{opacity:.7;cursor:default}
  .csslksend.alt{background:#4a154b} .csslksend.alt:hover{background:#611f69}
  .csslkconn{font-size:12px;color:var(--sage);display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .csslkconn .ct{font-size:10.5px;color:var(--faint);font-family:'Space Grotesk'}
  .csslkconn .csdis{margin-left:auto;cursor:pointer;color:var(--faint);font-size:11px;border-bottom:1px dotted var(--faint)}
  .csslkconn .csdis:hover{color:var(--text)}
  .slksteps{margin:0 0 14px;padding-left:18px;font-size:12px;color:var(--muted);line-height:1.55}
  .slksteps li{margin-bottom:6px}
  .csnavslk.on{background:#007a5a;border-color:#0a8f6c}`;
  document.head.insertAdjacentHTML('beforeend',`<style>${css}</style>`);
  const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const md=s=>esc(s).replace(/\*(.+?)\*/g,'<b>$1</b>').replace(/\n/g,'<br>');
  function render(blocks){return (blocks||[]).map(b=>{
    if(b.type==='header')return `<div class="slk-h">${esc(b.text.text)}</div>`;
    if(b.type==='section')return b.fields?`<div class="slk-fields">${b.fields.map(f=>`<div>${md(f.text)}</div>`).join('')}</div>`:`<div class="slk-s">${md(b.text.text)}</div>`;
    if(b.type==='context')return `<div class="slk-ctx">${b.elements.map(e=>md(e.text)).join(' ')}</div>`;
    if(b.type==='actions')return `<div class="slk-act">${b.elements.map(e=>`<a href="${e.url||'#'}" target="_blank" rel="noopener">${esc(e.text.text)}</a>`).join('')}</div>`;
    return '';}).join('');}
  async function slackStatus(){try{return await(await fetch('/api/slack/status')).json();}catch(e){return {connected:false};}}
  function refreshNavSlack(st){
    const btn=document.getElementById('csnavslk');if(!btn)return;
    const on=!!(st&&(st.connected||st.ask_enabled));
    btn.classList.toggle('on',on);
    const bits=[];
    if(st&&st.connected)bits.push('alerts');
    if(st&&st.ask_enabled)bits.push(st.socket_running?'Ask AI · socket':'Ask AI');
    btn.title=on?('Slack · '+bits.join(' + ')):'Connect & send to Slack';
    btn.innerHTML=on?('▧ Slack · '+(bits[0]||'on')):'▧ Slack';
  }
  function openConnect(){
    if(document.getElementById('csslkc'))return;
    document.body.insertAdjacentHTML('beforeend',`<div class="csslk" id="csslkc"><div class="csslkcard" style="width:min(520px,100%)">
      <div class="csslkhead"><span class="slklogo">▧</span> Connect Slack<span class="csslkx" id="csslkcx">✕</span></div>
      <div class="slkhubbody">
        <p class="slkhubintro"><b>Outbound alerts</b> — Incoming Webhook (Watchtower / Gap / Compliance).</p>
        <ol class="slksteps">
          <li>Open <a href="https://api.slack.com/messaging/webhooks" target="_blank" rel="noopener" style="color:var(--teal)">Slack Incoming Webhooks ↗</a>, pick a channel, click <b>Add Incoming WebHooks Integration</b>.</li>
          <li>Paste the webhook URL below.</li>
        </ol>
        <input id="csslkurl" class="csslkinput" placeholder="https://hooks.slack.com/services/T…/B…/…" autocomplete="off" />
        <button class="csslksend" id="csslkconnect" style="margin:12px 0 0;width:100%">Connect webhook</button>
        <div class="slkhubsep"></div>
        <p class="slkhubintro"><b>Ask AI in Slack</b> — message the bot (or <code>/complisense</code>) and get agent answers. Best for Docker: Socket Mode (no public URL).</p>
        <ol class="slksteps">
          <li>Create a Slack app → <b>OAuth & Permissions</b> → Bot Token Scopes: <code>chat:write</code>, <code>app_mentions:read</code>, <code>commands</code>, <code>im:history</code>.</li>
          <li>Install to workspace → copy <b>Bot User OAuth Token</b> (<code>xoxb-</code>).</li>
          <li>For local Docker: <b>Basic Information</b> → App-Level Token (<code>xapp-</code>) with <code>connections:write</code> → enable Socket Mode.</li>
          <li>Optional: Event Subscriptions URL <code>https://YOUR_HOST/api/slack/events</code> and Slash Command Request URL <code>…/api/slack/commands</code>.</li>
        </ol>
        <input id="csslkbot" class="csslkinput" placeholder="xoxb-… Bot Token" autocomplete="off" style="margin-bottom:8px" />
        <input id="csslkapp" class="csslkinput" placeholder="xapp-… App Token (Socket Mode)" autocomplete="off" style="margin-bottom:8px" />
        <input id="csslksign" class="csslkinput" placeholder="Signing Secret (HTTP events / slash)" autocomplete="off" />
        <button class="csslksend alt" id="csslkask" style="margin:12px 0 0;width:100%">Enable Ask AI in Slack</button>
        <div id="csslkmsg" class="csslkmsg"></div>
      </div></div></div>`);
    const close=()=>document.getElementById('csslkc')?.remove();
    document.getElementById('csslkcx').addEventListener('click',close);
    document.getElementById('csslkc').addEventListener('click',e=>{if(e.target.id==='csslkc')close()});
    document.getElementById('csslkconnect').addEventListener('click',async()=>{
      const url=document.getElementById('csslkurl').value.trim(),msg=document.getElementById('csslkmsg'),btn=document.getElementById('csslkconnect');
      if(!url){msg.style.color='#d98a8a';msg.textContent='Paste the webhook URL from Slack first.';return;}
      if(!url.startsWith('https://hooks.slack.com/')){msg.style.color='#d98a8a';msg.textContent='That doesn’t look like a Slack webhook URL (must start with https://hooks.slack.com/).';return;}
      msg.style.color='var(--muted)';msg.textContent='Connecting…';btn.disabled=true;
      let r;try{r=await(await fetch('/api/slack/connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({webhook_url:url})})).json();}catch(e){r={ok:false,error:'server offline — start the CompliSense server first'};}
      btn.disabled=false;
      if(r.ok){msg.style.color='var(--sage)';msg.textContent='Webhook connected ✓ — alerts can post.';refreshNavSlack({connected:true,target:url.slice(0,34)+'…'});}
      else{msg.style.color='#d98a8a';msg.textContent=r.error||'Could not connect.';}
    });
    document.getElementById('csslkask').addEventListener('click',async()=>{
      const bot=document.getElementById('csslkbot').value.trim();
      const appTok=document.getElementById('csslkapp').value.trim();
      const sign=document.getElementById('csslksign').value.trim();
      const msg=document.getElementById('csslkmsg'),btn=document.getElementById('csslkask');
      if(!bot){msg.style.color='#d98a8a';msg.textContent='Paste a Bot Token (xoxb-) to enable Ask AI.';return;}
      msg.style.color='var(--muted)';msg.textContent='Enabling Ask AI…';btn.disabled=true;
      let r;try{r=await(await fetch('/api/slack/ask/connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bot_token:bot,app_token:appTok,signing_secret:sign})})).json();}catch(e){r={ok:false,error:'server offline'};}
      btn.disabled=false;
      if(r.ok){
        msg.style.color='var(--sage)';
        msg.textContent=r.socket_mode||r.socket_running
          ?'Ask AI enabled ✓ — Socket Mode listening. @mention the bot or DM it.'
          :'Ask AI enabled ✓ — add an App Token (xapp-) for Socket Mode, or point Events/Slash URLs at this server.';
        refreshNavSlack(r);setTimeout(()=>{close();window.csSlackHub();},900);
      }else{msg.style.color='#d98a8a';msg.textContent=r.error||'Could not enable Ask AI.';}
    });
  }
  async function sendSignal(kind,sector,blocks,btn){
    if(btn){btn.textContent='Sending…';btn.disabled=true;}
    let r;try{r=await(await fetch('/api/slack/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,sector:sector||'',blocks:blocks||null})})).json();}catch(e){r={ok:false,error:'server offline'};}
    if(btn){btn.textContent=r.ok?'Sent to Slack ✓':('Failed — '+(r.error||'error'));btn.disabled=!!r.ok;}
    return r;
  }
  window.csSlackModal=async function(kind,sector,prebuilt){
    let data;
    if(prebuilt){data={blocks:prebuilt};}
    else{try{data=await(await fetch(`/api/slack/preview?kind=${encodeURIComponent(kind||'watchtower')}${sector?'&sector='+encodeURIComponent(sector):''}`)).json();}
    catch(e){data={blocks:[],error:'server offline'};}}
    const st=await slackStatus();
    const footer=data.error?'':(st.connected
      ?`<button class="csslksend" id="csslksend">▧ Send to Slack now</button><div class="csslknote">Posts to your connected channel (<b>${esc(st.target||'')}</b>).</div>`
      :`<button class="csslksend alt" id="csslkconnbtn">Connect Slack to send</button><div class="csslknote">This is the exact Block Kit message — <b>not sent yet</b>.</div>`);
    document.body.insertAdjacentHTML('beforeend',`<div class="csslk" id="csslk"><div class="csslkcard">
      <div class="csslkhead"><span class="slklogo">▧</span> Slack ${st.connected?'· connected':'preview'}<span class="csslkx" id="csslkx">✕</span></div>
      <div class="slkmsg">${data.error?`<div class="slk-s">Couldn't build preview — ${esc(data.error)}</div>`:render(data.blocks)}</div>
      ${footer}
    </div></div>`);
    document.getElementById('csslkx').addEventListener('click',()=>document.getElementById('csslk').remove());
    document.getElementById('csslk').addEventListener('click',e=>{if(e.target.id==='csslk')e.target.remove()});
    const sb=document.getElementById('csslksend');if(sb)sb.addEventListener('click',()=>sendSignal(kind,sector,prebuilt,sb));
    const cb=document.getElementById('csslkconnbtn');if(cb)cb.addEventListener('click',()=>{document.getElementById('csslk').remove();openConnect();});
  };
  // Single main entry point: the header Slack button opens the hub.
  window.csSlackHub=async function(){
    if(document.getElementById('csslkhub'))return;
    const cc=(window.csCompany&&window.csCompany())||{};const sec=cc.gfKey||'';
    const st=await slackStatus();
    refreshNavSlack(st);
    const connBar=(st.connected||st.ask_enabled)
      ?`<div class="csslkconn">${st.connected?'Webhook ✓':''}${st.connected&&st.ask_enabled?' · ':''}${st.ask_enabled?(st.socket_running?'Ask AI ✓ (socket)':'Ask AI ✓'):''}
         <span class="ct">${esc(st.target||'')}</span>
         <span class="csdis" id="csdis">Disconnect</span></div>`
      :`<button class="slkopt connect" id="csslkgo"><b>Connect Slack</b><span>Webhook for alerts · Bot Token for Ask AI in Slack.</span></button>`;
    document.body.insertAdjacentHTML('beforeend',`<div class="csslk" id="csslkhub"><div class="csslkcard">
      <div class="csslkhead"><span class="slklogo">▧</span> Slack${(st.connected||st.ask_enabled)?' · connected':''}<span class="csslkx" id="csslkhubx">✕</span></div>
      <div class="slkhubbody">
        <p class="slkhubintro">${st.ask_enabled?'@mention the bot or DM it a question — CompliSense answers in-thread. ':'Connect outbound webhook and/or Ask AI tokens, then send alerts below.'}</p>
        ${connBar}<div class="slkhubsep"></div>
        <button class="slkopt" data-k="watchtower"><b>⚠ Regulatory alert</b><span>Preview / send a Watchtower circular with the primary source.</span></button>
        <button class="slkopt" data-k="gap"><b>◎ Competitor gap</b><span>Preview / send the top fixable weakness for your sector.</span></button>
        <button class="slkopt" data-k="compliance"><b>⬡ Compliance summary</b><span>Preview / send your sector’s regulators + top blocker.</span></button>
        <button class="slkopt connect" id="csslkcfg"><b>⚙ Tokens & webhook</b><span>Paste webhook / Bot Token / Socket Mode App Token.</span></button>
      </div></div></div>`);
    const close=()=>document.getElementById('csslkhub')?.remove();
    document.getElementById('csslkhubx').addEventListener('click',close);
    document.getElementById('csslkhub').addEventListener('click',e=>{if(e.target.id==='csslkhub')close()});
    const go=document.getElementById('csslkgo');if(go)go.addEventListener('click',()=>{close();openConnect();});
    const cfg=document.getElementById('csslkcfg');if(cfg)cfg.addEventListener('click',()=>{close();openConnect();});
    const dis=document.getElementById('csdis');if(dis)dis.addEventListener('click',async()=>{
      try{await fetch('/api/slack/disconnect',{method:'POST'});}catch(e){}
      try{await fetch('/api/slack/ask/disconnect',{method:'POST'});}catch(e){}
      refreshNavSlack({connected:false,ask_enabled:false});close();window.csSlackHub();
    });
    document.querySelectorAll('#csslkhub .slkopt[data-k]').forEach(b=>b.addEventListener('click',()=>{
      const k=b.dataset.k;close();
      if(k==='gap'&&window.gapToSlack)window.gapToSlack();
      else window.csSlackModal(k,k==='compliance'?sec:'');
    }));
  };
  const _nav=document.querySelector('nav .wrap');
  if(_nav){_nav.insertAdjacentHTML('beforeend','<button id="csnavslk" class="csnavslk" title="Connect & send to Slack">▧ Slack</button>');
    document.getElementById('csnavslk').addEventListener('click',()=>window.csSlackHub());
    slackStatus().then(refreshNavSlack);}
})();

/* floating on-page AI helper: every page hands its context to the live run */
const PAGE_ASK = {
  index:'What can you analyse for my business?',
  dashboard:'Analyse my business profile end to end',
  watchtower:'Explain the latest RBI changes that affect my business',
  compliance:'Assess my compliance readiness and what to fix first',
  pestel:'Which macro force most affects my finances right now, and what should I do?',
  swot:'Given my SWOT, what is the single best strategic move?',
  trends:'Predict my market 12-18 months out and what it means for my money',
  competitors:'Where is my financial opening against my competitors?',
  gapfinder:'Which competitor weakness is the most defensible opening for me?',
};
/* Provenance & confidence lens (canonical, shared by every page) + inline Ask AI */
(function askAI(){
  const CSS=`
  @keyframes csblink{50%{opacity:.25}}
  .provbar{display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:11px 13px;margin-bottom:14px;border:1px solid var(--stroke);border-radius:12px;background:rgba(255,255,255,.02)}
  .provscore{font-family:'Space Grotesk';font-weight:500;font-size:12.5px;color:var(--muted);display:flex;align-items:baseline;gap:6px}
  .provscore .pv{font-size:22px;font-weight:700;color:var(--sage)}
  .provscore.warn .pv{color:#d9a441}.provscore.low .pv{color:#d98a8a}
  .provmeta{font-size:11px;color:var(--faint)}
  .provleg{margin-left:auto;display:flex;gap:12px;font-size:10px;color:var(--muted);font-family:'Space Grotesk'}
  .provleg .lg{position:relative;padding-left:13px}
  .provleg .lg::before{content:'';position:absolute;left:0;top:50%;transform:translateY(-50%);width:8px;height:8px;border-radius:50%}
  .provleg .lg-s::before{background:var(--sage)}.provleg .lg-e::before{background:#d9a441}.provleg .lg-u::before{background:rgba(255,255,255,.35)}
  .provclaims{display:flex;flex-direction:column;gap:6px}
  .cl{position:relative;padding:8px 12px 8px 26px;border-radius:9px;line-height:1.55;font-size:13.5px;border-left:2px solid transparent}
  .cl .cdot{position:absolute;left:11px;top:13px;width:8px;height:8px;border-radius:50%}
  .cl-sourced{background:rgba(123,191,143,.06);border-left-color:var(--sage)}.cl-sourced .cdot{background:var(--sage)}
  .cl-estimate{background:rgba(217,164,65,.06);border-left-color:#d9a441}.cl-estimate .cdot{background:#d9a441}
  .cl-unverified{background:rgba(255,255,255,.02);border-left-color:rgba(255,255,255,.18)}.cl-unverified .cdot{background:rgba(255,255,255,.35)}
  .cit{display:inline-block;font-size:10px;font-family:'Space Grotesk';font-weight:700;padding:1px 6px;margin:0 2px;border-radius:6px;background:var(--sage);color:#06231a;text-decoration:none;vertical-align:middle}
  a.cit:hover{filter:brightness(1.12)}
  .cit-x{background:rgba(255,255,255,.14);color:var(--muted)}
  .provnote{margin-top:11px;font-size:10.5px;color:var(--faint);line-height:1.6}
  .askpanel{position:fixed;right:22px;bottom:82px;width:min(432px,calc(100vw - 30px));max-height:74vh;display:flex;flex-direction:column;background:var(--panel);border:1px solid var(--stroke);border-radius:16px;box-shadow:0 26px 70px -22px rgba(0,0,0,.75);z-index:70;opacity:0;transform:translateY(14px) scale(.985);pointer-events:none;transition:.26s}
  .askpanel.show{opacity:1;transform:none;pointer-events:auto}
  .askpanel .aph{display:flex;align-items:center;gap:9px;padding:12px 15px;border-bottom:1px solid var(--stroke)}
  .askpanel .aph b{font-family:'Space Grotesk';font-size:13px;letter-spacing:.03em}
  .askpanel .apfull{margin-left:auto;font-size:10px;color:var(--teal);text-decoration:none;border:1px solid var(--stroke);border-radius:12px;padding:3px 9px;font-family:'Space Grotesk'}
  .askpanel .apx{cursor:pointer;color:var(--faint);font-size:14px;padding:2px 4px}
  .askpanel .apx:hover{color:var(--text)}
  .aplens{display:flex;flex-wrap:wrap;gap:6px;padding:10px 14px 2px}
  .aplens .lz{cursor:pointer;font-family:'Space Grotesk';font-size:10px;letter-spacing:.05em;border:1px solid var(--stroke);border-radius:14px;padding:4px 10px;color:var(--muted);transition:.18s;user-select:none}
  .aplens .lz:hover{color:var(--text);border-color:var(--stroke2)}
  .aplens .lz.on{background:rgba(76,195,182,.14);border-color:var(--teal);color:var(--teal)}
  .aplens .lzhint{flex-basis:100%;font-size:10px;color:var(--faint);padding:2px 2px 6px;line-height:1.45}
  .aplens .lzcap{font-family:'Space Grotesk';font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint);align-self:center}
  .aplens .lzname{font-family:'Space Grotesk';font-size:12.5px;color:var(--teal);background:rgba(76,195,182,.12);border:1px solid var(--teal);border-radius:12px;padding:3px 11px}
  .askpanel .apin{display:flex;gap:8px;padding:12px 14px;border-bottom:1px solid var(--stroke)}
  .askpanel .apin input{flex:1;min-width:0;background:rgba(255,255,255,.04);border:1px solid var(--stroke);border-radius:10px;padding:9px 11px;color:var(--text);font-size:13px;font-family:inherit;outline:none}
  .askpanel .apin input:focus{border-color:var(--teal)}
  .askpanel .apin button{background:var(--teal);color:#06231a;border:none;border-radius:10px;padding:0 15px;font-weight:700;cursor:pointer;font-family:'Space Grotesk';font-size:12px}
  .askpanel .apstatus{display:flex;align-items:center;gap:9px;padding:10px 15px;font-size:12.5px;color:var(--muted);border-bottom:1px solid var(--stroke)}
  .askpanel .apstatus.idle{display:none}
  .askpanel .apstatus .apdot{width:8px;height:8px;border-radius:50%;background:var(--teal);animation:csblink 1.4s infinite}
  .askpanel .apbody{overflow-y:auto;padding:14px 15px}
  @media(max-width:560px){.askpanel{right:8px;left:8px;bottom:76px;width:auto}}
  `;
  document.head.insertAdjacentHTML('beforeend',`<style>${CSS}</style>`);

  const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  function classify(t){
    if(/\[S\d+\]/.test(t))return'sourced';
    if(/(~|≈|approx|estimat|roughly|ballpark|order[- ]of[- ]magnitude|no public data|assum|indicativ)/i.test(t))return'estimate';
    return'unverified'}
  function cite(t,idMap){return t.replace(/\[S(\d+)\]/g,(m,n)=>{const s=idMap['S'+n],lab='S'+n;
    if(!s)return`<span class="cit cit-x">${lab}</span>`;
    const ref=s.ref||'',tip=esc(s.title||ref||'').replace(/"/g,'&quot;');
    return ref&&/^https?:/i.test(ref)?`<a class="cit" href="${ref}" target="_blank" rel="noopener" title="${tip}">${lab}</a>`
      :`<span class="cit" title="${tip}">${lab}</span>`})}
  function splitClaims(text){const out=[];String(text).split(/\n+/).forEach(line=>{line=line.trim();if(!line)return;
    line.split(/(?<=[.;])\s+(?=[A-Z0-9₹•—-])/).forEach(p=>{p=p.trim();if(p.length>1)out.push(p)})});return out.length?out:[String(text).trim()]}
  window.csRenderProvenance=function(text,sources){
    const idMap={};(sources||[]).forEach(s=>{if(s.id)idMap[s.id]=s});
    const cs=splitClaims(text);let ns=0,ne=0,nu=0;
    const rows=cs.map(c=>{const k=classify(c);k==='sourced'?ns++:k==='estimate'?ne++:nu++;
      return`<p class="cl cl-${k}"><span class="cdot"></span><span class="ctx">${cite(esc(c),idMap)}</span></p>`}).join('');
    const total=cs.length||1,pct=Math.round(ns/total*100),tone=pct>=60?'':pct>=30?'warn':'low';
    return`<div class="provbar"><div class="provscore ${tone}"><span class="pv">${pct}%</span> grounded</div>`
      +`<div class="provmeta">${ns} cited · ${ne} estimate${ne===1?'':'s'} · ${nu} unverified · ${total} claims</div>`
      +`<div class="provleg"><span class="lg lg-s">sourced</span><span class="lg lg-e">estimate</span><span class="lg lg-u">unverified</span></div></div>`
      +`<div class="provclaims">${rows}</div>`
      +`<div class="provnote">Sourced = citation you can open · estimate = a stated approximation · unverified = model reasoning without a cited source. Nothing is shown as fact without provenance.</div>`};

  const page=document.body.dataset.page;
  /* Switchable analysis lenses — framing only. Routing is decided by the
     orchestrator. Default = AUTO (detect from the question); chips are optional overrides. */
  const LENSES={
    finance:{label:'Finance',hint:'Money first: margins, CAC, runway, costs — grounding lens for any sector.',
      frame:'Analyse through the FINANCE lens for my sector: every conclusion must land on a quantified financial metric (margin, CAC, runway, cost), sourced or flagged as an estimate.'},
    regulatory:{label:'Regulatory',hint:'Rules & licenses: obligations, RBI/sectoral regulation, compliance cost.',
      frame:'Analyse through the REGULATORY lens: which rules, licenses and circulars govern this (RBI where relevant, sectoral otherwise), what each obligation costs, citing the rule — and explicitly flag anything outside the grounded corpus as out-of-scope rather than guessing.'},
    customer:{label:'Customer',hint:'Review & sentiment evidence with denominators — never social-media noise as metrics.',
      frame:'Analyse through the CUSTOMER lens: what structured reviews say (with denominators and trend, never anecdotes as metrics), classify complaint themes as fixable gap / inherent tradeoff / vocal minority, and tie sentiment shifts to events.'},
    competitor:{label:'Competitor',hint:'Head-to-head vs named rivals on sourced axes — decompose “better”, never declare it.',
      frame:'Analyse through the COMPETITOR lens: head-to-head against the named rivals on sourced axes (pricing, funding, product, regulatory posture, sentiment), showing who leads per axis with evidence — decompose "better", never a black-box verdict.'},
    strategy:{label:'Strategy',hint:'Relative SWOT + TOWS: every strength/weakness benchmarked “vs whom”.',
      frame:'Analyse through the STRATEGY lens: a relative SWOT (each item benchmarked against a named competitor — a strength only exists vs someone) and the TOWS moves it implies, with the financial impact of each move stated.'},
    growth:{label:'Growth',hint:'PESTEL forces + 12–18 month trajectory, each leg ending in a financial number.',
      frame:'Analyse through the GROWTH lens: the PESTEL forces and 12–18 month trajectory for my sector, each force terminating in a quantified financial impact (sourced or flagged), with what would change the prediction stated explicitly.'}};
  /* Client heuristic — orchestrator still auto-classifies + sets route_flags. */
  window.csDetectLens=function(q){
    const t=String(q||'').toLowerCase();
    if(/\b(through the \w+ lens|analyse through the \w+ lens)\b/.test(t)){
      const m=t.match(/through the (\w+) lens/);
      if(m&&LENSES[m[1]])return m[1];
    }
    if(/\b(rbi|nbfc|licence|license|circular|kyc|compliance|regulator|regulatory|approval)\b/.test(t))return'regulatory';
    if(/\b(review|sentiment|complaint|nps|rating|customer|buyer|vocal minority|fixable gap)\b/.test(t))return'customer';
    if(/\b(competitor|rival|vs\.?|versus|head[- ]to[- ]head|opening|weakness|market share|gap finder)\b/.test(t))return'competitor';
    if(/\b(swot|tows|strategic move|positioning)\b/.test(t))return'strategy';
    if(/\b(pestel|trajectory|12[-–]?18|outlook|trend|growth|macro)\b/.test(t))return'growth';
    if(/\b(margin|cac|runway|burn|cogs|unit economics|ltv|payback)\b/.test(t))return'finance';
    return''; // empty → let orchestrator decide; no forced frame
  };
  let lensMode=localStorage.getItem('cs_lens_mode')||'auto'; // 'auto' | specific key
  let curLens=lensMode==='auto'?'':(LENSES[lensMode]?lensMode:'');
  function lensHint(){
    if(!curLens)return'Lens is chosen automatically from your question — you don’t need to pick one.';
    return LENSES[curLens].hint;
  }
  window.csComposeAsk=q=>{
    const detected=window.csDetectLens(q);
    const lens=curLens||detected||'';
    const cc=(window.csCompanyContext&&window.csCompanyContext())||'';
    const frame=lens&&LENSES[lens]?LENSES[lens].frame:'';
    const parts=[];
    if(frame)parts.push(frame);
    if(cc)parts.push(cc);
    parts.push('Question: '+q);
    return parts.join('\n\n');
  };
  window.csActiveLens=()=>curLens||null;
  if(page==='agents')return; // Live page has its own full runner (still uses csComposeAsk above)
  const seedQ=PAGE_ASK[page]||PAGE_ASK.index;
  const ACT={orchestrator:'Understanding your question…',rbi:'Checking the rulebook…',pestel:'Scanning the environment…',
    competitor:'Scanning the market…',trend:'Reading the trajectory…',faithfulness:'Fact-checking…',
    crossexam:'Peer-reviewing…',swot:'Weighing strategy…',analysis:'Bringing it together…',responder:'Writing your answer…'};
  document.body.insertAdjacentHTML('beforeend',
    `<a class="askfab" id="csfab" role="button" tabindex="0"><span class="afdot"></span>Ask AI<span class="afsub">about this page</span></a>
     <div class="askpanel" id="csask">
       <div class="aph"><span class="afdot"></span><b>Ask CompliSense</b>
         <a class="apfull" id="csfull" href="agents.html">⤢ full live view</a><span class="apx" id="csx">✕</span></div>
       <div class="aplens" id="cslens">
         <span class="lzcap">Lens</span>
         <span class="lz ${!curLens?'on':''}" data-lens="auto">Auto</span>
         ${Object.entries(LENSES).map(([k,l])=>
           `<span class="lz ${k===curLens?'on':''}" data-lens="${k}">${l.label}</span>`).join('')}
         <span class="lzhint" id="cshint">${lensHint()}</span></div>
       <div class="apin"><input id="csq" value="${seedQ.replace(/"/g,'&quot;')}" aria-label="Ask about this page" /><button id="csgo">Ask</button></div>
       <div class="apstatus idle" id="csstat"><span class="apdot"></span><span id="csstattx"></span></div>
       <div class="apbody" id="csans"><div class="provnote">Ask anything — the orchestrator picks the lens and which agents to run. No manual lens required.</div></div>
     </div>`);
  function paintLens(){
    document.querySelectorAll('#cslens .lz').forEach(x=>{
      const k=x.dataset.lens;
      x.classList.toggle('on',(!curLens&&k==='auto')||(curLens&&k===curLens));
    });
    document.getElementById('cshint').textContent=lensHint();
  }
  document.getElementById('cslens').addEventListener('click',e=>{
    const el=e.target.closest('.lz');if(!el)return;
    if(el.dataset.lens==='auto'){curLens='';localStorage.setItem('cs_lens_mode','auto');}
    else{curLens=el.dataset.lens;localStorage.setItem('cs_lens_mode',curLens);}
    paintLens();
  });
  const panel=document.getElementById('csask'),input=document.getElementById('csq'),
    stat=document.getElementById('csstat'),stattx=document.getElementById('csstattx'),ans=document.getElementById('csans');
  let es=null;
  document.getElementById('csfab').addEventListener('click',()=>{panel.classList.add('show');input.focus()});
  document.getElementById('csx').addEventListener('click',()=>panel.classList.remove('show'));
  function run(){
    const q=input.value.trim();if(!q)return;
    if(es)es.close();
    const detected=window.csDetectLens(q);
    const used=curLens||detected||'auto';
    if(!curLens&&detected){
      document.getElementById('cshint').textContent='Auto-detected: '+((LENSES[detected]&&LENSES[detected].label)||detected)+' — '+lensHint();
    }
    const framed=window.csComposeAsk(q);
    document.getElementById('csfull').href='agents.html?q='+encodeURIComponent(framed);
    stat.classList.remove('idle');stattx.textContent=ACT.orchestrator;
    ans.innerHTML='<div class="provnote">Running multi-agent analysis'+(used&&used!=='auto'?' · '+used+' lens':'')+'… orchestrator routes specialists (~30–60s).</div>';
    es=new EventSource('/api/stream?q='+encodeURIComponent(framed));
    let finished=false;
    es.onmessage=e=>{
      let d;try{d=JSON.parse(e.data)}catch(err){return}
      if(d.error&&!d.done){stattx.textContent='Issue — continuing if possible…';
        if(!finished)ans.innerHTML='<div class="provnote">Something went wrong — '+esc(d.error)+'</div>';
        return}
      if(d.done){finished=true;stat.classList.add('idle');
        ans.innerHTML=d.response?window.csRenderProvenance(d.response,d.sources):'<div class="provnote">No answer returned.</div>';
        es.close();return}
      if(d.node==='orchestrator'&&d.analysis_lens){
        const lab=(LENSES[d.analysis_lens]&&LENSES[d.analysis_lens].label)||d.analysis_lens;
        document.getElementById('cshint').textContent='Orchestrator lens: '+lab+(d.route_flags?' · agents: '+Object.entries(d.route_flags).filter(([,v])=>v).map(([k])=>k).join(', ')||'none':'');
      }
      if(d.node&&d.skipped){stattx.textContent=(ACT[d.node]||d.node)+' — skipped';return}
      if(d.node&&ACT[d.node])stattx.textContent=ACT[d.node]};
    es.onerror=()=>{
      if(finished){es.close();return}
      finished=true;stat.classList.add('idle');
      if(!ans.querySelector('.provclaims')&&!ans.textContent.includes('Something went wrong')){
        ans.innerHTML='<div class="provnote">Connection closed before an answer arrived. Check that the server is up (<code>/api/health</code>) and try again.</div>';
      }
      es.close()}}
  document.getElementById('csgo').addEventListener('click',run);
  input.addEventListener('keydown',e=>{if(e.key==='Enter')run()});
})();

/* minimal scroll-reactive background: aurora drifts + hue-shifts, grid parallaxes */
(function bg(){
  const a=document.getElementById('aurora'),g=document.getElementById('grid');let t=0,target=0;
  addEventListener('scroll',()=>{target=scrollY});
  (function loop(){t+=(target-t)*.06;
    const p=t*.05, hue=(t*.02)%40-20;
    a.style.transform=`translate3d(${Math.sin(t*.001)*40}px,${p}px,0)`;
    a.style.filter=`blur(90px) hue-rotate(${hue}deg)`;
    g.style.transform=`translateY(${-p*.4}px)`;
    requestAnimationFrame(loop)})();
})();

/* GSAP scroll system */
function initScroll(){
  if(!window.gsap)return;gsap.registerPlugin(ScrollTrigger);
  gsap.utils.toArray('.reveal').forEach((el,i)=>gsap.to(el,{opacity:1,y:0,duration:.8,delay:(i%4)*.05,scrollTrigger:{trigger:el,start:'top 86%'}}));
  document.querySelectorAll('[data-count]').forEach(el=>ScrollTrigger.create({trigger:el,start:'top 88%',once:true,onEnter:()=>countUp(el)}));
  document.querySelectorAll('.fbar .fill').forEach(el=>ScrollTrigger.create({trigger:el,start:'top 92%',once:true,onEnter:()=>el.style.width=el.dataset.v+'%'}));
  document.querySelectorAll('.ring').forEach(r=>{const c=r.querySelector('circle.val');if(!c)return;
    ScrollTrigger.create({trigger:r,start:'top 82%',once:true,onEnter:()=>{const len=2*Math.PI*100;
      c.style.transition='stroke-dashoffset 1.7s cubic-bezier(.2,.8,.2,1)';c.style.strokeDashoffset=len*(1-(+r.dataset.val)/100)}})});
}
function countUp(el){const t=+el.dataset.count,pre=el.dataset.pre||'',suf=el.dataset.suf||'',dec=t%1?1:0;
  let s=0,step=t/45;const iv=setInterval(()=>{s+=step;if(s>=t){s=t;clearInterval(iv)}el.textContent=pre+s.toFixed(dec)+suf},22)}

function initTilt(){document.querySelectorAll('.t3').forEach(w=>{
  w.addEventListener('mousemove',e=>{const r=w.getBoundingClientRect();
    const rx=((e.clientY-r.top)/r.height-.5)*-9,ry=((e.clientX-r.left)/r.width-.5)*9;
    w.style.transform=`rotateX(${rx}deg) rotateY(${ry}deg) translateY(-4px)`});
  w.addEventListener('mouseleave',()=>w.style.transform='')})}

document.addEventListener('click',e=>{const a=e.target.closest('a[data-link]');
  if(!a||a.getAttribute('href')===here)return;e.preventDefault();
  const c=document.getElementById('curtain');c.classList.remove('gone');
  setTimeout(()=>location.href=a.getAttribute('href'),400)});

/* ---- chart builders (matte) ---- */
const MT={teal:'#4cc3b6',indigo:'#8089e8',rose:'#e08896',amber:'#d9a34e',sage:'#7bbf8f',slate:'#6f7891',
  grid:'rgba(255,255,255,.06)',tick:'#9aa2b1',text:'#e6e8ee'};
/* pages without charts (watchtower/agents) don't load Chart.js — guard, or this
   line throws and kills the whole script incl. the .reveal boot at the bottom. */
if(window.Chart){Chart.defaults.font.family="Inter";Chart.defaults.color=MT.tick;}

/* advanced PESTEL: radial polar-area, animated */
function polar(id,labels,data,colors){new Chart(document.getElementById(id),{type:'polarArea',
  data:{labels,datasets:[{data,backgroundColor:(colors||[MT.indigo,MT.teal,MT.sage,MT.amber,MT.slate,MT.rose]).map(c=>c+'cc'),
    borderColor:'rgba(255,255,255,.10)',borderWidth:1}]},
  options:{responsive:true,maintainAspectRatio:false,animation:{animateRotate:true,duration:1400},
    plugins:{legend:{display:false}},scales:{r:{min:0,max:10,grid:{color:MT.grid},angleLines:{color:MT.grid},
      ticks:{display:false},pointLabels:{display:true,centerPointLabels:true,font:{size:12},color:MT.tick}}}}})}

/* advanced Trends: area + forecast band + dashed projection */
function projection(id,labels,actual,projFrom){
  const ctx=document.getElementById(id).getContext('2d');
  const grad=ctx.createLinearGradient(0,0,0,320);grad.addColorStop(0,'rgba(76,195,182,.30)');grad.addColorStop(1,'rgba(76,195,182,0)');
  const hi=actual.map((v,i)=>i>=projFrom?Math.round(v*1.08):null);
  const lo=actual.map((v,i)=>i>=projFrom?Math.round(v*0.92):null);
  new Chart(document.getElementById(id),{type:'line',
    data:{labels,datasets:[
      {data:hi,borderColor:'transparent',backgroundColor:'rgba(128,137,232,.14)',fill:'+1',pointRadius:0,tension:.4},
      {data:lo,borderColor:'transparent',backgroundColor:'transparent',fill:false,pointRadius:0,tension:.4},
      {data:actual,borderColor:MT.teal,borderWidth:3,backgroundColor:grad,fill:true,tension:.4,
        pointBackgroundColor:MT.teal,pointRadius:(c)=>c.dataIndex>=projFrom?5:4,
        segment:{borderDash:c=>c.p1DataIndex>=projFrom?[6,5]:undefined,borderColor:c=>c.p1DataIndex>=projFrom?MT.indigo:MT.teal}}]},
    options:{responsive:true,maintainAspectRatio:false,animation:{duration:1500},plugins:{legend:{display:false}},
      scales:{x:{grid:{color:MT.grid},ticks:{color:MT.tick}},y:{grid:{color:MT.grid},ticks:{color:MT.tick}}}}})}

function hbars(id,labels,data,colors){new Chart(document.getElementById(id),{type:'bar',
  data:{labels,datasets:[{data,backgroundColor:colors||MT.indigo,borderRadius:7,barThickness:20}]},
  options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,animation:{duration:1300},plugins:{legend:{display:false}},
    scales:{x:{grid:{color:MT.grid},ticks:{color:MT.tick}},y:{grid:{display:false},ticks:{color:MT.text,font:{size:13}}}}}})}
function scatter(id,points){new Chart(document.getElementById(id),{type:'scatter',
  data:{datasets:points.map(p=>({label:p.n,data:[{x:p.x,y:p.y}],backgroundColor:p.c+'dd',borderColor:'rgba(255,255,255,.15)',pointRadius:p.r||11,pointHoverRadius:(p.r||11)+3}))},
  options:{responsive:true,maintainAspectRatio:false,animation:{duration:1200},plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>c.dataset.label}}},
    scales:{x:{min:0,max:10,title:{display:true,text:'Market reach',color:MT.tick},grid:{color:MT.grid},ticks:{color:MT.tick}},
      y:{min:0,max:10,title:{display:true,text:'Compliance maturity',color:MT.tick},grid:{color:MT.grid},ticks:{color:MT.tick}}}}})}
/* multi-line — one line per series, colour passed in (e.g. PESTEL forces by state) */
function multiline(id,labels,series,opts){opts=opts||{};
  new Chart(document.getElementById(id),{type:'line',
    data:{labels,datasets:series.map(s=>({label:s.name,data:s.data,borderColor:s.color,backgroundColor:s.color,
      borderWidth:2.5,tension:.4,pointRadius:3,pointHoverRadius:6,fill:false}))},
    options:{responsive:true,maintainAspectRatio:false,animation:{duration:1300},
      onClick:(e,els)=>{if(els.length&&opts.onPoint)opts.onPoint(els[0].datasetIndex,els[0].index)},
      plugins:{legend:{display:opts.legend!==false,position:'bottom',labels:{color:MT.tick,boxWidth:12,font:{size:11.5},usePointStyle:true}},
        tooltip:{callbacks:{title:i=>labels[i[0].dataIndex],label:c=>`${c.dataset.label}: ${c.parsed.y}`}}},
      scales:{x:{grid:{color:MT.grid},ticks:{color:MT.tick}},y:{min:opts.min,max:opts.max,grid:{color:MT.grid},ticks:{color:MT.tick}}}}})}

/* scenarios — bull/base/bear band lines */
function scenarios(id,labels,series,colors){
  new Chart(document.getElementById(id),{type:'line',
    data:{labels,datasets:Object.keys(series).map(k=>({label:k,data:series[k],borderColor:colors[k],backgroundColor:colors[k],
      borderWidth:k==='Base'?3:2,borderDash:k==='Base'?[]:[5,4],tension:.4,pointRadius:3,fill:false}))},
    options:{responsive:true,maintainAspectRatio:false,animation:{duration:1300},
      plugins:{legend:{display:true,position:'bottom',labels:{color:MT.tick,boxWidth:12,font:{size:11.5},usePointStyle:true}}},
      scales:{x:{grid:{color:MT.grid},ticks:{color:MT.tick}},y:{grid:{color:MT.grid},ticks:{color:MT.tick}}}}})}

window.polar=polar;window.projection=projection;window.hbars=hbars;window.scatter=scatter;
window.multiline=multiline;window.scenarios=scenarios;

/* ---- daily monitor strip: evidence-hashed, stable-until-market-moves ---- */
async function mountMonitor(kind){
  const el=document.getElementById('monitor');if(!el)return;
  try{
    const d=await(await fetch('/api/state')).json();
    if(d.error||!d.brief)throw 0;
    const since=new Date(d.since).toLocaleDateString(undefined,{day:'numeric',month:'short'});
    const fresh=(d.new_since_last||[]).length;
    const stable=d.stable&&!fresh;
    let chips='';
    if(kind==='pestel'){
      chips=Object.entries(d.brief.pestel_forces||{}).map(([f,v])=>
        `<a class="mchip" href="${v.events[0].link}" target="_blank" rel="noopener" title="${v.events[0].title}">▲ ${f} ${v.direction} · ${v.events.length} event${v.events.length>1?'s':''}</a>`).join('');
    }else{
      const su=d.brief.swot_updates||{Threats:[],Opportunities:[]};
      chips=[...su.Threats.slice(0,3).map(t=>`<a class="mchip rose" href="${t.link}" target="_blank" rel="noopener" title="${t.why}">T · ${t.title.slice(0,46)}${t.title.length>46?'…':''}</a>`),
             ...su.Opportunities.slice(0,2).map(o=>`<a class="mchip sage" href="${o.link}" target="_blank" rel="noopener" title="${o.why}">O · ${o.title.slice(0,46)}${o.title.length>46?'…':''}</a>`)].join('');
    }
    el.innerHTML=`<div class="mhead">
        <span class="mdot ${stable?'ok':'hot'}"></span><b>DAILY MONITOR</b>
        <span class="masof">${stable?`read unchanged since ${since} — market quiet`:`market moved — ${fresh} new signal${fresh===1?'':'s'}`}</span>
        <span class="mhash" title="${(d.method||'').replace(/"/g,'')}">evidence #${d.evidence_hash}</span>
      </div>
      <div class="mchips">${chips||'<span class="mnone">no force-moving events in the current window</span>'}</div>`;
  }catch(e){
    el.innerHTML='<div class="mhead"><span class="mdot"></span><b>DAILY MONITOR</b><span class="masof">offline — start the server for live monitoring</span></div>';
  }
}
window.mountMonitor=mountMonitor;

/* ---- detail drawer (PESTEL force / SWOT item deep-dive) ---- */
function drawer(html,color){
  let d=document.getElementById('dwrap');
  if(!d){document.body.insertAdjacentHTML('beforeend',
    `<div class="dwrap" id="dwrap"><div class="scrim" onclick="closeDrawer()"></div><div class="drawer" id="drawerBody"></div></div>`);
    d=document.getElementById('dwrap');
    addEventListener('keydown',e=>{if(e.key==='Escape')closeDrawer()});}
  const body=document.getElementById('drawerBody');
  body.style.setProperty('--dc',color||'var(--accent)');
  body.innerHTML=`<span class="dx" onclick="closeDrawer()">✕</span>`+html;
  d.classList.add('show');document.body.style.overflow='hidden';
  requestAnimationFrame(()=>{
    body.querySelectorAll('.dfill').forEach(f=>f.style.width=f.dataset.v+'%');
    body.querySelectorAll('.spark i').forEach((i,n)=>setTimeout(()=>i.style.height=i.dataset.h+'%',n*70));
  });
}
function closeDrawer(){const d=document.getElementById('dwrap');if(d){d.classList.remove('show');document.body.style.overflow=''}}
window.drawer=drawer;window.closeDrawer=closeDrawer;

/* ---- ask modal (demo; agents.html does the live stream) ---- */
function fill(el){const i=document.getElementById('q');if(i){i.value=el.textContent;ask()}}
function ask(){const i=document.getElementById('q');if(!i)return;const q=i.value.trim();if(!q)return;
  let r=document.getElementById('resp');
  if(!r){document.body.insertAdjacentHTML('beforeend',`<div class="resp" id="resp"><div class="respcard"><span class="x" onclick="document.getElementById('resp').classList.remove('show')">✕</span><div class="eyebrow" id="rqi"></div><div class="bar" id="rbar"></div><div class="typed" id="rtxt"></div></div></div>`);r=document.getElementById('resp')}
  r.classList.add('show');document.getElementById('rqi').textContent=q;
  const bar=document.getElementById('rbar');bar.style.width='0';setTimeout(()=>bar.style.width='100%',60);
  const a=answer(q),tx=document.getElementById('rtxt');tx.textContent='';let n=0;
  (function type(){if(n<=a.length){tx.textContent=a.slice(0,n);n+=2;setTimeout(type,7)}})()}
function answer(q){const l=q.toLowerCase();
  if(l.includes('28%')||l.includes('control')||l.includes('investor'))return`Yes — prior RBI approval is required.\n\n• Shareholding: a new investor at 28% crosses the 26% change-in-control threshold  [Scale-Based Regulation 2023].\n• Management: replacing 4 of 10 directors (40%) exceeds the 30% board-change threshold.\n\nNext: file for RBI prior approval before closing; prepare fit-and-proper docs.`;
  if(l.includes('payment aggregator')||l.includes('licence')||l.includes('license')||l.includes('net worth'))return`Payment Aggregator licence (RBI, PSS Act).\n\n• Net worth: ₹15 cr → ₹25 cr by Mar 2028  [PA Directions 2025].\n• Submit: financials, net-worth certificate, business plan, KYC/AML framework, infosec policy.`;
  if(l.includes('kyc')||l.includes('onboard'))return`KYC / customer due diligence  [KYC Master Direction 2016].\n\n• Verify identity (Aadhaar e-KYC, Video-KYC, OVDs).\n• EDD for non-face-to-face; STRs to FIU-IND in 7 days; retain records 5 years.`;
  return`Open the Live page to watch the agents run this question and return a cited answer.`}
window.fill=fill;window.ask=ask;

/* readyState-aware boot: if the document already finished parsing by the time
   this runs (bfcache restore, preview panel timing), DOMContentLoaded never
   re-fires and .reveal elements would stay invisible. */
function _boot(){initScroll();initTilt()}
if(document.readyState==='loading'){addEventListener('DOMContentLoaded',_boot)}else{_boot()}
