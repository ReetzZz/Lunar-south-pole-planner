<!-- Last updated: 2026-11-14 -->
# Lunar South Pole Planner — integrazione v8

Aggiunge una stima diagnostica della visibilità solare diretta confrontando le osservazioni solari NASA/JPL Horizons con il profilo d'orizzonte DEM già esportato.

## Uso
1. Generare `reports/local_horizon_profile.json` dal pulsante PROFILO ORIZZONTE LOCALE.
2. Aggiornare le osservazioni NASA/JPL Horizons.
3. Usare `STIMA ILLUMINAZIONE DA ORIZZONTE (DIAGNOSTICA)`.
4. Inserire un offset azimutale soltanto se determinato da una verifica indipendente.
5. Consultare `reports/solar_illumination_diagnostic.json`.

Convenzione: `azimut_griglia = (azimut_Horizons + offset) mod 360`.

## Limiti
- Il modulo non stima automaticamente l'offset e non dichiara l'orientamento validato.
- Il sito geodetico resta non validato indipendentemente.
- È una stima geometrica diagnostica, non un modello di energia solare, ombre penumbrali o potenza del rover.
- I raster originali non vengono modificati e il modulo non effettua nuove richieste di rete.
- Nessun test automatico è stato eseguito in questa fase; i test sono rinviati alla verifica finale concordata.
