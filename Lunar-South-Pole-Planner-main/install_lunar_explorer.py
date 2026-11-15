# Last updated: 2026-11-14
from pathlib import Path
from datetime import datetime
import shutil
import re

path = Path("src/ui_web/index.html")
html = path.read_text(encoding="utf-8")

if 'id="publicMissionPanel"' in html:
    raise SystemExit("La nuova interfaccia risulta già installata.")

required = [
    '<section class="panel center">',
    '<div class="scene"><canvas id="viewport"></canvas>',
    '<section id="lunarHome"',
    '<button type="button" id="openHome">',
    '</body>'
]
for anchor in required:
    if html.count(anchor) != 1:
        raise SystemExit(f"STOP: struttura non riconosciuta: {anchor}")

backup = Path("backups") / (
    f"index-before-lunar-explorer-{datetime.now():%Y%m%d-%H%M%S}.html"
)
backup.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(path, backup)

# Rimuove la precedente Home separata.
html = re.sub(
    r'\s*<section id="lunarHome".*?</section>\s*(?=<main>)',
    '\n',
    html,
    count=1,
    flags=re.S
)

# Sostituisce il vecchio pulsante HOME con un selettore di modalità.
html = html.replace(
    '<button type="button" id="openHome">HOME</button>',
    '<button type="button" id="modeToggle">MISSION CONTROL</button>',
    1
)

# Inserisce i controlli pubblici nella scena 3D esistente.
scene_anchor = '<div class="scene"><canvas id="viewport"></canvas>'
public_panel = """
<div id="publicMissionPanel" class="public-ui">
 <div class="public-eyebrow">LUNAR SOUTH POLE EXPLORER</div>
 <h2>Esplora la Luna</h2>
 <p>Seleziona un sito per scoprire le condizioni della regione lunare.</p>

 <div class="public-label">SITI CANDIDATI</div>
 <div class="public-sites">
  <button type="button" class="public-site selected" data-public-site="Shackleton" aria-pressed="true">
   <strong>Shackleton</strong><span>Regione del polo sud</span>
  </button>
  <button type="button" class="public-site" data-public-site="Connecting Ridge" aria-pressed="false">
   <strong>Connecting Ridge</strong><span>Rilievo lunare</span>
  </button>
  <button type="button" class="public-site" data-public-site="Nobile" aria-pressed="false">
   <strong>Nobile</strong><span>Area del polo sud</span>
  </button>
 </div>

 <div class="public-facts">
  <div><span>LUCE SOLARE</span><strong>Analisi astronomica</strong></div>
  <div><span>VISIBILITÀ DELLA TERRA</span><strong>Analisi geometrica</strong></div>
 </div>

 <button type="button" id="publicAnalyze" class="public-analyze">ANALIZZA QUESTO SITO</button>
 <button type="button" id="educationToggle" class="education-toggle">SCOPRI COME FUNZIONA</button>
 <div id="educationText" hidden>
  La luce solare può alimentare i sistemi di una missione. La visibilità geometrica della Terra è un elemento importante per pianificare le comunicazioni. Le condizioni cambiano con la posizione e il tempo.
 </div>
 <div id="publicMessage" role="status" aria-live="polite"></div>
</div>
"""
html = html.replace(scene_anchor, scene_anchor + '\n' + public_panel, 1)

