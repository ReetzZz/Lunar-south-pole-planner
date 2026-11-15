from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "src" / "ui_web" / "index.html"
CONFIG = ROOT / "src" / "ui_web" / "mission_login_config.js"

if not HTML.exists():
    raise SystemExit(
        "index.html non trovato. Metti questo installer nella cartella principale "
        "del repository e rieseguilo."
    )

html = HTML.read_text(encoding="utf-8")

if 'id="missionLogin"' in html:
    raise SystemExit("STOP: la schermata di login risulta già installata.")

checks = {
    "selettore profili": 'id="profileHome"' in html,
    "profilo planner": 'data-profile="planner"' in html,
    "funzione selectProfile": "function selectProfile(profile)" in html,
    "ramo planner": "} else if (profile === 'planner') {" in html,
    "schermata educatore": 'id="educatorHome"' in html,
    "chiusura head": html.count("</head>") == 1,
}
for label, ok in checks.items():
    print(("PASS" if ok else "FAIL") + " - " + label)
if not all(checks.values()):
    raise SystemExit("STOP: struttura diversa da quella attesa. Nessuna modifica effettuata.")

backup_dir = ROOT / "backups"
backup_dir.mkdir(exist_ok=True)
backup = backup_dir / f"index-before-mission-login-{datetime.now():%Y%m%d-%H%M%S}.html"
shutil.copy2(HTML, backup)

login_markup = r"""
<section id="missionLogin" class="mission-login" aria-labelledby="missionLoginTitle">
 <form class="login-card" id="missionLoginForm">
  <div class="profile-eyebrow">LUNAR SOUTH POLE · RESTRICTED AREA</div>
  <div class="login-symbol">◈</div>
  <h1 id="missionLoginTitle">MISSION CONTROL ACCESS</h1>
  <p class="login-description">Accesso riservato al personale autorizzato.</p>

  <label class="login-label" for="missionUsername">OPERATOR ID</label>
  <input id="missionUsername" name="username" type="text"
         autocomplete="username" placeholder="Inserisci il tuo identificativo"
         required>

  <label class="login-label" for="missionPassword">PASSWORD</label>
  <input id="missionPassword" name="password" type="password"
         autocomplete="current-password" placeholder="Inserisci la password"
         required>

  <button class="login-submit" type="submit">AUTHENTICATE →</button>
  <div id="missionLoginMessage" role="status" aria-live="polite"></div>
  <button class="profile-back login-back" id="loginBack" type="button">
   ← TORNA ALLA SCELTA PROFILO
  </button>
 </form>
</section>
"""

login_css = r"""
<style>
/* MISSION CONTROL LOGIN */
body.planner-login main,
body.planner-login #educatorHome {display:none!important}
body.planner-login #missionLogin {display:flex}
body:not(.planner-login) #missionLogin {display:none}
body.planner-login #changeProfile {display:none}

.mission-login {
 min-height:calc(100vh - 65px);
 align-items:center;justify-content:center;
 padding:28px 18px;
 background:radial-gradient(ellipse at 50% 35%,#172d40,#080f19 65%,#060a10);
}
.login-card {
 width:min(100%,420px);
 padding:34px;
 border:1px solid #2a4054;
 border-radius:10px;
 background:linear-gradient(145deg,#122334,#0a131e);
 box-shadow:0 18px 55px #0006;
}
.login-card h1 {
 margin:12px 0 8px;
 font-size:clamp(21px,3vw,29px);
 letter-spacing:1.5px;
}
.login-symbol {font-size:35px;color:var(--cyan);margin-top:24px}
.login-description {color:#9cafc1;font-size:12px;line-height:1.6;margin-bottom:25px}
.login-label {
 display:block;margin:17px 0 7px;
 color:#9cafc1;font-size:10px;letter-spacing:1.3px;font-weight:700;
}
.login-card input {width:100%;padding:12px;border:1px solid #2a4054;background:#08121d}
.login-card input:focus {outline:1px solid var(--cyan);border-color:var(--cyan)}
.login-submit {
 width:100%;margin-top:23px;padding:13px;
 border:1px solid #327181;border-radius:5px;
 background:#103541;color:#9af5fa;font-weight:800;letter-spacing:1px;
}
#missionLoginMessage {min-height:20px;margin-top:12px;font-size:11px;color:var(--amber)}
.login-back {width:100%;margin-top:9px}
</style>
"""

