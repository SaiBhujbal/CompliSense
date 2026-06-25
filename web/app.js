/* CompliSense futuristic UI. Sample analysis baked in; swap DATA for a live
   call to the backend (/api/analyze) when wiring the agents (see ask()). */

const DATA = {
  pestel: [
    {k:'Political',  s:7, c:'#8b7bff', t:'Pro-digital policy; tight RBI scrutiny of lending & PA settlements.'},
    {k:'Economic',   s:8, c:'#3df0ff', t:'$2.4B FinTech funding in 2025; early-stage up 78% YoY.'},
    {k:'Social',     s:8, c:'#39e6a8', t:'UPI-native users; trust hinges on transparent, fair conduct.'},
    {k:'Technological',s:9,c:'#ffc24b', t:'Account Aggregator rails + AI underwriting reshape the stack.'},
    {k:'Environmental',s:4,c:'#5b6890', t:'Low direct exposure; ESG disclosure rising for lenders.'},
    {k:'Legal',      s:6, c:'#ff5db1', t:'DPDP Act, KYC MD 2016, PA Directions 2025 all in force.'},
  ],
  swot: [
    {h:'Strengths', i:'S', c:'#39e6a8', li:['Citation-grounded RBI answers','Account-Aggregator-ready data model','Faithfulness gate on every claim']},
    {h:'Weaknesses', i:'W', c:'#ffc24b', li:['NOF below ₹10 cr 2027 target','Manual compliance reporting','Thin capital buffer']},
    {h:'Opportunities', i:'O', c:'#3df0ff', li:['Co-lending with banks','Underserved MSME credit','PA licence → payments upsell']},
    {h:'Threats', i:'T', c:'#ff5d6c', li:['Tightening DLG / pass-through rules','Funding cool-down risk','Incumbent super-apps']},
  ],
  competitors: [
    {n:'LenDenClub', tag:'P2P', funding:'$10M', stage:'Series B'},
    {n:'KreditBee', tag:'Digital lending', funding:'$700M', stage:'Series D'},
    {n:'Cred', tag:'Payments', funding:'$806M', stage:'Late'},
  ],
  trend:{labels:['2021','2022','2023','2024','2025','2026E'], v:[34,52,61,70,84,97]},
};

/* ---------- particle backdrop ---------- */
(function bg(){
  const c=document.getElementById('bg'),x=c.getContext('2d');let w,h,pts;
  function rs(){w=c.width=innerWidth;h=c.height=innerHeight;pts=Array.from({length:Math.min(90,innerWidth/16)},()=>({x:Math.random()*w,y:Math.random()*h,vx:(Math.random()-.5)*.25,vy:(Math.random()-.5)*.25}))}
  rs();addEventListener('resize',rs);
  (function loop(){x.clearRect(0,0,w,h);
    for(const p of pts){p.x=(p.x+p.vx+w)%w;p.y=(p.y+p.vy+h)%h}
    for(let i=0;i<pts.length;i++){const a=pts[i];
      x.fillStyle='rgba(61,240,255,.6)';x.beginPath();x.arc(a.x,a.y,1.3,0,7);x.fill();
      for(let j=i+1;j<pts.length;j++){const b=pts[j],d=Math.hypot(a.x-b.x,a.y-b.y);
        if(d<120){x.strokeStyle='rgba(139,123,255,'+(.16*(1-d/120))+')';x.lineWidth=.6;x.beginPath();x.moveTo(a.x,a.y);x.lineTo(b.x,b.y);x.stroke()}}}
    requestAnimationFrame(loop)})();
})();

/* ---------- hero intro ---------- */
gsap.to('#k',{opacity:1,y:0,duration:.7,delay:.1});
gsap.fromTo('#h1',{opacity:0,y:24},{opacity:1,y:0,duration:.9,delay:.25});
gsap.fromTo('#hp',{opacity:0,y:18},{opacity:1,y:0,duration:.8,delay:.5});
gsap.fromTo('#ask',{opacity:0,y:18},{opacity:1,y:0,duration:.8,delay:.7});
gsap.to('#chips',{opacity:1,duration:.8,delay:.9});

