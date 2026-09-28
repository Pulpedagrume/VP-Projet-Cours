# Table des adresses Modbus

Serveur : **l'automate** (`plc_main.py`), port TCP **5020**, n° d'esclave
indifférent (1 conseillé). Adresses en **base 0**.

Source unique dans le code Python : [`src/demirame/mapping.py`](../src/demirame/mapping.py).
Côté Node-RED, la même table est recopiée dans le nœud « Table des adresses ».

## Organisation en blocs

Chaque cellule du poste occupe un bloc de **20 adresses**, dans les coils
comme dans les registres :

| Bloc | Cellule | Adresses | Phaseurs |
|---|---|---|---|
| 0 | Arrivée + informations générales | 0 – 19 | 80 – 99 |
| 1 | Départ 1 | 20 – 39 | 100 – 119 |
| 2 | Départ 2 | 40 – 59 | 120 – 139 |
| 3 | Départ 3 | 60 – 79 | 140 – 159 |

**Adresse = 20 × bloc + décalage.** Exemple : tempo I> du départ 2 =
20 × 2 + 6 = **46**.

## Pourquoi seulement des coils et des holding registers ?

Un client Modbus ne peut **écrire** que dans les coils et les holding
registers. Comme la simulation et l'IHM sont des clients, et que le
programme de l'automate passe lui aussi par un client, toutes les données
sont dans ces deux zones. Le **sens** de chaque donnée est fixé par son
décalage.

## Coils (bits) : décalage dans le bloc

| Décalage | Blocs | Variable | Sens | Écrit par |
|---|---|---|---|---|
| 0 | tous | Position DJ (1 = fermé) | Procédé → automate | Simulation |
| 1 | tous | Ordre d'ouverture DJ | Automate → procédé | Automate |
| 2 | tous | Ordre de fermeture DJ | Automate → procédé | Automate |
| 3 | tous | Télécommande ACR d'ouverture (impulsion) | IHM → automate | Node-RED, remis à 0 par l'automate |
| 4 | tous | Télécommande ACR de fermeture (impulsion) | IHM → automate | Node-RED, remis à 0 par l'automate |
| 5 | 0 | Acquittement ACR (impulsion) | IHM → automate | Node-RED, remis à 0 par l'automate |
| 6 | 0 | Voyant alarme générale | Automate → IHM | Automate |
| 10 | départs | Démarrage I> (seuil dépassé, tempo en cours) | Automate → IHM | Automate |
| 11 | départs | Démarrage Io> | Automate → IHM | Automate |
| 12 | départs | Alarme mémorisée : déclenchement I> | Automate → IHM | Automate |
| 13 | départs | Alarme mémorisée : déclenchement Io> | Automate → IHM | Automate |

## Holding registers (mots de 16 bits) : décalage dans le bloc

| Décalage | Blocs | Variable | Unité | Sens | Écrit par |
|---|---|---|---|---|---|
| 0 | tous | Courant phase L1 | A | Procédé → automate | Simulation |
| 1 | tous | Courant phase L2 | A | Procédé → automate | Simulation |
| 2 | tous | Courant phase L3 | A | Procédé → automate | Simulation |
| 3 | tous | Courant résiduel Io | A | Procédé → automate | Simulation |
| 4 | 0 | Tension jeu de barres | kV × 10 | Procédé → automate | Simulation |
| 5 | départs | Réglage seuil I> | A (50 – 8000) | IHM → automate | Node-RED (l'automate écrit les valeurs par défaut et corrige une valeur hors plage) |
| 6 | départs | Réglage tempo I> | ms (0 – 10000) | IHM → automate | idem |
| 7 | départs | Réglage seuil Io> | A (5 – 1000) | IHM → automate | idem |
| 8 | départs | Réglage tempo Io> | ms (0 – 10000) | IHM → automate | idem |
| 10 | 0 | Mot de vie (+1 par cycle) | — | Automate → IHM | Automate |
| 11 | 0 | Durée du dernier cycle automate | ms | Automate → IHM | Automate |
| 10 | départs | Relevé : t protection (apparition → ordre) | ms | Automate → IHM | Automate |
| 11 | départs | Relevé : t ouverture DJ (ordre → DJ ouvert) | ms | Automate → IHM | Automate |
| 12 | départs | Relevé : t élimination (apparition → DJ ouvert) | ms | Automate → IHM | Automate |
| 13 | départs | Relevé : phases vues en défaut | bits (voir ci-dessous) | Automate → IHM | Automate |
| 14 | départs | Relevé : nombre de déclenchements | — | Automate → IHM | Automate |
| 15 | départs | **Banc de test** : défaut injecté | bits (voir ci-dessous) | Banc de test → simulation | Node-RED (l'automate ne le lit pas) |
| 16 | départs | Relevé : protection ayant déclenché | 1 = I>, 2 = Io>, 3 = les deux | Automate → IHM | Automate |

## Zone des phaseurs : holding registers 80 à 159

Pour les diagrammes de Fresnel. Même découpage en blocs de 20, décalé de 80 :
**adresse = 80 + 20 × bloc + décalage**. Écrite par la simulation, lue par
l'IHM (nœud « Lire phaseurs 80..159 ») ; l'automate ne l'utilise pas, car
ses protections travaillent sur les modules.

| Décalage | Blocs | Variable | Unité |
|---|---|---|---|
| 0 | tous | Angle du courant L1 | degrés (0 – 359) |
| 1 | tous | Angle du courant L2 | degrés |
| 2 | tous | Angle du courant L3 | degrés |
| 3 | tous | Angle du courant résiduel Io | degrés |
| 4 | 0 | Module de V1 (tension simple du jeu de barres) | kV × 100 (1155 = 11,55 kV) |
| 5 | 0 | Module de V2 | kV × 100 |
| 6 | 0 | Module de V3 | kV × 100 |
| 7 | 0 | Module de V0 = (V1 + V2 + V3) / 3 | kV × 100 |
| 8 – 11 | 0 | Angles de V1, V2, V3, V0 | degrés |

Les modules des courants sont ceux de la zone principale (décalages 0 à 3).
Angles mesurés par rapport à V1 avant défaut (0°), sens trigonométrique.

## Codage des phases (décalages 13 et 15)

| Bit | Valeur | Signification |
|---|---|---|
| 0 | 1 | Phase L1 |
| 1 | 2 | Phase L2 |
| 2 | 4 | Phase L3 |
| 3 | 8 | Terre |

Exemples : 3 = L1-L2 (biphasé isolé), 11 = L1-L2-Terre (biphasé terre),
12 = L3-Terre (monophasé terre), 7 = L1-L2-L3 (triphasé).
