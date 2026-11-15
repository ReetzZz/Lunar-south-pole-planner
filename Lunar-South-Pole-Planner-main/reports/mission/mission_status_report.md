<!-- Last updated: 2026-11-14 -->
# Lunar South Pole — rapporto di stato missione

- Generato UTC: 2026-10-27T17:42:03.302196+00:00
- Run ID: 9f32aa6d-2f68-4cb7-8b44-5b150b8a8b25
- Sito candidato: Connecting Ridge
- Data pianificazione: 2026-10-25
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

## Pianificazione rover

- distance_m: 133.99494936611666
- estimated_energy_wh: 2.6798989873223333
- max_slope_deg: 19.799291107416934
- cells_expanded: 558
- status: preliminary
- warning: Pianificazione preliminare su DEM. Energia = distanza x consumo costante; non include massa, pendenza energetica, slittamento, ruote, temperatura, incertezza DEM o dinamica del rover. Frame geodetico non validato.
- dem_path: data/terrain/official-lola/Site04_final_adj_5mpp_surf.tif

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

- Stato: completed_preliminary

### Step

- **descent_hazard_detection**: success
- **site_selection**: success
- **lola_lroc_quality**: success
- **rover_path**: success

### Artefatti

- **descent_hazard_detection**: `reports/mission/descent_hazard_report.json`
- **site_selection**: `reports/mission/site_ranking.json`
- **lola_lroc_quality**: `reports/mission/lola_lroc_quality.json`
- **rover_plan**: `reports/mission/rover_plan.json`
- **route_quality**: `reports/mission/route_quality.json`
- **rover_route_map**: `reports/mission/rover_route_map.png`

### Avvisi dell'orchestratore

- Risultati preliminari, non certificati per operazioni reali.
- Georeferenziazione e frame fisico lunare non validati indipendentemente.
- L'allocazione multi-rover usa distanze euclidee, non percorsi DEM.
- Il journal è locale e non si connette a nodi P-System remoti.
