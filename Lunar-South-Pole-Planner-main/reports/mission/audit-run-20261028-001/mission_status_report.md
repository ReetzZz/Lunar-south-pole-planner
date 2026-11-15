<!-- Last updated: 2026-11-14 -->
# Lunar South Pole — rapporto di stato missione

- Generato UTC: 2026-10-28T00:14:03.359746+00:00
- Run ID: 95ef6e7b-46c9-4c54-8d18-91de349c59bf
- Sito candidato: non specificato
- Data pianificazione: 2026-10-28
- Orizzonte: 48 ore

## Osservazioni astronomiche caricate

- Sole: 0 campioni
- Terra: 0 campioni
- Fonte: observations already loaded in the application; no network request performed
- Nota: Geometric observations do not alone establish solar power or RF link availability.

## Dati del terreno

- LOLA: presente — `data/terrain/official-lola/Site04_final_adj_5mpp_surf.tif`
- LROC: presente — `data/terrain/reference-lroc/NAC_DTM_ESALL_SR12.TIF`
- Georeferenziazione fisica validata: False

## Selezione del sito lunare

- Stato della selezione: not_configured
- Candidati classificati nel ranking: 0
- Candidato migliore: non disponibile.
- Nota: la classificazione topografica è preliminare e non certifica la sicurezza o l'idoneità operativa del sito.

## Pianificazione rover

- Nessun piano rover salvato disponibile.

## Valutazione energetica rover

- Valutazione energetica non disponibile.
- Motivo: valutazione energetica non configurata

## P-System

- Stato journal locale: Disabilitato dalla configurazione
- Eventi nel journal locale: 0
- Eventi dell'esecuzione corrente: 0
- Percorso journal: non applicabile
- Nodo remoto collegato: False

## Limiti e avvertenze

- Geodetic alignment of LOLA/LROC and candidate coordinates is not independently validated.
- No power-system model, RF link budget, rover dynamics, or multi-rover coordination is certified by this report.
- Missing measurements remain missing; no placeholder scientific values are inferred.
- The P-System journal is local unless a real remote protocol integration is configured separately.

## Esecuzione orchestratore

- Stato: completed

### Step

- **descent_hazard_detection**: success

### Artefatti

- **descent_hazard_detection**: `reports/mission/audit-run-20261028-001/descent_hazard_report.json`

### Avvisi dell'orchestratore

- Risultati preliminari, non certificati per operazioni reali.
- Georeferenziazione e frame fisico lunare non validati indipendentemente.
- L'allocazione multi-rover usa distanze euclidee, non percorsi DEM.
- Il journal è locale e non si connette a nodi P-System remoti.


## Sintesi integrata della missione

- Stato selezione siti: not_configured
- Candidati nel ranking: 0
- Candidato migliore: non disponibile.
- Budget energetico: valutazione non disponibile.
- descent_hazard_detection: success
- descent_risk_map: non disponibile

## Limiti e avvertenze

- Geodetic alignment of LOLA/LROC and candidate coordinates is not independently validated.
- No power-system model, RF link budget, rover dynamics, or multi-rover coordination is certified by this report.
- Missing measurements remain missing; no placeholder scientific values are inferred.
- The P-System journal is local unless a real remote protocol integration is configured separately.
- Avviso orchestratore: Risultati preliminari, non certificati per operazioni reali.
- Avviso orchestratore: Georeferenziazione e frame fisico lunare non validati indipendentemente.
- Avviso orchestratore: L'allocazione multi-rover usa distanze euclidee, non percorsi DEM.
- Avviso orchestratore: Il journal è locale e non si connette a nodi P-System remoti.

## Quadro complessivo dello stato della missione

- Stato complessivo: completed
- Moduli registrati: 1
- Moduli con stato 'success': 1

### Dettaglio dei moduli

- **descent_hazard_detection**: success

### Artefatti generati

- descent_hazard_detection: `reports/mission/audit-run-20261028-001/descent_hazard_report.json`

### Avvisi e limitazioni aperte

- Risultati preliminari, non certificati per operazioni reali.
- Georeferenziazione e frame fisico lunare non validati indipendentemente.
- L'allocazione multi-rover usa distanze euclidee, non percorsi DEM.
- Il journal è locale e non si connette a nodi P-System remoti.
- I moduli non presenti nel registro non sono considerati completati. L'assenza di avvisi non costituisce una certificazione di sicurezza.

## Dettaglio delle analisi tecniche

- Qualità LOLA/LROC: artefatto non registrato.
- Qualità del percorso rover: artefatto non registrato.
- **Rilevamento dei rischi di discesa**: `reports/mission/audit-run-20261028-001/descent_hazard_report.json`
  - status: preliminary
  - warnings: ['Prototipo software preliminare: non certificato per un atterraggio reale.', 'La scansione sintetica non riproduce geometria, dinamica o limiti reali del lidar.', 'Il confronto presuppone DEM e scansione allineati nello stesso riferimento orizzontale e verticale.', 'La classificazione non costituisce una garanzia di sicurezza.']
- Mappa dei rischi: artefatto non registrato.
- La presenza di un artefatto non equivale a una validazione scientifica o a una certificazione operativa.

## Quadro decisionale della missione

- **Selezione del sito** — fase non registrata; artefatto non registrato
- **Confronto qualitativo LOLA/LROC** — fase non registrata; artefatto non registrato
- **Analisi dei rischi di discesa** — success; artefatto: `reports/mission/audit-run-20261028-001/descent_hazard_report.json`
- **Mappa dei rischi** — fase non registrata; artefatto non registrato
- **Pianificazione del rover** — fase non registrata; artefatto non registrato
- **Valutazione energetica** — fase non registrata; artefatto non registrato

### Criteri per interpretare il risultato

- Un modulo riuscito indica che la fase software ha prodotto un risultato; non dimostra da solo la validità scientifica del risultato.
- Una fase non configurata o non registrata non deve essere interpretata come superata.
- La selezione topografica non sostituisce le verifiche di georeferenziazione, illuminazione, comunicazione, dinamica del rover e condizioni operative.
- La stima energetica deve essere interpretata secondo le ipotesi e le riserve riportate nel relativo artefatto.
- Decisione operativa finale: non determinabile dal solo riepilogo software; richiede validazione dei dati, dei modelli e dei requisiti della missione.

## Coerenza finale dell'esecuzione

- Stato orchestratore: completed_preliminary
- Moduli eseguiti: 1
- Artefatti registrati: 3
- Avvisi: 4
- Gli esiti preliminary indicano analisi non certificate.

### Avvisi

- Risultati preliminari, non certificati per operazioni reali.
- Georeferenziazione e frame fisico lunare non validati indipendentemente.
- L'allocazione multi-rover usa distanze euclidee, non percorsi DEM.
- Il journal è locale e non si connette a nodi P-System remoti.
