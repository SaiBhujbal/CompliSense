/* CompliSense shared engine: 3D backdrop, scroll animations, page transitions,
   chart builders, ask modal. Pages set <body data-page="..."> and call builders. */

/* ---------------- shared chrome (curtain + nav + footer) ---------------- */
const PAGES = [
  ['index.html','Overview'],['compliance.html','Compliance'],['pestel.html','PESTEL'],
  ['swot.html','SWOT'],['trends.html','Trends'],['competitors.html','Market'],
];
const here = (location.pathname.split('/').pop() || 'index.html');
document.body.insertAdjacentHTML('afterbegin',
  `<canvas id="three"></canvas><div class="veil"></div>
   <div class="curtain" id="curtain"><div class="ld">CompliSense</div></div>
   <nav><div class="wrap">
     <a class="brand" href="index.html" data-link><span class="dot"></span>Compli<span class="grad">Sense</span></a>
     <div class="nav-links">${PAGES.filter(p=>p[0]!=='index.html').map(p=>`<a href="${p[0]}" data-link class="${p[0]===here?'active':''}">${p[1]}</a>`).join('')}</div>
   </div></nav>`);
addEventListener('load',()=>setTimeout(()=>document.getElementById('curtain').classList.add('gone'),250));

/* ---------------- Three.js 3D backdrop ---------------- */
function initThree(){
  if(!window.THREE)return;
  const cv=document.getElementById('three');
  const rnd=new THREE.WebGLRenderer({canvas:cv,alpha:true,antialias:true});
  rnd.setPixelRatio(Math.min(devicePixelRatio,2));rnd.setSize(innerWidth,innerHeight);
  const scene=new THREE.Scene();
  const cam=new THREE.PerspectiveCamera(60,innerWidth/innerHeight,.1,100);cam.position.z=15;
  const ico=new THREE.Mesh(new THREE.IcosahedronGeometry(6,1),
    new THREE.MeshBasicMaterial({color:0x3df0ff,wireframe:true,transparent:true,opacity:.18}));
  const ico2=new THREE.Mesh(new THREE.IcosahedronGeometry(4,1),
    new THREE.MeshBasicMaterial({color:0x8b7bff,wireframe:true,transparent:true,opacity:.22}));
  scene.add(ico,ico2);
  const N=900,pos=new Float32Array(N*3);
  for(let i=0;i<N*3;i++)pos[i]=(Math.random()-.5)*46;
  const pg=new THREE.BufferGeometry();pg.setAttribute('position',new THREE.BufferAttribute(pos,3));
  const pts=new THREE.Points(pg,new THREE.PointsMaterial({color:0x9fb6ff,size:.07,transparent:true,opacity:.6}));
  scene.add(pts);
  let mx=0,my=0;addEventListener('mousemove',e=>{mx=(e.clientX/innerWidth-.5);my=(e.clientY/innerHeight-.5)});
  let sy=0;addEventListener('scroll',()=>sy=scrollY);
  addEventListener('resize',()=>{rnd.setSize(innerWidth,innerHeight);cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix()});
  let last=0;
  function loop(t){
    if(window.__stopGL)return;requestAnimationFrame(loop);
    if(document.hidden||t-last<33)return;last=t;  /* ~30fps; pause when tab hidden */
    ico.rotation.y+=.005;ico.rotation.x+=.0024;ico2.rotation.y-=.0072;ico2.rotation.z+=.0036;
    pts.rotation.y+=.0012;
    cam.position.x+=(mx*3-cam.position.x)*.04;cam.position.y+=(-my*3-cam.position.y)*.04;
    cam.position.z=15+sy*.004;cam.lookAt(0,0,0);rnd.render(scene,cam);
  }
  requestAnimationFrame(loop);
}
initThree();

