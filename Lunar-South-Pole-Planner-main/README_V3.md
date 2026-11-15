<!-- Last updated: 2026-11-14 -->
# Integrazione v3 — Rapporto unificato di stato missione

Questa integrazione aggiunge un rapporto JSON e Markdown dai dati già disponibili nell'applicazione.

## Nuove funzionalità

- Pulsante GUI `ESPORTA RAPPORTO MISSIONE`.
- Nuovo modulo `src/mission_report.py`.
- Esporta sito/data/orizzonte, osservazioni Horizons già caricate, presenza dei DEM, piano rover già salvato e conteggio del journal P-System locale.
- Evidenzia in modo esplicito metriche mancanti e limiti di validazione geospaziale.
- Non effettua richieste di rete e non modifica i raster.

## File generati dall'applicazione

- `reports/mission_status_report.json`
- `reports/mission_status_report.md`

## Limiti

Il rapporto è una fotografia dello stato presente, non una certificazione scientifica. Le osservazioni astronomiche sono incluse solo se già caricate per il sito selezionato. Il journal resta locale; nessuna connessione remota P-System è dichiarata. Nessun test automatico è stato eseguito in questa fase, in accordo con il piano concordato.