# Inserisce il login subito dopo la selezione dei profili.
profile_end = """ </section>

<section id="educatorHome" """
if profile_end not in html:
    raise SystemExit("STOP: non trovo il punto esatto tra selettore profili ed educatore.")
html = html.replace(
    profile_end,
    " </section>\n\n" + login_markup + "\n<section id=\"educatorHome\" ",
    1
)

# Aggiunge lo stile del login.
html = html.replace("</head>", login_css + "\n</head>", 1)

# Carica la configurazione demo separata, così le credenziali non sono nel file HTML.
config_tag = '<script src="/src/ui_web/mission_login_config.js"></script>\n'
anchor = '<script type="module" src="/src/ui_web/main.js"></script>'
if anchor not in html:
    raise SystemExit("STOP: non trovo il caricamento di main.js.")
html = html.replace(anchor, config_tag + anchor, 1)

old_planner = """} else if (profile === 'planner') {
    changeProfile.textContent = 'CAMBIA PROFILO';
    requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
   }"""
new_planner = """} else if (profile === 'planner') {
    body.classList.add('planner-login');
    changeProfile.textContent = 'CAMBIA PROFILO';
   }"""
if old_planner not in html:
    raise SystemExit("STOP: il ramo planner non corrisponde a quello atteso.")
html = html.replace(old_planner, new_planner, 1)

# Collega il form e gestisce l'accesso dimostrativo.
old_tail = """  changeProfile.addEventListener('click', showProfileHome);
  document.getElementById('educatorBack').addEventListener('click', showProfileHome);
  // All'apertura il sistema chiede sempre chi utilizzerà la piattaforma.
  showProfileHome();"""
new_tail = """  changeProfile.addEventListener('click', showProfileHome);
  document.getElementById('educatorBack').addEventListener('click', showProfileHome);
  document.getElementById('loginBack').addEventListener('click', showProfileHome);

  const loginForm = document.getElementById('missionLoginForm');
  const loginMessage = document.getElementById('missionLoginMessage');

  loginForm.addEventListener('submit', event => {
   event.preventDefault();
   const username = document.getElementById('missionUsername').value.trim();
   const password = document.getElementById('missionPassword').value;
   const users = window.MISSION_LOGIN_USERS || [];

   const valid = users.some(user =>
    user.username === username && user.password === password
   );

   if (!valid) {
    loginMessage.textContent = 'Credenziali non valide. Verifica ID e password.';
    document.getElementById('missionPassword').value = '';
    return;
   }

   loginMessage.textContent = '';
   body.classList.remove('planner-login');
   requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
  });

  // All'apertura il sistema chiede sempre chi utilizzerà la piattaforma.
  showProfileHome();"""
if old_tail not in html:
    raise SystemExit("STOP: non trovo il punto esatto per collegare il form.")
html = html.replace(old_tail, new_tail, 1)

# La configurazione viene creata solo se non esiste già.
if not CONFIG.exists():
    CONFIG.write_text(
        """// CONFIGURAZIONE DIMOSTRATIVA DEL LOGIN.
// Cambia queste credenziali prima di provare la schermata.
// ATTENZIONE: essendo un sito statico, queste credenziali sono visibili
// nel browser e NON costituiscono autenticazione sicura per un sito pubblico.
window.MISSION_LOGIN_USERS = [
  { username: "operator", password: "LunarDemo2026!" }
];
""",
        encoding="utf-8"
    )

HTML.write_text(html, encoding="utf-8")

print("\\nLOGIN INSTALLATO.")
print("File modificato:", HTML)
print("Configurazione credenziali:", CONFIG)
print("Backup originale:", backup)
print("\\nCredenziali demo:")
print("  ID:       operator")
print("  Password: LunarDemo2026!")
print("\\nNOTA: login dimostrativo lato browser, non adatto a proteggere dati reali.")
print("Per autenticazione reale serve un backend con verifica password lato server.")
