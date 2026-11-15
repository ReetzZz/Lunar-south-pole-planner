# Last updated: 2026-11-14
from pathlib import Path
from datetime import datetime
import shutil

p = Path("src/ui_web/index.html")
html = p.read_text(encoding="utf-8")

if 'id="lunarHome"' in html:
    raise SystemExit("Home già installata.")

for anchor in ("</head>", "</header>", "<main>", "</body>"):
    if html.count(anchor) != 1:
        raise SystemExit(f"STOP: ancora {anchor!r} non univoca.")

backup = Path("backups") / f"index-before-home-{datetime.now():%Y%m%d-%H%M%S}.html"
backup.parent.mkdir(exist_ok=True)
shutil.copy2(p, backup)

css = """
<style>
body.home-mode main{display:none!important}
body:not(.home-mode) .home-screen{display:none!important}
body.home-mode #openHome{display:none}
#openHome{margin-left:16px;padding:9px 15px;color:#8ff2fa;background:#10303b;border:1px solid #286574;border-radius:5px}
.home-screen{min-height:calc(100vh - 65px);padding:clamp(20px,4vw,52px);overflow:auto;background:radial-gradient(ellipse at 50% 0%,#142b40,#080f19 55%,#060a10)}
.home-content{max-width:1050px;margin:auto}
.home-intro{text-align:center;padding:25px 0 30px}
.home-eyebrow{color:var(--cyan);font-size:10px;letter-spacing:3px}
.home-title{font-size:clamp(27px,4vw,43px);letter-spacing:2px}
.home-description{color:var(--muted);line-height:1.7;max-width:650px;margin:auto}
.home-step{margin:22px 0 10px;font-size:11px;letter-spacing:1.5px;color:#b5c9dc;font-weight:700}
.home-sites{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px}
.home-site{text-align:left;padding:18px;min-height:112px;border:1px solid #263b50;border-radius:9px;background:linear-gradient(145deg,#101f2e,#0b131e)}
.home-site.selected{border-color:var(--cyan);background:#102a37}
.home-site strong{display:block;font-size:16px;margin-bottom:9px}
.home-site span{color:var(--muted);font-size:11px;line-height:1.5}
.home-site .site-check{float:right;color:var(--cyan);opacity:0}
.home-site.selected .site-check{opacity:1}
.home-options{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:19px;border:1px solid #263b50;border-radius:9px;background:#0b141f}
.home-options label{display:block;color:var(--muted);font-size:10px;letter-spacing:1px}
.home-options input{display:block;width:100%;margin-top:8px}
.home-actions{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:17px}
.home-actions button{min-height:49px;border-radius:6px;font-weight:800;letter-spacing:1px}
.home-primary{background:#103541;border:1px solid #327181;color:#9af5fa}
.home-secondary{background:#101c29;border:1px solid #263b50;color:#c0d0df}
#homeError{min-height:18px;margin-top:10px;color:#f4b95f;text-align:center;font-size:11px}
.home-help{margin-top:22px;text-align:center;color:var(--muted);font-size:11px;line-height:1.7}
@media(max-width:700px){.home-sites,.home-options,.home-actions{grid-template-columns:1fr}.home-screen{padding:18px}}
</style>
"""