/* ---------- scroll reveals ---------- */
gsap.registerPlugin(ScrollTrigger);
gsap.utils.toArray('.reveal').forEach(el=>gsap.to(el,{opacity:1,y:0,duration:.7,scrollTrigger:{trigger:el,start:'top 85%'}}));

/* ---------- count-up + compliance ring (on scroll) ---------- */
function countUp(el){const tgt=+el.dataset.count,pre=el.dataset.pre||'',suf=el.dataset.suf||'',dec=tgt%1?1:0;
  let s=0;const step=tgt/45;const t=setInterval(()=>{s+=step;if(s>=tgt){s=tgt;clearInterval(t)}el.textContent=pre+s.toFixed(dec)+suf},22)}
document.querySelectorAll('[data-count]').forEach(el=>{
  new IntersectionObserver((es,o)=>es.forEach(e=>{if(e.isIntersecting){countUp(el);o.disconnect()}}),{threshold:.6}).observe(el)});
new IntersectionObserver((es,o)=>es.forEach(e=>{if(e.isIntersecting){
  document.getElementById('ringc').style.transition='stroke-dashoffset 1.6s cubic-bezier(.2,.8,.2,1)';
  document.getElementById('ringc').style.strokeDashoffset=628*(1-.78);o.disconnect()}}),{threshold:.5})
  .observe(document.querySelector('.ring'));

/* ---------- PESTEL factors + radar ---------- */
const fc=document.getElementById('factors');
DATA.pestel.forEach((f,i)=>{const d=document.createElement('div');d.className='factor';d.style.setProperty('--c',f.c);
  d.innerHTML=`<div class="ft"><b>${f.k}</b><span class="score">${f.s}/10</span></div><p>${f.t}</p>`;
  d.onclick=()=>{document.querySelectorAll('.factor').forEach(x=>x.classList.remove('on'));d.classList.add('on')};
  if(i===3)d.classList.add('on');fc.appendChild(d)});
new Chart(document.getElementById('radar'),{type:'radar',
  data:{labels:DATA.pestel.map(f=>f.k.slice(0,4)),datasets:[{data:DATA.pestel.map(f=>f.s),
    borderColor:'#3df0ff',backgroundColor:'rgba(139,123,255,.22)',pointBackgroundColor:'#ff5db1',borderWidth:2}]},
  options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},
    scales:{r:{min:0,max:10,grid:{color:'rgba(120,160,255,.15)'},angleLines:{color:'rgba(120,160,255,.15)'},
      pointLabels:{color:'#94a3c8',font:{size:12}},ticks:{display:false}}}}});

/* ---------- SWOT ---------- */
const sw=document.getElementById('swot');
DATA.swot.forEach((q,i)=>{const d=document.createElement('div');d.className='q reveal';d.style.setProperty('--qc',q.c);
  d.innerHTML=`<h3><i>${q.i}</i>${q.h}</h3><ul>${q.li.map(x=>`<li>${x}</li>`).join('')}</ul>`;sw.appendChild(d);
  gsap.to(d,{opacity:1,y:0,duration:.6,delay:i*.08,scrollTrigger:{trigger:'#swot',start:'top 80%'}})});

/* ---------- trend chart ---------- */
new Chart(document.getElementById('trend'),{type:'line',
  data:{labels:DATA.trend.labels,datasets:[{data:DATA.trend.v,borderColor:'#3df0ff',borderWidth:3,tension:.4,
    fill:true,backgroundColor:(c)=>{const g=c.chart.ctx.createLinearGradient(0,0,0,330);g.addColorStop(0,'rgba(61,240,255,.35)');g.addColorStop(1,'rgba(61,240,255,0)');return g},
    pointBackgroundColor:'#ff5db1',pointRadius:4}]},
  options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},
    scales:{x:{grid:{color:'rgba(120,160,255,.08)'},ticks:{color:'#94a3c8'}},
      y:{grid:{color:'rgba(120,160,255,.08)'},ticks:{color:'#94a3c8'}}}}});