/* ---------------- GSAP scroll system ---------------- */
function initScroll(){
  if(!window.gsap)return;gsap.registerPlugin(ScrollTrigger);
  gsap.utils.toArray('.reveal').forEach((el,i)=>gsap.to(el,{opacity:1,y:0,duration:.8,delay:(i%4)*.06,
    scrollTrigger:{trigger:el,start:'top 86%'}}));
  document.querySelectorAll('[data-count]').forEach(el=>{
    ScrollTrigger.create({trigger:el,start:'top 88%',once:true,onEnter:()=>countUp(el)})});
  document.querySelectorAll('.fbar .fill').forEach(el=>{
    ScrollTrigger.create({trigger:el,start:'top 92%',once:true,onEnter:()=>el.style.width=el.dataset.v+'%'})});
  document.querySelectorAll('.ring').forEach(r=>{const c=r.querySelector('circle.val');if(!c)return;
    ScrollTrigger.create({trigger:r,start:'top 80%',once:true,onEnter:()=>{
      const len=2*Math.PI*100;c.style.transition='stroke-dashoffset 1.7s cubic-bezier(.2,.8,.2,1)';
      c.style.strokeDashoffset=len*(1-(+r.dataset.val)/100)}})});
}
function countUp(el){const t=+el.dataset.count,pre=el.dataset.pre||'',suf=el.dataset.suf||'',dec=t%1?1:0;
  let s=0,step=t/45;const iv=setInterval(()=>{s+=step;if(s>=t){s=t;clearInterval(iv)}el.textContent=pre+s.toFixed(dec)+suf},22)}

/* ---------------- 3D tilt ---------------- */
function initTilt(){document.querySelectorAll('.t3').forEach(w=>{
  w.addEventListener('mousemove',e=>{const r=w.getBoundingClientRect();
    const rx=((e.clientY-r.top)/r.height-.5)*-12,ry=((e.clientX-r.left)/r.width-.5)*12;
    w.style.transform=`rotateX(${rx}deg) rotateY(${ry}deg) translateY(-5px)`});
  w.addEventListener('mouseleave',()=>w.style.transform='')})}

/* ---------------- page transitions ---------------- */
document.addEventListener('click',e=>{const a=e.target.closest('a[data-link]');
  if(!a||a.getAttribute('href')===here)return;e.preventDefault();
  const c=document.getElementById('curtain');c.classList.remove('gone');
  setTimeout(()=>location.href=a.getAttribute('href'),420)});

/* ---------------- chart builders ---------------- */
const Cg={grid:'rgba(120,160,255,.1)',tick:'#94a3c8'};
function radar(id,labels,data){new Chart(document.getElementById(id),{type:'radar',
  data:{labels,datasets:[{data,borderColor:'#3df0ff',backgroundColor:'rgba(139,123,255,.22)',
    pointBackgroundColor:'#ff5db1',borderWidth:2,pointRadius:4}]},
  options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},
    scales:{r:{min:0,max:10,grid:{color:Cg.grid},angleLines:{color:Cg.grid},
      pointLabels:{color:Cg.tick,font:{size:12}},ticks:{display:false}}}}})}
function area(id,labels,data,label){new Chart(document.getElementById(id),{type:'line',
  data:{labels,datasets:[{label,data,borderColor:'#3df0ff',borderWidth:3,tension:.4,fill:true,pointRadius:4,
    pointBackgroundColor:'#ff5db1',backgroundColor:c=>{const g=c.chart.ctx.createLinearGradient(0,0,0,330);
      g.addColorStop(0,'rgba(61,240,255,.34)');g.addColorStop(1,'rgba(61,240,255,0)');return g}}]},
  options:{responsive:true,maintainAspectRatio:false,animation:{duration:1400},plugins:{legend:{display:false}},
    scales:{x:{grid:{color:Cg.grid},ticks:{color:Cg.tick}},y:{grid:{color:Cg.grid},ticks:{color:Cg.tick}}}}})}
