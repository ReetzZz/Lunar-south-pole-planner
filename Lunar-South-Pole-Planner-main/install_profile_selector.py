# Last updated: 2026-11-14
from pathlib import Path
from datetime import datetime
import shutil

p = Path("src/ui_web/index.html")
s = p.read_text(encoding="utf-8")

if 'id="profileHome"' in s:
    raise SystemExit("STOP: selettore profili già installato.")

checks = {
    "vecchia navigazione": 'id="modeToggle"' in s,
    "schermata pubblica": 'id="publicMissionPanel"' in s,
    "canvas lunare": 'id="viewport"' in s,
    "main": s.count("<main>") == 1,
    "script precedente": "setMode(true)" in s,
    "chiusura body": s.count("</body>") == 1,
}
for name, ok in checks.items():
    print(("PASS" if ok else "FAIL") + " - " + name)
if not all(checks.values()):
    raise SystemExit("STOP: struttura inattesa. Nessuna modifica effettuata.")

backup = Path("backups") / f"index-before-profile-selector-{datetime.now():%Y%m%d-%H%M%S}.html"
backup.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(p, backup)

# Pulsante per tornare alla scelta dei profili.
s = s.replace(
    '<button type="button" id="modeToggle">MISSION CONTROL</button>',
    '<button type="button" id="changeProfile">CAMBIA PROFILO</button>',
    1
)

# Schermata iniziale: scelta del profilo.
profile = """
<section id="profileHome" class="profile-home">
 <div class="profile-content">
  <div class="profile-eyebrow">LUNAR SOUTH POLE · EXPLORATION PLATFORM</div>
  <h1>LUNAR SOUTH POLE PLANNER</h1>
  <p class="profile-subtitle">Esplora, comprendi e pianifica le missioni lunari.</p>
  <div class="profile-question">COME VUOI UTILIZZARE LA PIATTAFORMA?</div>

  <div class="profile-cards">
   <button class="profile-card" type="button" data-profile="public">
    <span class="profile-icon">◉</span>
    <strong>PUBBLICO</strong>
    <span>Confronta i siti di atterraggio e le date. Scopri le condizioni di illuminazione e comunicazione.</span>
    <span class="profile-enter">PUBLIC EXPLORER →</span>
   </button>

   <button class="profile-card" type="button" data-profile="educator">
    <span class="profile-icon">⌘</span>
    <strong>EDUCATORE</strong>
    <span>Scopri la scienza lunare, i vincoli ambientali e perché alcuni siti sono più adatti di altri.</span>
    <span class="profile-enter">EDUCATIONAL EXPLORER →</span>
   </button>

   <button class="profile-card" type="button" data-profile="planner">
    <span class="profile-icon">⌖</span>
    <strong>PIANIFICATORE DI MISSIONE</strong>
    <span>Accedi ai dati astronomici, alle analisi e alle simulazioni ingegneristiche avanzate.</span>
    <span class="profile-enter">MISSION CONTROL →</span>
   </button>
  </div>
  <div class="profile-footer">ONE LUNAR PLATFORM · THREE EXPERIENCES</div>
 </div>
</section>
"""

# Schermata educativa iniziale.
education = """
<section id="educatorHome" class="educator-home">
 <div class="educator-content">
  <div class="profile-eyebrow">LUNAR SOUTH POLE · LEARNING CENTER</div>
  <h1>EDUCATIONAL EXPLORER</h1>
  <p>Comprendi le sfide che rendono difficile pianificare una missione al polo sud lunare.</p>

  <div class="lesson-grid">
   <article class="lesson-card">
    <span>01 · ILLUMINAZIONE</span>
    <h2>La luce del Sole</h2>
    <p>Perché alcuni luoghi ricevono luce solare per periodi più lunghi mentre altri rimangono in ombra?</p>
   </article>
   <article class="lesson-card">
    <span>02 · COMUNICAZIONI</span>
    <h2>La Terra all'orizzonte</h2>
    <p>Perché la posizione della Terra rispetto all'orizzonte influenza le comunicazioni dirette?</p>
   </article>
   <article class="lesson-card">
    <span>03 · TERRENO</span>
    <h2>Ombre e morfologia</h2>
    <p>Come pendii, crateri e ostacoli possono influenzare la scelta di una zona di atterraggio?</p>
   </article>
   <article class="lesson-card">
    <span>04 · PIANIFICAZIONE</span>
    <h2>Perché scegliere un sito?</h2>
    <p>Come si bilanciano illuminazione, comunicazioni, sicurezza e obiettivi scientifici?</p>
   </article>
  </div>
  <p class="educator-note">Le spiegazioni e le simulazioni didattiche saranno collegate progressivamente ai dati scientifici della piattaforma.</p>
  <button type="button" class="profile-back" id="educatorBack">← CAMBIA PROFILO</button>
 </div>
</section>
"""

s = s.replace("<main>", profile + "\n" + education + "\n<main>", 1)

