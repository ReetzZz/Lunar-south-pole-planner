<!-- Last updated: 2026-11-14 -->
# Lunar South Pole Planner — integrazione v5

Questa integrazione aggiorna il pianificatore rover per usare la dimensione reale dei pixel in entrambe le direzioni e una stima della pendenza locale ottenuta dal gradiente del DEM. Le celle NoData restano invalicabili; il costo di ricerca penalizza pendenze maggiori.

## File inclusi
- `main.py`: aggiorna la finestra del pianificatore per passare separatamente la risoluzione X/Y e salvarla nel rapporto.
- `src/rover_planning.py`: implementa il routing terrain-aware A* con risoluzione anisotropa.

## Limiti espliciti
- L'energia è ancora una stima semplificata `distanza × Wh/m`, non un modello fisico di rover.
- Non include dinamica, slittamento, carico, temperatura, stato della batteria, incertezza altimetrica o pianificazione multi-rover.
- Il percorso usa righe/colonne del DEM; non convalida la georeferenziazione fisica dei prodotti lunari.
- I test automatici non sono stati eseguiti in questa fase, in accordo con il piano di concentrarli nella verifica finale.

## Applicazione
Estrarre l'archivio nella root del progetto, sovrascrivendo i due file inclusi. Fare prima una copia di backup.