function hbars(id,labels,data,colors){new Chart(document.getElementById(id),{type:'bar',
  data:{labels,datasets:[{data,backgroundColor:colors||'#8b7bff',borderRadius:8,barThickness:22}]},
  options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,animation:{duration:1300},plugins:{legend:{display:false}},
    scales:{x:{grid:{color:Cg.grid},ticks:{color:Cg.tick}},y:{grid:{display:false},ticks:{color:'#eaf0ff',font:{size:13}}}}}})}
function scatter(id,points){new Chart(document.getElementById(id),{type:'scatter',
  data:{datasets:points.map(p=>({label:p.n,data:[{x:p.x,y:p.y}],backgroundColor:p.c,pointRadius:p.r||10,pointHoverRadius:(p.r||10)+3}))},
  options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>c.dataset.label}}},
    scales:{x:{min:0,max:10,title:{display:true,text:'Market reach',color:Cg.tick},grid:{color:Cg.grid},ticks:{color:Cg.tick}},
      y:{min:0,max:10,title:{display:true,text:'Compliance maturity',color:Cg.tick},grid:{color:Cg.grid},ticks:{color:Cg.tick}}}}})}
window.radar=radar;window.area=area;window.hbars=hbars;window.scatter=scatter;

/* ---------------- ask modal (demo; wire /api/analyze for live) ---------------- */
function fill(el){const i=document.getElementById('q');if(i){i.value=el.textContent;ask()}}
function ask(){const i=document.getElementById('q');if(!i)return;const q=i.value.trim();if(!q)return;
  let r=document.getElementById('resp');
  if(!r){document.body.insertAdjacentHTML('beforeend',
    `<div class="resp" id="resp"><div class="respcard"><span class="x" onclick="document.getElementById('resp').classList.remove('show')">✕</span>
     <div class="eyebrow" id="rqi"></div><div class="bar" id="rbar"></div><div class="typed" id="rtxt"></div></div></div>`);
    r=document.getElementById('resp')}
  r.classList.add('show');document.getElementById('rqi').textContent=q;
  const bar=document.getElementById('rbar');bar.style.width='0';setTimeout(()=>bar.style.width='100%',60);
  const a=answer(q),tx=document.getElementById('rtxt');tx.textContent='';let n=0;
  (function type(){if(n<=a.length){tx.textContent=a.slice(0,n);n+=2;setTimeout(type,7)}})()}
function answer(q){const l=q.toLowerCase();
  if(l.includes('28%')||l.includes('control')||l.includes('investor'))return`Yes — prior RBI approval is required.\n\n• Shareholding: a new investor at 28% crosses the 26% change-in-control threshold  [Scale-Based Regulation 2023].\n• Management: replacing 4 of 10 directors (40%) exceeds the 30% board-change threshold  [SBR 2023].\n\nNext steps:\n1. File for RBI prior approval before closing.\n2. Prepare fit-and-proper docs for the incoming shareholder.\n3. Brief the board on the timeline.`;
  if(l.includes('payment aggregator')||l.includes('licence')||l.includes('license')||l.includes('net worth'))return`Payment Aggregator licence (RBI, under the PSS Act).\n\n• Minimum net worth: ₹15 cr now → ₹25 cr by Mar 2028  [PA Directions 2025].\n• Submit: audited financials, net-worth certificate, business plan, KYC/AML framework, infosec policy.\n• Ongoing: merchant due diligence + settlement & fraud reporting.`;
  if(l.includes('kyc')||l.includes('onboard'))return`KYC / customer due diligence  [KYC Master Direction 2016].\n\n• Verify identity (Aadhaar e-KYC, Video-KYC, or OVDs).\n• Risk-categorise; Enhanced Due Diligence for non-face-to-face.\n• Monitor transactions; STRs to FIU-IND within 7 days; retain records 5 years.`;
  return`CompliSense routes your question to the RBI, PESTEL, competitor and trend agents, grounds the answer in cited RBI directions, and renders it as live visuals.\n\nTry: licensing, KYC, change of control, or digital lending — for a board-ready, [S#]-cited answer.`}
window.fill=fill;window.ask=ask;

addEventListener('DOMContentLoaded',()=>{initScroll();initTilt()});
