// Last updated: 2026-11-14
import * as THREE from '/src/ui_web/node_modules/three/build/three.module.js';
import { GLTFLoader } from '/src/ui_web/node_modules/three/examples/jsm/loaders/GLTFLoader.js';

const canvas = document.querySelector('#viewport');
const message = document.querySelector('#message');
const scene = new THREE.Scene();
scene.background = new THREE.Color('#070d16');

const camera = new THREE.PerspectiveCamera(38, 1, 0.01, 1000);
const INITIAL_CAMERA_Z = 9.2;
camera.position.set(0, 0.3, INITIAL_CAMERA_Z);

const renderer = new THREE.WebGLRenderer({canvas, antialias:true, alpha:false});
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.10;
document.querySelector('#webglStatus').textContent = 'READY';

scene.add(new THREE.HemisphereLight(0xa8c8e8, 0x151a25, 1.15));
const sun = new THREE.DirectionalLight(0xfff0dc, 3.0);
sun.position.set(-4, 3, 5);
scene.add(sun);
const rim = new THREE.DirectionalLight(0x3a91c7, 0.25);
rim.position.set(4, -1, -4);
scene.add(rim);

const stars = new THREE.BufferGeometry();
const positions = [];
for (let i=0;i<1800;i++) {
  const r=30+Math.random()*100;
  const a=Math.random()*Math.PI*2, z=Math.random()*2-1;
  const q=Math.sqrt(1-z*z);
  positions.push(r*q*Math.cos(a),r*z,r*q*Math.sin(a));
}
stars.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
scene.add(new THREE.Points(stars,new THREE.PointsMaterial({color:0x9cb9d7,size:0.055,transparent:true,opacity:0.7})));

const root = new THREE.Group();
scene.add(root);
let moon = null;
let dragging=false, lastX=0,lastY=0, targetRotX=0.12,targetRotY=0.3;
const loader = new GLTFLoader();
const modelUrl = '/data/terrain/global/Moon_NASA_LRO_8k_Topo_Small.glb';

loader.load(modelUrl, gltf => {
  moon = gltf.scene;
  const box = new THREE.Box3().setFromObject(moon);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const extent = Math.max(size.x,size.y,size.z);
  if (!extent) throw new Error('Il modello lunare ha dimensioni nulle');
  moon.scale.setScalar(4.5/extent);
  moon.position.set(-center.x*moon.scale.x,-center.y*moon.scale.y,-center.z*moon.scale.z);
  moon.traverse(obj => {
    if (obj.isMesh) {
      obj.castShadow = false;
      obj.receiveShadow = true;
      if (obj.material) {
        obj.material.side = THREE.FrontSide;

        const materials = Array.isArray(obj.material)
          ? obj.material
          : [obj.material];

        for (const material of materials) {
          if ('roughness' in material) material.roughness = 0.94;

          // Filtraggio più uniforme alle diverse distanze.
          for (const key of [
            'map',
            'normalMap',
            'roughnessMap',
            'metalnessMap',
            'aoMap',
            'emissiveMap'
          ]) {
            const texture = material[key];
            if (!texture) continue;

            texture.minFilter = THREE.LinearMipmapLinearFilter;
            texture.magFilter = THREE.LinearFilter;
            texture.generateMipmaps = true;
            texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
            texture.needsUpdate = true;
          }

          material.needsUpdate = true;
        }
      }
    }
  });
  root.add(moon);
  document.querySelector('#modelStatus').textContent='LOADED';
  document.querySelector('#modelStatus').className='good';
  message.textContent='NASA lunar model loaded. Drag to rotate; scroll to zoom.';
}, undefined, err => {
  console.error(err);
  document.querySelector('#modelStatus').textContent='LOAD ERROR';
  document.querySelector('#modelStatus').className='warn';
  message.textContent='Model failed to load. Check the browser console and GLB path.';
});