# CSS: la modalità pubblica usa il viewport esistente a piena area.
css = """
<style>
/* LUNAR EXPLORER - modalità pubblica */
#modeToggle {
 margin-left:16px;padding:10px 15px;border:1px solid #327181;
 border-radius:5px;background:#103541;color:#9af5fa;
 font-weight:800;letter-spacing:1px;white-space:nowrap
}
body.public-mode main {
 height:calc(100vh - 65px);
 padding:10px;display:grid;grid-template-columns:minmax(0,1fr);
 grid-template-rows:minmax(0,1fr);gap:0
}
body.public-mode .left,
body.public-mode .right,
body.public-mode .bottom,
body.public-mode #missionSplitter {display:none!important}
body.public-mode .center {
 grid-column:1;grid-row:1;min-height:0;display:flex;flex-direction:column
}
body.public-mode .center .panelhead {flex:0 0 42px}
body.public-mode .center .scene {
 flex:1;height:auto;min-height:0;position:relative
}
body.public-mode .overlay {z-index:1}
.public-ui {
 position:absolute;z-index:3;right:20px;top:18px;
 width:min(310px,calc(100% - 30px));max-height:calc(100% - 36px);
 overflow:auto;padding:19px;border:1px solid #36536a;border-radius:10px;
 background:rgba(7,16,27,.94);box-shadow:0 12px 40px #0009;
 backdrop-filter:blur(12px)
}
.public-eyebrow {font-size:9px;letter-spacing:2px;color:var(--cyan)}
.public-ui h2 {font-size:22px;margin:10px 0}
.public-ui p {font-size:11px;line-height:1.6;color:#a9bacb}
.public-label {font-size:9px;letter-spacing:1.5px;color:#91a8bb;margin:17px 0 8px}
.public-sites {display:grid;gap:7px}
.public-site {
 width:100%;padding:11px;text-align:left;border:1px solid #2b4053;
 border-radius:6px;background:#101e2d
}
.public-site strong,.public-site span {display:block}
.public-site strong {font-size:12px}
.public-site span {font-size:10px;color:#91a8bb;margin-top:4px}
.public-site.selected {border-color:var(--cyan);background:#12303b}
.public-facts {display:grid;gap:8px;margin-top:15px}
.public-facts div {padding:10px;border:1px solid #263b50;border-radius:5px;background:#0c1926}
.public-facts span,.public-facts strong {display:block}
.public-facts span {font-size:9px;color:#91a8bb;letter-spacing:1px}
.public-facts strong {font-size:11px;margin-top:5px}
.public-analyze,.education-toggle {
 width:100%;padding:12px;margin-top:12px;border-radius:5px;
 font-size:10px;font-weight:800;letter-spacing:1px
}
.public-analyze {background:#103541;border:1px solid #327181;color:#9af5fa}
.education-toggle {background:#101e2d;border:1px solid #2b4053}
#educationText {font-size:11px;line-height:1.7;color:#b4c6d7;margin-top:12px}
#publicMessage {font-size:10px;color:var(--amber);margin-top:8px}
body:not(.public-mode) .public-ui {display:none}
@media(max-width:700px) {
 body.public-mode main {padding:5px}
 .public-ui {right:10px;top:10px;width:min(270px,calc(100% - 20px));padding:13px}
 .public-ui h2 {font-size:18px}
}
</style>
"""
html = html.replace("</head>", css + "\n</head>", 1)

# Sostituisce soltanto il vecchio script della Home in fondo al documento.
body_pos = html.rfind("</body>")
script_start = html.rfind("<script>", 0, body_pos)
if script_start < 0:
    raise SystemExit("STOP: script finale non trovato.")

old_script = html[script_start:body_pos]
if "const body=document.body" not in old_script or "analyzeMission" not in old_script:
    raise SystemExit("STOP: lo script finale non corrisponde alla vecchia Home.")

new_script = """
<script>
(() => {
 const body = document.body;
 const toggle = document.getElementById('modeToggle');
 const site = document.getElementById('site');
 const message = document.getElementById('publicMessage');

 if (!toggle || !site) return;

 function setMode(publicMode) {
  body.classList.toggle('public-mode', publicMode);
  toggle.textContent = publicMode ? 'MISSION CONTROL' : 'PUBLIC VIEW';
  requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
 }

 toggle.addEventListener('click', () => {
  setMode(!body.classList.contains('public-mode'));
 });

 document.querySelectorAll('.public-site').forEach(button => {
  button.addEventListener('click', () => {
   document.querySelectorAll('.public-site').forEach(item => {
    const active = item === button;
    item.classList.toggle('selected', active);
    item.setAttribute('aria-pressed', String(active));
   });
   site.value = button.dataset.publicSite;
   message.textContent = 'Sito selezionato: ' + site.value;
  });
 });

 document.getElementById('publicAnalyze').addEventListener('click', () => {
  site.dispatchEvent(new Event('change', {bubbles:true}));
  document.getElementById('apply').click();
  message.textContent = 'Richiesta di analisi inviata. Consultare i risultati in Mission Control.';
 });

 document.getElementById('educationToggle').addEventListener('click', event => {
  const explanation = document.getElementById('educationText');
  explanation.hidden = !explanation.hidden;
  event.currentTarget.textContent = explanation.hidden
   ? 'SCOPRI COME FUNZIONA' : 'NASCONDI SPIEGAZIONE';
 });

 setMode(true);
})();
</script>
"""
html = html[:script_start] + new_script + "\n" + html[body_pos:]

checks = [
    'id="viewport"' in html,
    'id="publicMissionPanel"' in html,
    'id="modeToggle"' in html,
    'data-public-site="Shackleton"' in html,
    'data-public-site="Connecting Ridge"' in html,
    'data-public-site="Nobile"' in html,
    'id="publicAnalyze"' in html,
    'id="educationToggle"' in html,
    'body.public-mode main' in html,
    'id="lunarHome"' not in html,
]
if not all(checks):
    raise SystemExit("STOP: verifica finale fallita. Ripristinare il backup se necessario.")

path.write_text(html, encoding="utf-8")
print("LUNAR EXPLORER INSTALLATO")
print("Backup:", backup)
print("Canvas Three.js conservato:", 'id="viewport"' in html)
print("main.js non modificato.")
