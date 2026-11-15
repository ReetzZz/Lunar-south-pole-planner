Last updated: 2026-11-14
Lunar South Pole Mission Planner
================================

Scopo
-----
Applicazione Python/Tkinter per supportare l'analisi preliminare di siti e
operazioni al polo sud lunare. L'applicazione distingue dati astronomici
NASA/JPL Horizons, dati dimostrativi e calcoli locali ancora da validare.

Moduli
------
src/astronomy.py       Osservazioni topocentriche da NASA/JPL Horizons.
src/lunar_geometry.py  Trasformazioni lunari ipotetiche; non certificano il frame.
src/terrain_horizon.py Profilo geometrico dell'orizzonte da DEM.
src/visibility.py      Confronto diagnostico con il profilo di orizzonte.
src/local_site_analysis.py Rapporto preliminare del sito.
src/data_quality.py    Audit non distruttivo dei metadati e della copertura DEM.
src/mission_planning.py Scoring trasparente e finestre operative da metriche esplicite.
src/rover_planning.py  A* su griglia DEM con vincoli di pendenza e budget energetico.
src/psystem_adapter.py Journal locale append-only e riconciliazione deterministica.

Dipendenze
----------
Python 3.10+ consigliato. GUI: tkinter, matplotlib. Analisi: numpy, rasterio,
pyproj, requests. Installare le dipendenze nel virtualenv del progetto.

Avvio
-----
python main.py

Percorsi DEM attesi dalla GUI (opzionali):
data/terrain/official-lola/Site04_final_adj_5mpp_surf.tif
data/terrain/reference-lroc/NAC_DTM_ESALL_SR12.TIF

Funzioni aggiunte
-----------------
- Pulsante AUDIT DEM LUNARI: riporta dimensioni, risoluzione, percentuale di
  copertura valida, intervallo altimetrico e avvertenze. Non modifica i raster.
- Pulsante P-SYSTEM JOURNAL: registra eventi missione in
  reports/mission_events.jsonl. È un journal locale dimostrativo, non una
  connessione remota o un protocollo P-System certificato.
- Confronto siti: non mostra più punteggi fittizi; chiarisce quali metriche
  servono prima di produrre una classifica scientifica.
- src/mission_planning.py: scoring 0-100 con metriche esplicite e metriche
  mancanti dichiarate; finestre geometriche basate su elevazioni in ingresso.
- src/rover_planning.py: pianificatore A* preliminare su matrice DEM.

Esempio d'uso API (da integrare in uno script o notebook)
---------------------------------------------------------
from src.mission_planning import SiteMetrics, SiteWeights, score_site

metrics = SiteMetrics(
    name="candidate-A",
    illumination_fraction=0.75,
    earth_visibility_fraction=0.80,
    slope_deg=8.0,
    roughness_m=1.2,
    data_confidence=0.6,
    notes="Esempio illustrativo: sostituire con misure calcolate.",
)
result = score_site(metrics, SiteWeights())
print(result.to_dict())

from src.rover_planning import plan_rover_path
import numpy as np
# DEM giocattolo, non dati lunari reali:
plan = plan_rover_path(np.zeros((20, 20)), (1, 1), (18, 18), pixel_size_m=5)
print(plan.to_dict())

Limitazioni scientifiche e operative
-----------------------------------
1. Le coordinate dei siti, i CRS e i raster LOLA/LROC devono essere validati
   indipendentemente nel medesimo frame lunare prima di usare risultati per
   decisioni operative. Lo stesso raggio o nome di proiezione non prova
   l'allineamento fisico.
2. Le curve dimostrative già presenti nella GUI sono illustrative, non
   previsioni di illuminazione o disponibilità di comunicazione.
3. Elevazione solare positiva non equivale a potenza disponibile: servono
   geometria dei pannelli, occultazioni, efficienza, batteria e carichi.
4. Elevazione della Terra positiva non equivale a collegamento radio: servono
   link budget, antenne, potenza, frequenze, ostacoli, relay e protocolli.
5. Il pianificatore rover usa un modello semplice di pendenza e consumo Wh/m.
   Non modella dinamica, slittamento, sabbia, ruote, termica o incertezza.
6. Il journal P-System è un adattatore locale di prototipo. La riconciliazione
   ordina e deduplica eventi; i conflitti concorrenti sono segnalati, non
   risolti automaticamente. Non esiste collegamento remoto finché non viene
   definito e integrato il protocollo/API reale.
7. Nessun test automatico è stato eseguito in questa fase, in accordo con la
   decisione di raccogliere le modifiche e svolgere la verifica alla fine.