function resize(){
 const w=canvas.clientWidth,h=canvas.clientHeight;
 if(!w||!h)return;
 renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(canvas);
resize();

canvas.addEventListener('pointerdown',e=>{dragging=true;lastX=e.clientX;lastY=e.clientY;canvas.setPointerCapture(e.pointerId)});
canvas.addEventListener('pointermove',e=>{
 if(!dragging)return;
 targetRotY+=(e.clientX-lastX)*0.008;
 targetRotX+=(e.clientY-lastY)*0.008;
 targetRotX=Math.max(-1.4,Math.min(1.4,targetRotX));
 lastX=e.clientX;lastY=e.clientY;
});
canvas.addEventListener('pointerup',()=>dragging=false);
canvas.addEventListener('pointercancel',()=>dragging=false);
canvas.addEventListener('dblclick',()=>{targetRotX=.12;targetRotY=.3;camera.position.set(0,.3,INITIAL_CAMERA_Z)});
canvas.addEventListener('wheel',e=>{
 e.preventDefault();
 camera.position.z=Math.max(4.5,Math.min(15,camera.position.z+e.deltaY*.008));
},{passive:false});

function animate(){
 requestAnimationFrame(animate);

 // Rotazione automatica lenta, simile a una ripresa orbitale.
 // Quando l'utente trascina la Luna, la rotazione manuale prevale.
 if (!dragging) {
   targetRotY += 0.0007;
 }

 root.rotation.x += (targetRotX-root.rotation.x)*.04;
 root.rotation.y += (targetRotY-root.rotation.y)*.04;

 renderer.render(scene,camera);
}
animate();

const sites = {
 'Shackleton':[-89.7668,-171.87],
 'Connecting Ridge':[-89.4632,-137.49],
 'Nobile':[-85.4381,37.36667]
};
const site = document.querySelector('#site');
function update(){
 const name=site.value;
 const [lat,lon]=sites[name] || sites.Shackleton;
 document.querySelector('#targetName').textContent=name;
 document.querySelector('#siteLabel').textContent='TARGET: '+name.toUpperCase();
 document.querySelector('#coords').textContent=`${lat.toFixed(2)}°, ${lon.toFixed(2)}°`;
 const duration=Math.max(1,Math.min(720,Number(document.querySelector('#duration').value)||48));
 document.querySelector('#durationValue').textContent=duration;
 document.querySelector('#scienceValue').textContent=document.querySelector('#science').value+' / 5';
 document.querySelector('#engineeringValue').textContent=document.querySelector('#engineering').value+' / 5';
 document.querySelector('#elevationValue').textContent=document.querySelector('#elevation').value+'°';
 const earthValue=document.querySelector('#earthElevationValue');
 if(earthValue) earthValue.textContent=document.querySelector('#earthElevation').value+'°';
}
document.querySelector('#apply').addEventListener('click',update);
site.addEventListener('change',update);
document.querySelector('#reset').addEventListener('click',()=>{
 targetRotX=.12;targetRotY=.3;camera.position.set(0,.3,INITIAL_CAMERA_Z);
});
const dateInput=document.querySelector('#date');
const now=new Date();now.setMinutes(now.getMinutes()-now.getTimezoneOffset());
dateInput.value=now.toISOString().slice(0,16);
update();

function drawChart(id,variant){
 const c=document.getElementById(id),ctx=c.getContext('2d');
 const dpr=window.devicePixelRatio||1;
 const w=c.clientWidth,h=c.clientHeight;
 c.width=w*dpr;c.height=h*dpr;ctx.scale(dpr,dpr);
 ctx.clearRect(0,0,w,h);
 ctx.strokeStyle='#203141';ctx.lineWidth=1;
 for(let i=1;i<5;i++){ctx.beginPath();ctx.moveTo(0,h*i/5);ctx.lineTo(w,h*i/5);ctx.stroke()}
 ctx.strokeStyle=variant?'#f4b95f':'#5be7f5';ctx.lineWidth=2;ctx.beginPath();
 for(let x=0;x<w;x++){
  const t=x/w;
  const y=variant?h*(.48+.17*Math.sin(t*13)+.08*Math.sin(t*39)):h*(.55-.22*Math.sin(t*6)-.09*Math.cos(t*18));
  if(x===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
 }
 ctx.stroke();
 ctx.fillStyle='#8295a9';ctx.font='9px sans-serif';ctx.fillText('Illustrative visualization — not measured data',4,h-3);
}
function charts(){drawChart('chart1',0);drawChart('chart2',1)}
// I grafici vengono disegnati esclusivamente con campioni JPL reali.


// ===== REAL JPL HORIZONS DATA =====
const chart1 = document.querySelector('#chart1');
const chart2 = document.querySelector('#chart2');
const applyButton = document.querySelector('#apply');
const liveStatus = document.querySelector('.right .metric:last-child .statusrow:last-of-type span:last-child');
const chartNames = document.querySelectorAll('.graphname');

if (chartNames.length >= 2) {
  chartNames[0].textContent = 'SOLAR ELEVATION · JPL HORIZONS';
  chartNames[1].textContent = 'EARTH ELEVATION · OPERATIONAL WINDOWS';
}

if (liveStatus) liveStatus.textContent = 'READY';

function drawEphemerisChart(canvas, observations, field, threshold, color, windows = []) {
  const ctx = canvas.getContext('2d');
  const cssW = Math.max(100, canvas.clientWidth);
  const cssH = Math.max(80, canvas.clientHeight);
  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  const left = 34, right = 8, top = 8, bottom = 22;
  const w = cssW - left - right, h = cssH - top - bottom;
  const values = observations.map(o => o[field]).filter(Number.isFinite);
  if (values.length < 2) {
    ctx.fillStyle = '#8295a9';
    ctx.font = '11px sans-serif';
    ctx.fillText('Dati insufficienti', left, top + 20);
    return;
  }

  const minY = Math.min(-10, Math.floor(Math.min(...values) / 10) * 10);
  const maxY = Math.max(10, Math.ceil(Math.max(...values) / 10) * 10);
  const x = i => left + i * w / (observations.length - 1);
  const y = v => top + (maxY - v) * h / (maxY - minY);

  // Evidenzia gli intervalli che soddisfano entrambe le soglie.
  for (const win of windows) {
    const start = observations.findIndex(o => o.time_utc === win.start_utc);
    const end = observations.findIndex(o => o.time_utc === win.end_utc);
    if (start >= 0 && end >= start) {
      ctx.fillStyle = 'rgba(76, 214, 164, 0.10)';
      ctx.fillRect(x(start), top, Math.max(2, x(end) - x(start)), h);
    }
  }

  ctx.font = '9px sans-serif';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (let tick = Math.ceil(minY / 30) * 30; tick <= maxY; tick += 30) {
    const yy = y(tick);
    ctx.strokeStyle = '#1c2c3c';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(left, yy); ctx.lineTo(cssW-right, yy); ctx.stroke();
    ctx.fillStyle = '#8295a9';
    ctx.fillText(`${tick}°`, left - 5, yy);
  }

  if (Number.isFinite(threshold) && threshold >= minY && threshold <= maxY) {
    ctx.save();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = '#f4b95f';
    ctx.beginPath(); ctx.moveTo(left, y(threshold)); ctx.lineTo(cssW-right, y(threshold)); ctx.stroke();
    ctx.restore();
  }

  ctx.strokeStyle = color;
  ctx.lineWidth = 1.8;
  ctx.lineJoin = 'round';
  ctx.beginPath();
  observations.forEach((o, i) => {
    const v = o[field];
    if (!Number.isFinite(v)) return;
    if (i === 0) ctx.moveTo(x(i), y(v));
    else ctx.lineTo(x(i), y(v));
  });
  ctx.stroke();

  ctx.fillStyle = '#8295a9';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
  ctx.fillText(observations[0].time_utc.slice(11, 16) + ' UTC', left, cssH - 5);
  ctx.textAlign = 'right';
  ctx.fillText(observations[observations.length - 1].time_utc.slice(11, 16) + ' UTC', cssW-right, cssH-5);
}



function calculateMissionAnalytics(observations, thresholds, windows) {
  const values = (field) => observations
    .map(o => Number(o[field]))
    .filter(Number.isFinite);

  const sun = values('sun_elevation_deg');
  const earth = values('earth_elevation_deg');
  const minSun = Number(thresholds.sun_elevation_deg);
  const minEarth = Number(thresholds.earth_elevation_deg);

  const valid = observations.filter(o =>
    Number.isFinite(Number(o.sun_elevation_deg)) &&
    Number.isFinite(Number(o.earth_elevation_deg))
  );

  const sunPass = valid.filter(o => Number(o.sun_elevation_deg) >= minSun).length;
  const earthPass = valid.filter(o => Number(o.earth_elevation_deg) >= minEarth).length;
  const bothPass = valid.filter(o =>
    Number(o.sun_elevation_deg) >= minSun &&
    Number(o.earth_elevation_deg) >= minEarth
  ).length;

  const stats = arr => arr.length ? {
    min: Math.min(...arr),
    max: Math.max(...arr),
    mean: arr.reduce((a, b) => a + b, 0) / arr.length,
    samples: arr.length
  } : null;

  const pct = n => valid.length ? 100 * n / valid.length : 0;

  const windowSpans = windows.map(w => {
    if (Number.isFinite(Number(w.sampled_span_hours))) {
      return Number(w.sampled_span_hours);
    }
    return Math.max(0, Number(w.duration_samples || 1) - 1);
  });

  const totalWindowHours = windowSpans.reduce((a, b) => a + b, 0);
  let diagnosis;

  if (!valid.length) {
    diagnosis = 'Campioni validi insufficienti per formulare una diagnosi.';
  } else if (bothPass > 0) {
    diagnosis = `${bothPass} campioni soddisfano simultaneamente entrambe le soglie.`;
  } else if (sunPass === 0 && earthPass === 0) {
    diagnosis = 'Nessuna condizione soddisfatta: sia il Sole sia la Terra restano sotto le rispettive soglie.';
  } else if (sunPass === 0) {
    diagnosis = 'Vincolo solare limitante: nessun campione raggiunge la soglia del Sole.';
  } else if (earthPass === 0) {
    diagnosis = 'Vincolo terrestre limitante: nessun campione raggiunge la soglia della Terra.';
  } else {
    diagnosis = 'Sole e Terra superano le soglie separatamente, ma non negli stessi campioni.';
  }

  return {
    sample_count: observations.length,
    valid_sample_count: valid.length,
    thresholds_deg: { sun: minSun, earth: minEarth },
    sun: { ...stats(sun), passing_samples: sunPass, passing_percent: pct(sunPass) },
    earth: { ...stats(earth), passing_samples: earthPass, passing_percent: pct(earthPass) },
    simultaneous: {
      passing_samples: bothPass,
      passing_percent: pct(bothPass)
    },
    operational_windows: {
      count: windows.length,
      total_sampled_span_hours: totalWindowHours,
      spans_hours: windowSpans,
      earliest_start_utc: windows.length ? windows[0].start_utc : null
    },
    diagnosis
  };
}

function renderMissionAnalytics(a) {
  const put = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  };
  const fmt = v => Number.isFinite(v) ? `${v.toFixed(2)}°` : '—';
  const statsText = s => s
    ? `min ${fmt(s.min)} · max ${fmt(s.max)} · media ${fmt(s.mean)}`
    : 'Dati non disponibili';

  const pct = value => Number.isFinite(value) ? `${value.toFixed(1)}%` : 'N/D';
  const count = value => Number.isFinite(value) ? value : 0;
  const valid = count(a.valid_sample_count);
  const sun = a.sun || {};
  const earth = a.earth || {};
  const simultaneous = a.simultaneous || {};
  const windows = a.operational_windows || {};

  put('analyticsStatus', `${valid}/${count(a.sample_count)} VALID SAMPLES`);
  put('sunStats', statsText(sun));
  put('earthStats', statsText(earth));
  put('sunPass', `${count(sun.passing_samples)}/${valid} campioni · ${pct(sun.passing_percent)} sopra soglia`);
  put('earthPass', `${count(earth.passing_samples)}/${valid} campioni · ${pct(earth.passing_percent)} sopra soglia`);
  put('combinedPass', pct(simultaneous.passing_percent));
  put('combinedCount', `${count(simultaneous.passing_samples)}/${valid} campioni simultanei`);
  put('analyticsWindowCount', String(count(windows.count)));
  put('analyticsWindowSpan', `${Number.isFinite(windows.total_sampled_span_hours) ? windows.total_sampled_span_hours.toFixed(1) : '—'} h di intervallo campionato totale`);
  put('analyticsDiagnosis', a.diagnosis || 'Diagnosi non disponibile.');
}

function renderOperationalWindows(data, observations, windows) {
  const tbody = document.querySelector('#operationalWindows');
  const count = document.querySelector('#windowCount');
  const notice = document.querySelector('#windowNotice');
  if (!tbody || !count || !notice) return;

  count.textContent = `${windows.length} WINDOWS`;
  notice.textContent = data.notice ||
    'Finestre geometriche preliminari: non verificano ostacoli, budget radio o sicurezza.';

  const fmtTime = value => {
    const d = new Date(value);
    return Number.isNaN(d.getTime())
      ? '—'
      : d.toISOString().slice(0, 16).replace('T', ' ');
  };

  if (!windows.length) {
    tbody.innerHTML =
      '<tr><td colspan="7" class="empty-windows">' +
      'Nessuna finestra soddisfa contemporaneamente entrambe le soglie nel periodo selezionato.' +
      '</td></tr>';
    return;
  }

  tbody.replaceChildren();
  windows.forEach((win, index) => {
    const tr = document.createElement('tr');
    const values = [
      String(index + 1),
      fmtTime(win.start_utc),
      fmtTime(win.end_utc),
      `${win.sampled_span_hours ?? Math.max(0, win.duration_samples - 1)} h · ${win.duration_samples} campioni`,
      `${Number(win.min_sun_elevation_deg).toFixed(2)}°`,
      `${Number(win.min_earth_elevation_deg).toFixed(2)}°`,
      'GEOMETRIC OK'
    ];

    values.forEach((value, i) => {
      const td = document.createElement('td');
      td.textContent = value;
      if (i === 6) td.className = 'window-ok';
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

async function updateEphemerides() {
  if (applyButton.disabled) return;

  const site = document.querySelector('#site').value;
  const dateInput = document.querySelector('#date');
  const hours = Number(document.querySelector('#duration').value);
  const minSun = Number(document.querySelector('#elevation').value);
  const science = Number(document.querySelector('#science').value);
  const engineering = Number(document.querySelector('#engineering').value);
  const minEarth = Number(document.querySelector('#earthElevation').value);

  if (!dateInput.value) {
    message.textContent = 'Seleziona data e ora di inizio UTC.';
    dateInput.focus();
    return;
  }
  if (!Number.isInteger(hours) || hours < 1 || hours > 720 ||
      !Number.isFinite(minSun) || minSun < -90 || minSun > 90 ||
      !Number.isFinite(minEarth) || minEarth < -90 || minEarth > 90 ||
      !Number.isInteger(science) || science < 1 || science > 5 ||
      !Number.isInteger(engineering) || engineering < 1 || engineering > 5) {
    message.textContent = 'Controlla durata, soglia e priorità: valori fuori intervallo.';
    return;
  }

  const params = new URLSearchParams({
    site, start: dateInput.value, hours: String(hours),
    min_sun: String(minSun), min_earth: String(minEarth)
  });

  applyButton.disabled = true;
  applyButton.textContent = 'CALCULATING…';
  message.textContent = 'Richiesta effemeridi NASA/JPL Horizons…';
  if (liveStatus) liveStatus.textContent = 'CALCULATING';

  try {
    const response = await fetch(`/api/ephemerides?${params.toString()}`, {cache: 'no-store'});
    const data = await response.json();
    if (!response.ok || data.status !== 'ok') {
      throw new Error(data.error || `HTTP ${response.status}`);
    }

    const observations = data.observations || [];
    if (observations.length < 2) throw new Error('Horizons ha restituito meno di due osservazioni.');

    drawEphemerisChart(chart1, observations, 'sun_elevation_deg',
      data.thresholds.sun_elevation_deg, '#5be7f5', data.windows);
    drawEphemerisChart(chart2, observations, 'earth_elevation_deg',
      data.thresholds.earth_elevation_deg, '#f4b95f', data.windows);

    document.querySelector('#targetName').textContent = data.site;
    document.querySelector('#coords').textContent =
      `${data.latitude_deg.toFixed(4)}°, ${data.longitude_east_deg.toFixed(4)}°`;
    document.querySelector('#durationValue').textContent = data.duration_hours;
    document.querySelector('#scienceValue').textContent = `${science} / 5`;
    document.querySelector('#engineeringValue').textContent = `${engineering} / 5`;
    document.querySelector('#elevationValue').textContent = `${minSun}°`;
    document.querySelector('#earthElevationValue').textContent = `${minEarth}°`;
    document.querySelector('#siteLabel').textContent = `TARGET: ${data.site.toUpperCase()}`;

    if (liveStatus) {
      liveStatus.textContent = 'CONNECTED · JPL';
      liveStatus.className = 'good';
    }

    const windows = data.windows || [];
    const analytics = data.analytics ||
      calculateMissionAnalytics(observations, data.thresholds, windows);

    if (analytics.schema &&
        analytics.schema !== 'lunar-ephemeris-analytics/1.0') {
      throw new Error(`Schema analytics non riconosciuto: ${analytics.schema}`);
    }

    data.analytics = analytics;
    data.science_priority = science;
    data.engineering_priority = engineering;
    window.lastEphemerides = data;

    renderMissionAnalytics(analytics);
    renderOperationalWindows(data, observations, windows);
    const summary = windows.length
      ? windows.map((win, i) =>
          `#${i+1} ${win.start_utc.slice(0,16).replace('T',' ')} – ` +
          `${win.end_utc.slice(0,16).replace('T',' ')} UTC`
        ).join(' | ')
      : 'Nessuna finestra soddisfa entrambe le soglie nel periodo selezionato.';

    message.textContent =
      `${data.source} · ${observations.length} campioni · ${windows.length} finestre geometriche. ` +
      summary + ' — Non include verifica ostacoli o budget radio.';
    document.querySelectorAll('.graphname')[0].textContent =
      `SOLAR ELEVATION · ${observations.length} SAMPLES`;
    document.querySelectorAll('.graphname')[1].textContent =
      `EARTH ELEVATION · ${windows.length} WINDOWS`;
  } catch (err) {
    console.error('Ephemerides error:', err);
    if (liveStatus) {
      liveStatus.textContent = 'ERROR';
      liveStatus.className = 'warn';
    }
    message.textContent = `Effemeridi non disponibili: ${err.message}. Nessun dato dimostrativo mostrato.`;
  } finally {
    applyButton.disabled = false;
    applyButton.textContent = 'UPDATE VISUALIZATION';
  }
}

applyButton.addEventListener('click', updateEphemerides);
window.addEventListener('resize', () => {
  // Ridisegna i grafici solo dopo aver ricevuto dati reali.
  if (window.lastEphemerides) {
    const d = window.lastEphemerides;
    drawEphemerisChart(chart1, d.observations, 'sun_elevation_deg',
      d.thresholds.sun_elevation_deg, '#5be7f5', d.windows);
    drawEphemerisChart(chart2, d.observations, 'earth_elevation_deg',
      d.thresholds.earth_elevation_deg, '#f4b95f', d.windows);
  }
});



// ===== COMMUNICATION INTELLIGENCE =====
window.lastEngineeringModels = {};

function numericInput(id) {
  const value = Number(document.getElementById(id).value);
  if (!Number.isFinite(value)) throw new Error(`Valore non valido: ${id}`);
  return value;
}

function displayNumber(id, value, suffix = '') {
  document.getElementById(id).textContent =
    Number.isFinite(value) ? `${value.toFixed(2)}${suffix}` : 'N/D';
}

async function postModel(endpoint, payload) {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
    cache: 'no-store'
  });
  const data = await response.json();
  if (!response.ok || data.status !== 'ok') {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data.result;
}

document.querySelector('#calculateRF').addEventListener('click', async () => {
  const button = document.querySelector('#calculateRF');
  const status = document.querySelector('#rfStatus');
  button.disabled = true;
  status.textContent = 'Calcolo del budget radio…';

  try {
    const payload = {
      distance_km: numericInput('rfDistance'),
      frequency_ghz: numericInput('rfFrequency'),
      transmit_power_dbm: numericInput('rfPower'),
      transmit_antenna_gain_dbi: numericInput('rfTxGain'),
      receive_antenna_gain_dbi: numericInput('rfRxGain'),
      system_losses_db: numericInput('rfLosses'),
      receiver_sensitivity_dbm: numericInput('rfSensitivity'),
      required_margin_db: numericInput('rfMargin')
    };
    const result = await postModel('/api/communications/link-budget', payload);
    window.lastEngineeringModels.rf = {inputs: payload, result};

    displayNumber('rfPathLoss', result.free_space_path_loss_db, ' dB');
    displayNumber('rfReceived', result.received_power_dbm, ' dBm');
    displayNumber('rfLinkMargin', result.link_margin_db, ' dB');
    document.querySelector('#rfCheck').textContent =
      result.margin_check === true ? 'PASS' :
      result.margin_check === false ? 'FAIL' : 'N/D';
    status.textContent =
      'Stima preliminare in spazio libero. Visibilità del terreno, puntamento, interferenze e prestazioni hardware non sono verificate.';
  } catch (error) {
    status.textContent = `Calcolo RF non riuscito: ${error.message}`;
  } finally {
    button.disabled = false;
  }
});

// ===== THERMAL INTELLIGENCE =====
function drawThermalChart(samples) {
  const canvas = document.querySelector('#thermalChart');
  const ctx = canvas.getContext('2d');
  const width = Math.max(100, canvas.clientWidth);
  const height = Math.max(100, canvas.clientHeight);
  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const points = (Array.isArray(samples) ? samples : []).map((sample, index) => {
    const time = Number(sample.time_s ?? sample.elapsed_s ?? sample.time ?? index);
    const temperature = Number(sample.temperature_k ?? sample.temperature_K ?? sample.temperature);
    return {time, temperature};
  }).filter(p => Number.isFinite(p.time) && Number.isFinite(p.temperature));

  if (points.length < 2) {
    ctx.fillStyle = '#8295a9';
    ctx.font = '11px sans-serif';
    ctx.fillText('Campioni termici non disponibili nel formato atteso.', 8, 22);
    return;
  }

  const minT = Math.min(...points.map(p => p.temperature));
  const maxT = Math.max(...points.map(p => p.temperature));
  const minX = points[0].time;
  const maxX = points[points.length - 1].time;
  const pad = {left:42, right:10, top:10, bottom:22};
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const rangeT = Math.max(1e-9, maxT - minT);
  const rangeX = Math.max(1e-9, maxX - minX);

  ctx.strokeStyle = '#203141';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + plotH * i / 4;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(width-pad.right, y); ctx.stroke();
  }

  ctx.strokeStyle = '#f4b95f';
  ctx.lineWidth = 2;
  ctx.beginPath();
  points.forEach((p, i) => {
    const x = pad.left + (p.time - minX) / rangeX * plotW;
    const y = pad.top + (maxT - p.temperature) / rangeT * plotH;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.fillStyle = '#9aafc2';
  ctx.font = '9px sans-serif';
  ctx.fillText(`${maxT.toFixed(1)} K`, 3, 13);
  ctx.fillText(`${minT.toFixed(1)} K`, 3, height - 25);
  ctx.fillText('TEMPO (s)', pad.left, height - 5);
}

document.querySelector('#calculateThermal').addEventListener('click', async () => {
  const button = document.querySelector('#calculateThermal');
  const status = document.querySelector('#thermalStatus');
  button.disabled = true;
  status.textContent = 'Simulazione termica RK4 in corso…';

  try {
    const payload = {
      duration_s: numericInput('thDuration'),
      step_s: numericInput('thStep'),
      initial_temperature_k: numericInput('thInitial'),
      thermal_capacity_j_k: numericInput('thCapacity'),
      solar_flux_w_m2: numericInput('thFlux'),
      projected_area_m2: numericInput('thArea'),
      absorptivity: numericInput('thAbsorptivity'),
      emissivity: numericInput('thEmissivity'),
      radiator_area_m2: numericInput('thRadiator'),
      internal_power_w: numericInput('thPower'),
      environment_temperature_k: numericInput('thEnvironment'),
      illumination_fraction: numericInput('thIllumination'),
      conductive_coupling_w_k: numericInput('thCoupling'),
      sink_temperature_k: numericInput('thSink')
    };
    const result = await postModel('/api/thermal/simulate', payload);
    window.lastEngineeringModels.thermal = {inputs: payload, result};

    displayNumber('thFinal', result.final_temperature_k, ' K');
    displayNumber('thMin', result.min_temperature_k, ' K');
    displayNumber('thMax', result.max_temperature_k, ' K');
    document.querySelector('#thSamples').textContent =
      Array.isArray(result.samples) ? String(result.samples.length) : 'N/D';
    drawThermalChart(result.samples);

    status.textContent =
      'Simulazione preliminare a nodo singolo. Proprietà costanti e condizioni ambientali semplificate; non è una qualifica termica del veicolo.';
  } catch (error) {
    status.textContent = `Simulazione termica non riuscita: ${error.message}`;
  } finally {
    button.disabled = false;
  }
});


// Esporta il piano e le effemeridi realmente ricevute da JPL Horizons.
document.querySelector('#exportMission').addEventListener('click', () => {
  const data = window.lastEphemerides;
  if (!data || !Array.isArray(data.observations) || data.observations.length < 2) {
    message.textContent = 'Prima aggiorna la visualizzazione e attendi i dati NASA/JPL.';
    return;
  }

  const plan = {
    schema_version: 1,
    generated_at_utc: new Date().toISOString(),
    mission: {
      site: data.site,
      start_date_utc: data.start_utc,
      duration_hours: data.duration_hours,
      science_priority: data.science_priority,
      engineering_priority: data.engineering_priority,
      min_sun_elevation_deg: data.thresholds.sun_elevation_deg,
      min_earth_elevation_deg: data.thresholds.earth_elevation_deg
    },
    astronomy: {
      status: data.source,
      observations: data.observations,
      operational_windows: data.windows || [],
      window_count: (data.windows || []).length,
      step: data.step,
      window_constraints: data.thresholds,
      analytics: data.analytics || null
    },
    engineering_models: window.lastEngineeringModels || {},
    validation: {
      terrain_occlusion: 'not_verified',
      radio_line_of_sight: 'not_verified',
      landing_safety: 'not_verified',
      flight_qualification: 'not_qualified'
    },
    notice: data.notice || 'Piano preliminare: non certificato per uso operativo.'
  };

  const blob = new Blob([JSON.stringify(plan, null, 2) + '\n'], {
    type: 'application/json;charset=utf-8'
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  const safeSite = data.site.toLowerCase().replace(/[^a-z0-9]+/g, '_');
  link.href = url;
  link.download = `mission_${safeSite}_${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  message.textContent = 'Piano JSON esportato con effemeridi e finestre calcolate.';
});
