<!-- Last updated: 2026-11-14 -->
# Lunar South Pole Planner — integrazione v9

## Obiettivo
Aggiunge una prima stima energetica di percorso basata sul piano rover già salvato (`reports/rover_plan.json`) e sul DEM sorgente registrato nel piano.

## Uso
1. Usa **PIANIFICA PERCORSO ROVER** per generare `reports/rover_plan.json`.
2. Apri **STIMA ENERGETICA PERCORSO ROVER**.
3. Inserisci massa, coefficiente di rotolamento, efficienza della trasmissione, potenza ausiliaria, durata, capacità batteria e riserva.
4. Il rapporto viene scritto in `reports/rover_energy_assessment.json`.

## Modello
- Resistenza al rotolamento: `Crr * massa * gravità lunare * distanza`.
- Lavoro contro gravità: `massa * gravità lunare * salita cumulativa positiva`.
- Energia di trazione: somma dei termini meccanici divisa per l'efficienza della trasmissione.
- Carichi ausiliari: potenza media moltiplicata per durata.
- Budget utilizzabile: capacità nominale meno riserva configurata.

La gravità lunare assunta è 1,62 m/s². Nessun recupero energetico in discesa o contributo solare viene accreditato.

## Limiti importanti
È una stima ingegneristica preliminare, non un modello qualificato. Non include accelerazione, sterzata, slittamento, sinkage, deformazione del suolo, temperatura, invecchiamento della batteria, efficienza variabile o incertezza del DEM. I valori predefiniti sono esempi modificabili, non specifiche di un rover reale. Il riferimento geodetico del DEM resta non validato indipendentemente.

I raster originali non vengono modificati. Non sono stati eseguiti test automatici, come concordato: la verifica viene rinviata alla fase finale.
