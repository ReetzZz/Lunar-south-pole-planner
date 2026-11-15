<!-- Last updated: 2026-11-14 -->
# Lunar South Pole Planner — integrazione v10

## Nuovo modulo: coordinamento multi-rover

- `src/multi_rover.py` implementa un'assegnazione deterministica di task a rover.
- La selezione rispetta le capacità richieste e il budget energetico disponibile.
- Le attività sono ordinate per priorità decrescente; i pareggi sono risolti in modo deterministico.
- La GUI presenta il pulsante **COORDINAMENTO MULTI-ROVER** e un editor JSON con esempio modificabile.
- Il piano viene salvato in `reports/multi_rover_plan.json`.
- Le assegnazioni vengono aggiunte al journal locale `reports/mission_events.jsonl`.

## Schema di input

`rovers`: lista di oggetti con `id`, `position_xy`, `capabilities`, `available_energy_wh` e `energy_wh_per_m`.

`tasks`: lista di oggetti con `id`, `position_xy`, `required_capabilities`, `priority`, `estimated_energy_wh` e `description`.

Tutte le coordinate `position_xy` devono essere espresse nello stesso frame metrico locale. Il modulo non converte coordinate lunari né presume che i frame geodetici dei DEM siano validati.

## Limiti espliciti

Questa è una pianificazione di alto livello: la distanza è euclidea in linea d'aria, non un percorso DEM. Il modello non gestisce collision avoidance, vincoli radio, finestre solari, schedulazione temporale, dinamica del rover o incertezza del terreno. Gli eventi sono registrati localmente: **non esiste ancora una connessione a un nodo P-System remoto** e il journal locale non deve essere presentato come tale.

## Verifica

Per rispettare il piano di lavoro concordato, non sono stati eseguiti test automatici intermedi. Eseguire la suite completa soltanto dopo il consolidamento delle integrazioni previste.
