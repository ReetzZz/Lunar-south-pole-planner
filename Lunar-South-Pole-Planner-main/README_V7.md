<!-- Last updated: 2026-11-14 -->
# Lunar South Pole Planner — integrazione v7

## Scopo
Aggiunge alla GUI una funzione per calcolare e salvare il profilo locale dell'orizzonte da un punto selezionato con indici di griglia DEM.

## Uso
- Nella GUI selezionare `PROFILO ORIZZONTE LOCALE (DIAGNOSTICO)`.
- Inserire riga e colonna 0-based del raster LOLA, altezza dell'osservatore e distanza massima.
- Il risultato viene salvato in `reports/local_horizon_profile.json`.

## Limiti scientifici
- Il profilo usa la funzione esistente `src/terrain_horizon.py`.
- Gli azimut del profilo seguono gli assi della griglia raster e non sono certificati come azimut rispetto al nord locale.
- Non viene effettuato alcun confronto automatico con gli azimut di NASA/JPL Horizons.
- La georeferenziazione fisica del candidato resta non validata; i risultati sono diagnostici.
- Nessun raster originale viene modificato e non vengono effettuate richieste di rete.

## Verifiche
Non sono stati eseguiti test automatici in questa fase, in accordo con la decisione di eseguirli tutti alla fine.
