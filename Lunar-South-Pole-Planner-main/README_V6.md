<!-- Last updated: 2026-11-14 -->
# Lunar South Pole Planner — integrazione v6

## Scopo
Collega lo scoring multi-criterio esistente alle metriche topografiche locali effettivamente calcolate dal DEM e alle osservazioni NASA/JPL Horizons già caricate nell'applicazione.

## Modifiche
- `src/site_assessment.py`: nuovo servizio di valutazione trasparente del candidato.
- `main.py`: il pulsante di scoring richiede riga/colonna DEM e raggio della finestra, calcola pendenza P95 e rugosità locale, usa le frazioni campionate di elevazione positiva di Sole e Terra e salva `reports/site_assessment.json`.

## Limiti
- La cella DEM è selezionata con indici di griglia: non viene dichiarato che coincida con il sito geografico nominale finché il frame lunare non sia validato.
- L'elevazione solare positiva non tiene conto delle ombre del terreno; la visibilità geometrica della Terra non è un link budget RF.
- La confidenza dei dati resta esplicitamente mancante, non viene inferita dalla sola copertura.
- Le osservazioni di Sole e Terra devono avere lo stesso numero di campioni; il codice non le accoppia implicitamente per indice se i conteggi differiscono.
- I raster originali non vengono modificati.

## Test
Non sono stati eseguiti test automatici in questa fase, secondo il piano di raggrupparli alla verifica finale.

## Applicazione
Fare un backup del progetto e poi estrarre l'archivio nella root del progetto. I file inclusi sovrascrivono `main.py` e aggiungono `src/site_assessment.py`.
