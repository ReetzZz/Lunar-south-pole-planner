<!-- Last updated: 2026-11-14 -->
# Integrazione v4 — metriche topografiche locali

Questa versione aggiunge `src/terrain_metrics.py` e il pulsante GUI **ANALISI LOCALE PENDENZA / RUGOSITÀ**.

## Cosa calcola
- quota del pixel centrale, se valida;
- pendenza locale in gradi, mediana e percentile 95 nella finestra;
- rugosità come deviazione standard dei residui rispetto a un piano locale;
- frazione di pixel validi;
- risoluzione del raster usata nel calcolo.

## Limiti deliberati
- La selezione avviene con indici riga/colonna 0-based del DEM LOLA, non con latitudine/longitudine o con il nome del sito.
- Questo evita di attribuire metriche a Shackleton finché la georeferenziazione fisica e il frame dei candidati non sono validati indipendentemente.
- I buchi NoData vengono esclusi dalle statistiche; per il calcolo dei gradienti sono sostituiti temporaneamente con la mediana locale e le statistiche usano solo celle valide. La pendenza vicino a grandi lacune va quindi interpretata con cautela.
- La rugosità è una definizione numerica locale, non un parametro certificato di traversabilità del rover.
- I raster originali non vengono modificati. Il risultato è scritto in `reports/local_terrain_metrics.json`.

## Applicazione
Estrarre questo archivio nella radice del progetto, sovrascrivendo `main.py` e aggiungendo `src/terrain_metrics.py`. Fare prima un backup della directory.

Nessun test automatico viene eseguito in questa fase, in accordo con il piano di lavoro.