css = """
<style>
/* PROFILO UTENTE E NAVIGAZIONE */
body.profile-home main,
body.educator-mode main {display:none!important}
body.profile-home #profileHome {display:flex}
body:not(.profile-home) #profileHome {display:none}
body.educator-mode #educatorHome {display:block}
body:not(.educator-mode) #educatorHome {display:none}

#changeProfile {
 margin-left:16px;padding:10px 15px;
 border:1px solid #327181;border-radius:5px;
 background:#103541;color:#9af5fa;
 font-weight:800;letter-spacing:1px;white-space:nowrap
}
body.profile-home #changeProfile {display:none}

.profile-home {
 min-height:calc(100vh - 65px);
 align-items:center;justify-content:center;
 padding:35px 20px;
 background:radial-gradient(ellipse at 50% 35%,#172d40,#080f19 65%,#060a10)
}
.profile-content {width:100%;max-width:1080px;margin:auto;text-align:center}
.profile-eyebrow {color:var(--cyan);font-size:10px;letter-spacing:3px}
.profile-content h1,.educator-content h1 {
 font-size:clamp(25px,4vw,42px);letter-spacing:2px;margin:15px 0
}
.profile-subtitle {color:#a9bacb;font-size:14px}
.profile-question {margin:48px 0 20px;font-size:11px;font-weight:800;letter-spacing:2px}
.profile-cards {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:17px}
.profile-card {
 display:flex;flex-direction:column;align-items:flex-start;
 min-height:245px;text-align:left;padding:24px;
 border:1px solid #2a4054;border-radius:10px;
 background:linear-gradient(145deg,#122334,#0a131e);
 transition:border-color .18s,transform .18s,background .18s
}
.profile-card:hover {border-color:var(--cyan);background:#132b3b;transform:translateY(-3px)}
.profile-icon {font-size:30px;color:var(--cyan);margin-bottom:22px}
.profile-card strong {font-size:15px;letter-spacing:1px;margin-bottom:13px}
.profile-card>span:nth-of-type(2) {font-size:12px;line-height:1.7;color:#9cafc1}
.profile-enter {margin-top:auto;padding-top:23px;color:var(--cyan);font-size:10px;font-weight:800;letter-spacing:1px}
.profile-footer {margin-top:40px;color:#61788d;font-size:9px;letter-spacing:2px}

.educator-home {
 min-height:calc(100vh - 65px);overflow:auto;
 padding:clamp(25px,5vw,65px);
 background:radial-gradient(ellipse at 50% 0%,#172d40,#080f19 65%)
}
.educator-content {max-width:1050px;margin:auto}
.educator-content>p {color:#a9bacb;line-height:1.7}
.lesson-grid {display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-top:30px}
.lesson-card {padding:23px;border:1px solid #2a4054;border-radius:9px;background:#0d1926}
.lesson-card>span {font-size:9px;color:var(--cyan);letter-spacing:1.5px}
.lesson-card h2 {font-size:18px}
.lesson-card p {font-size:12px;color:#a9bacb;line-height:1.7}
.educator-note {margin:25px 0;color:#8196a9;font-size:11px}
.profile-back {padding:11px 18px;background:#103541;border:1px solid #327181;border-radius:5px;color:#9af5fa}
@media(max-width:760px) {
 .profile-cards,.lesson-grid {grid-template-columns:1fr}
 .profile-card {min-height:190px}
 .profile-question {margin-top:30px}
}
</style>
"""
s = s.replace("</head>", css + "\n</head>", 1)

# Sostituisce il precedente script di navigazione.
end = s.rfind("</body>")
start = s.rfind("<script>", 0, end)
old = s[start:end]

if "setMode(true)" not in old or "publicAnalyze" not in old:
    raise SystemExit("STOP: script precedente non riconosciuto.")

new_script = """
<script>
(() => {
 const body = document.body;
 const changeProfile = document.getElementById('changeProfile');

 function selectProfile(profile) {
  body.classList.remove('profile-home','public-mode','educator-mode');

  if (profile === 'public') {
   body.classList.add('public-mode');
   changeProfile.textContent = 'CAMBIA PROFILO';
   requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
  } else if (profile === 'educator') {
   body.classList.add('educator-mode');
   changeProfile.textContent = 'CAMBIA PROFILO';
  } else if (profile === 'planner') {
   changeProfile.textContent = 'CAMBIA PROFILO';
   requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
  }
 }

 function showProfileHome() {
  body.classList.remove('public-mode','educator-mode');
  body.classList.add('profile-home');
 }

 document.querySelectorAll('[data-profile]').forEach(button => {
  button.addEventListener('click', () => selectProfile(button.dataset.profile));
 });

 changeProfile.addEventListener('click', showProfileHome);
 document.getElementById('educatorBack').addEventListener('click', showProfileHome);

 // All'apertura il sistema chiede sempre chi utilizzerà la piattaforma.
 showProfileHome();
})();
</script>
"""

s = s[:start] + new_script + "\n" + s[end:]

required = [
 'id="profileHome"', 'id="educatorHome"',
 'data-profile="public"', 'data-profile="educator"',
 'data-profile="planner"', 'id="changeProfile"',
 'id="viewport"', 'id="educatorBack"',
 'body.profile-home main'
]
if not all(x in s for x in required):
    raise SystemExit("STOP: verifica finale fallita.")

p.write_text(s, encoding="utf-8")
print("\nINSTALLAZIONE COMPLETATA")
print("Backup:", backup)
print("Tre profili installati.")
print("Canvas lunare conservato.")
print("main.js e backend non modificati.")
