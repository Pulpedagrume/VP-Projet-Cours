# Table des adresses Modbus

Serveur : **l'automate** (`plc_main.py`), port TCP **5020**, n° d'esclave
indifférent (1 conseillé). Adresses en **base 0**.

Source unique dans le code Python : [`src/demirame/mapping.py`](../src/demirame/mapping.py).
Côté Node-RED, la même table est recopiée dans le nœud « Table des adresses ».

Indices des disjoncteurs : **0 = départ 1, 1 = départ 2, 2 = départ 3, 3 = arrivée**.

## Pourquoi seulement des coils et des holding registers ?

Un client Modbus ne peut **écrire** que dans les coils et les holding
registers. Comme la simulation et l'IHM sont des clients, et que le
programme de l'automate passe lui aussi par un client, toutes les données
sont dans ces deux zones. Le **sens** de chaque donnée est fixé par sa
plage d'adresses.

## Coils (bits)

| Adresse | Variable | Sens | Écrit par |
|---|---|---|---|
| 0 – 3 | Position DJ (1 = fermé) | Procédé → automate | Simulation |
| 10 – 13 | Ordre d'ouverture DJ | Automate → procédé | Automate |
| 20 – 23 | Ordre de fermeture DJ | Automate → procédé | Automate |
| 30 – 33 | Demande ACR d'ouverture DJ (impulsion) | IHM → automate | Node-RED (remis à 0 par l'automate) |
| 40 – 43 | Demande ACR de fermeture DJ (impulsion) | IHM → automate | Node-RED (remis à 0 par l'automate) |
| 50 | Acquittement ACR (impulsion) | IHM → automate | Node-RED (remis à 0 par l'automate) |
| 60 – 62 | Seuil phase dépassé, départ 1 – 3 | Automate → IHM | Automate |
| 70 – 72 | Seuil homopolaire dépassé, départ 1 – 3 | Automate → IHM | Automate |
| 80 – 82 | Alarme déclenchement phase, départ 1 – 3 | Automate → IHM | Automate |
| 90 – 92 | Alarme déclenchement homopolaire, départ 1 – 3 | Automate → IHM | Automate |
| 100 | Voyant alarme générale | Automate → IHM | Automate |

## Holding registers (mots de 16 bits)

| Adresse | Variable | Unité / échelle | Sens | Écrit par |
|---|---|---|---|---|
| 0 – 2 | Courant de phase départ 1 – 3 | A | Procédé → automate | Simulation |
| 3 | Courant arrivée | A | Procédé → automate | Simulation |
| 4 – 6 | Courant résiduel Io départ 1 – 3 | A | Procédé → automate | Simulation |
| 7 | Tension jeu de barres | kV × 10 (200 = 20,0 kV) | Procédé → automate | Simulation |
| 20 | Mot de vie (compteur +1 par cycle) | — | Automate → IHM | Automate |
| 100 – 102 | Défaut injecté départ 1 – 3 : 0 aucun, 1 phase, 2 terre | code | Banc de test → simulation | Node-RED (page Banc de test) |

La zone 100 – 102 représente le « banc de test » de l'instructeur : elle est
lue par la simulation, **jamais par l'automate**.