home = """
<section id="lunarHome" class="home-screen">
 <div class="home-content">
  <div class="home-intro">
   <div class="home-eyebrow">LUNAR SOUTH POLE · MISSION PLANNING</div>
   <h1 class="home-title">PLAN YOUR LUNAR MISSION</h1>
   <p class="home-description">Esplora i siti candidati, scegli il periodo della missione e valuta illuminazione solare e visibilità della Terra.</p>
  </div>
  <div class="home-step">01 / SCEGLI IL SITO DI ATTERRAGGIO</div>
  <div class="home-sites">
   <button type="button" class="home-site selected" data-site="Shackleton" aria-pressed="true"><span class="site-check">✓</span><strong>Shackleton</strong><span>Esplora il cratere e le condizioni del polo sud.</span></button>
   <button type="button" class="home-site" data-site="Connecting Ridge" aria-pressed="false"><span class="site-check">✓</span><strong>Connecting Ridge</strong><span>Valuta un sito candidato lungo il rilievo.</span></button>
   <button type="button" class="home-site" data-site="Nobile" aria-pressed="false"><span class="site-check">✓</span><strong>Nobile</strong><span>Analizza un'altra area del polo sud lunare.</span></button>
  </div>
  <div class="home-step">02 / CONFIGURA IL PERIODO</div>
  <div class="home-options">
   <label>INIZIO MISSIONE<input id="homeDate" type="datetime-local"></label>
   <label>DURATA DELLA MISSIONE · ORE<input id="homeDuration" type="number" min="1" max="720" value="48"></label>
  </div>
  <div class="home-actions">
   <button type="button" id="analyzeMission" class="home-primary">ANALYZE MISSION →</button>
   <button type="button" id="openAdvanced" class="home-secondary">ADVANCED MISSION CONTROL</button>
  </div>
  <div id="homeError" role="status" aria-live="polite"></div>
  <div class="home-help">L'analisi utilizza le effemeridi astronomiche JPL Horizons.<br>Le valutazioni geometriche non costituiscono una certificazione operativa.</div>
 </div>
</section>
"""

js = """
<script>
(() => {
 const body=document.body;
 const date=document.getElementById('homeDate');
 const duration=document.getElementById('homeDuration');
 const error=document.getElementById('homeError');
 let selected='Shackleton';
 if(!date||!duration)return;

 const now=new Date();
 now.setMinutes(now.getMinutes()-now.getTimezoneOffset());
 date.value=now.toISOString().slice(0,16);

 document.querySelectorAll('.home-site').forEach(card=>{
  card.addEventListener('click',()=>{
   selected=card.dataset.site;
   document.querySelectorAll('.home-site').forEach(item=>{
    const active=item===card;
    item.classList.toggle('selected',active);
    item.setAttribute('aria-pressed',String(active));
   });
  });
 });

 function advanced(){
  body.classList.remove('home-mode');
  requestAnimationFrame(()=>window.dispatchEvent(new Event('resize')));
 }

 document.getElementById('openAdvanced').addEventListener('click',advanced);
 document.getElementById('openHome').addEventListener('click',()=>{
  body.classList.add('home-mode');
  error.textContent='';
 });

 document.getElementById('analyzeMission').addEventListener('click',()=>{
  const hours=Number(duration.value);
  if(!date.value){error.textContent='Seleziona data e ora.';date.focus();return}
  if(!Number.isInteger(hours)||hours<1||hours>720){
   error.textContent='La durata deve essere compresa tra 1 e 720 ore.';
   duration.focus();return;
  }
  document.getElementById('site').value=selected;
  document.getElementById('date').value=date.value;
  document.getElementById('duration').value=String(hours);
  advanced();
  document.getElementById('apply').click();
 });
 body.classList.add('home-mode');
})();
</script>
"""

html = html.replace("</head>", css + "\n</head>", 1)
html = html.replace("</header>", '<button type="button" id="openHome">HOME</button>\n</header>', 1)
html = html.replace("<main>", home + "\n<main>", 1)
html = html.replace("</body>", js + "\n</body>", 1)

required = ['id="lunarHome"', 'id="analyzeMission"', 'id="openAdvanced"',
            'id="openHome"', 'data-site="Shackleton"',
            'data-site="Connecting Ridge"', 'data-site="Nobile"']
if not all(x in html for x in required):
    raise SystemExit("Verifica preventiva fallita: file originale invariato.")

p.write_text(html, encoding="utf-8")
print("HOME INSTALLATA")
print("Backup:", backup)
print("main.js e Three.js non modificati.")