/* ---------- competitor 3D tilt ---------- */
const cm=document.getElementById('cmps');
DATA.competitors.forEach(c=>{const w=document.createElement('div');w.className='card cmp reveal';
  w.innerHTML=`<div class="top"><span class="badge">${c.tag}</span></div><h3>${c.n}</h3>
    <div class="stat"><div><span>Funding</span><b>${c.funding}</b></div><div><span>Stage</span><b>${c.stage}</b></div></div>`;
  cm.appendChild(w);gsap.to(w,{opacity:1,y:0,duration:.6,scrollTrigger:{trigger:'#competitors',start:'top 80%'}});
  w.addEventListener('mousemove',e=>{const r=w.getBoundingClientRect();const rx=((e.clientY-r.top)/r.height-.5)*-10;const ry=((e.clientX-r.left)/r.width-.5)*10;
    w.style.transform=`rotateX(${rx}deg) rotateY(${ry}deg) translateY(-4px)`});
  w.addEventListener('mouseleave',()=>w.style.transform='')});

/* ---------- ask (animated response) ---------- */
function fill(el){document.getElementById('q').value=el.textContent;ask()}
function ask(){
  const q=document.getElementById('q').value.trim();if(!q)return;
  const r=document.getElementById('resp');r.classList.add('show');
  document.getElementById('rqi').textContent=q;
  document.getElementById('rbar').style.width='0';
  setTimeout(()=>document.getElementById('rbar').style.width='100%',50);
  const txt=document.getElementById('rtxt');txt.textContent='';
  /* DEMO answer. To go live: fetch(`/api/analyze?q=`+encodeURIComponent(q)).then(r=>r.json())
     and type out data.final_response (the graph already returns it, [S#]-cited). */
  const a=answer(q);let i=0;(function type(){if(i<=a.length){txt.textContent=a.slice(0,i);i+=2;setTimeout(type,8)}})();
}
function answer(q){const l=q.toLowerCase();
  if(l.includes('28%')||l.includes('control')||l.includes('investor'))
    return `Yes — prior RBI approval is required.\n\n• Shareholding: a new investor at 28% crosses the 26% threshold for change in control  [Scale-Based Regulation 2023].\n• Management: replacing 4 of 10 directors (40%) exceeds the 30% board-change threshold  [SBR 2023].\n\nNext steps:\n1. File for RBI prior approval before closing the round.\n2. Prepare fit-and-proper docs for the incoming shareholder.\n3. Brief the board on the approval timeline.`;
  if(l.includes('payment aggregator')||l.includes('licence')||l.includes('license')||l.includes('net worth'))
    return `Payment Aggregator licence (RBI authorisation under the PSS Act).\n\n• Minimum net worth: ₹15 crore now, rising to ₹25 crore by Mar 2028  [PA Directions 2025].\n• Submit: audited financials, net-worth certificate, business plan, KYC/AML framework, infosec policy.\n• Ongoing: merchant due diligence, settlement & fraud reporting to RBI.`;
  if(l.includes('kyc')||l.includes('onboard'))
    return `KYC / customer due diligence for onboarding  [KYC Master Direction 2016].\n\n• Verify identity (Aadhaar e-KYC, Video-KYC, or OVDs).\n• Risk-categorise the customer; apply Enhanced Due Diligence for non-face-to-face.\n• Ongoing transaction monitoring; file STRs to FIU-IND within 7 days; retain records 5 years.`;
  return `CompliSense routes your question to the RBI, PESTEL, competitor and trend agents, grounds the answer in cited RBI directions, and renders it as the visuals above.\n\nTry a specific compliance question — licensing, KYC, change of control, digital lending — for a board-ready, [S#]-cited answer.`;
}
window.fill=fill;window.ask=ask;
