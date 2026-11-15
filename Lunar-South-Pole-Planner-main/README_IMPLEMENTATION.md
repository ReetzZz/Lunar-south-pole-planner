<!-- Last updated: 2026-11-14 -->
# Lunar South Pole Mission Planner — integrazione incrementale

## Novità in questa versione

- La GUI distingue le curve illustrative dalle osservazioni reali NASA/JPL Horizons: le card di illuminazione e visibilità indicano `DEMO` finché non si consultano le osservazioni reali.
- Le osservazioni Horizons caricate vengono conservate in memoria per le analisi successive.
- `FINESTRE OPERATIVE REALI` calcola finestre campionate nelle quali elevazione del Sole e della Terra sono entrambe >= 5°. È una verifica geometrica su campioni, non un modello di potenza o un link budget RF.
- `SCORING SITO CON DATI REALI` applica lo scoring trasparente solo alle frazioni geometriche ricavate da Horizons. Pendenza, rugosità e confidenza restano mancanti, non vengono inventate. Il punteggio è parziale e non è una classifica scientifica certificata.
- `PIANIFICA PERCORSO ROVER` carica il DEM LOLA e calcola un percorso A* su indici riga/colonna del raster, con soglia di pendenza e budget energetico preliminare. Il risultato viene scritto in `reports/rover_plan.json`.
- Il planner rover usa intenzionalmente indici di griglia, non latitudine/longitudine, finché il frame geodetico e l'allineamento dei DEM non sono stati validati.
- Il journal P-System resta un prototipo locale append-only. Non viene dichiarata una connessione a nodi P-System remoti.

## Avvio

Attivare l'ambiente virtuale con le dipendenze già usate dal progetto, poi eseguire:

```bash
python main.py
```

## Percorsi dati attesi

- `data/terrain/official-lola/Site04_final_adj_5mpp_surf.tif`
- `data/terrain/reference-lroc/NAC_DTM_ESALL_SR12.TIF`

## Limiti da mantenere espliciti

1. Le coordinate dei siti e i riferimenti CRS dei DEM richiedono validazione indipendente.
2. L'elevazione positiva del Sole non determina da sola potenza disponibile; servono geometria dei pannelli, efficienza, accumulo e carichi.
3. L'elevazione positiva della Terra non determina da sola un collegamento radio; servono link budget, antenne, potenza, frequenze, relay e ostacoli.
4. Il percorso rover è un modello A* preliminare; non include dinamica, slittamento, ruote, termica, rischio o incertezza del terreno.
5. Le finestre operative dipendono dal campionamento temporale e dalle osservazioni Horizons effettivamente ricevute.
6. Lo scoring è parziale quando mancano metriche e non va usato come decisione operativa.
7. L'adattatore P-System è locale e non è ancora integrato con un protocollo remoto.

## Piano di verifica

In accordo con il piano di lavoro, in questa fase non sono stati eseguiti test automatici. Eseguire la suite completa soltanto dopo aver terminato tutte le integrazioni previste.
