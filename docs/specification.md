# Spécification — Version 2

## 1. Système étudié

Une **demi-rame HTA de poste source** : un jeu de barres 20 kV alimenté par
**1 arrivée** (transformateur HTB/HTA) et distribuant **3 départs**. Chaque
cellule possède un disjoncteur (DJ) et une protection.

Un **automate virtuel** mesure les courants des trois phases, déclenche le
disjoncteur de la cellule en défaut, **réenclenche** automatiquement les
départs, accélère l'élimination des défauts du jeu de barres (**SLP**),
chronomètre l'élimination du défaut et exécute les ordres du poste de
conduite (**ACR**).

```
                 TR HTB/HTA
                      │
                 Arrivée (DJ A)     I> + Io> de secours + SLP
                      │
   ═══════════════════╪═══════════════════  Jeu de barres 20 kV
        │             │             │
      DJ 1          DJ 2          DJ 3      I> + Io> + réenclencheur (RRL)
        │             │             │
    Départ 1      Départ 2      Départ 3
```

## 2. Périmètre

| Inclus | Exclu |
|---|---|
| Défauts **francs** construits phase par phase (monophasé terre, biphasé isolé, biphasé terre, triphasé), sur un départ ou sur le jeu de barres | Défauts résistants (impédants) |
| Nature du défaut : fugitif, semi-permanent, permanent | Défaillance d'un disjoncteur (refus d'ouverture) |
| Départs : I> (ANSI 51) sur L1, L2, L3 et Io> (ANSI 51N), à temps constant | Défaut de mesure |
| Départs : réenclencheur RR + RL | Protections directionnelles |
| Arrivée : I> et Io> de secours + sélectivité logique (SLP) | |
| Réglages modifiables depuis l'IHM ; relevé des temps | |
| Mode aléatoire (fonctionnement normal d'un poste) | |
| Ordres ACR (4 DJ) par sélection puis exécution ; verrouillage et acquittement | |

## 3. Entrées de l'automate (par cellule, sauf mention)

| Nom | Type | Unité | Rôle |
|---|---|---|---|
| I L1, I L2, I L3 | Analogique | A | Courants de phase (surveillés par I>) |
| Io | Analogique | A | Courant résiduel (surveillé par Io>) |
| Tension barre (arrivée) | Analogique | kV | Présence de tension, creux de tension |
| Position DJ | TOR | 1 = fermé | Retour de position |
| Télécommandes ACR ouverture / fermeture | TOR (impulsion) | — | Ordres de l'opérateur |
| Acquittement ACR | TOR (impulsion) | — | Acquittement des alarmes |
| SLP en service | TOR | — | Mise en / hors service de la sélectivité logique |
| Réglages I> et Io> (seuil, tempo) | Registres | A, ms | Réglages des protections |
| RRL en service (départs), tempo SLP (arrivée) | Registres | —, ms | Réglages complémentaires |

## 4. Sorties de l'automate

| Nom | Type | Rôle |
|---|---|---|
| Ordre d'ouverture / de fermeture | TOR | Maintenu jusqu'au retour de position |
| Démarrage I>, démarrage Io> | TOR | Seuil dépassé, temporisation en cours |
| Déclenchement I>, Io> (et SLP sur l'arrivée) | TOR | Indication du dernier déclenchement |
| Étape et résultat du réenclencheur | Registres | Suivi du cycle RR / RL |
| Voyant alarme générale | TOR | Au moins une cellule verrouillée |
| Relevé : t protection, t ouverture DJ, t élimination, phases vues, protection d'origine, nombre de déclenchements | Registres | Chronométrage du dernier déclenchement |
| Mot de vie, durée de cycle | Registres | Surveillance de l'automate |

## 5. Réglages par défaut

| Cellule | Protection | Seuil | Temporisation |
|---|---|---|---|
| Départs | I> (51) | **800 A** | **500 ms** |
| Départs | Io> (51N) | **40 A** | **1000 ms** |
| Arrivée (secours) | I> | **2500 A** | **1000 ms** |
| Arrivée (secours) | Io> | **40 A** | **1500 ms** |
| Arrivée | SLP (défaut barre) | — | **200 ms** |

Plages : seuil I> 50 – 8000 A, seuil Io> 5 – 1000 A, temporisations
0 – 10000 ms. Une valeur hors plage est ramenée dans la plage par
l'automate, qui réécrit la valeur réellement appliquée.

**Sélectivité chronométrique** : les temporisations de l'arrivée sont plus
longues que celles des départs. Un défaut sur un départ est donc éliminé par
ce départ ; l'arrivée n'intervient qu'en secours.

Réenclencheur (constantes) : temps mort RR **0,3 s**, temps mort RL **15 s**,
temps de récupération **10 s** après chaque refermeture.

## 6. Logique de commande (cycle de 20 ms)

### 6.1 Protection d'un départ

1. **Détection** : chaque phase est comparée au seuil I> ; Io est comparé
   au seuil Io>. On note les phases vues en défaut.
2. **Temporisation** : chaque seuil lance une temporisation au travail (TON),
   comptée à partir du cycle où le seuil est dépassé. Si le seuil disparaît
   avant la fin, la tempo repart à zéro : pas de déclenchement.
3. **Déclenchement** : à la fin de la tempo, ordre d'ouverture du DJ.
4. **Relevé** : le chronomètre part au premier dépassement de seuil (t = 0).
   On relève t protection, t ouverture DJ et t élimination.
5. **Priorité à l'ouverture** : une demande d'ouverture annule toute demande
   de fermeture.

### 6.2 Réenclencheur (Grafcet)

```
          ┌────────────┐  déclenchement (RRL en service)
          │ 0 REPOS    │──────────────────────────────┐
          └────────────┘                              ▼
               ▲  ▲                          ┌─────────────────┐
  récupération │  │                          │ 1 TEMPS MORT RR │ 0,3 s DJ ouvert
     10 s OK   │  │                          └────────┬────────┘ → refermeture
   (RR réussi) │  │                                   ▼
               │  │  déclenchement           ┌─────────────────┐
               │  └──────────────────────────│ 2 RÉCUPÉRATION  │ 10 s DJ fermé
               │                             └────────┬────────┘
               │                     déclenchement    ▼
               │                             ┌─────────────────┐
               │                             │ 3 TEMPS MORT RL │ 15 s DJ ouvert
               │                             └────────┬────────┘ → refermeture
               │  récupération 10 s OK                ▼
               │  (RL réussi)                ┌─────────────────┐
               └─────────────────────────────│ 4 RÉCUPÉRATION  │ 10 s DJ fermé
                                             └────────┬────────┘
                                   déclenchement      ▼
                                             ┌─────────────────┐
                                             │ 5 DÉFINITIF     │ verrouillé
                                             └─────────────────┘ → acquittement
```

- RRL hors service : tout déclenchement mène directement à l'étape 5.
- Une télécommande ACR pendant le cycle l'interrompt (retour à l'étape 0) :
  l'opérateur reprend la main.
- Quand le cycle réussit, les indications de déclenchement s'effacent seules.
- Étape 5 : fermeture refusée tant que l'ACR n'a pas acquitté ; acquittement
  accepté seulement si le défaut n'est plus mesuré.

### 6.3 Arrivée et sélectivité logique (SLP)

- L'arrivée voit **tous** les défauts, puisque tout le courant passe par elle.
- Chaque départ qui voit le défaut (démarrage I> ou Io>) envoie une
  **attente logique** à l'arrivée.
- **Défaut sur un départ** : il y a une attente logique, donc l'arrivée
  attend sa temporisation longue (secours). Le départ déclenche avant elle
  et l'arrivée retombe.
- **Défaut sur le jeu de barres** : aucune attente logique. Avec la SLP en
  service, l'arrivée déclenche après **200 ms** au lieu de 1000 ms.
- L'arrivée n'a pas de réenclencheur : tout déclenchement est définitif
  (acquittement puis fermeture par l'ACR).

La durée réelle de chaque cycle est mesurée et utilisée par les
temporisations : les temps relevés sont précis à un cycle près (≈ 20 ms).

## 7. Simulation du procédé (pas de 10 ms)

Le modèle travaille en **phaseurs** (nombres complexes) : chaque courant et
chaque tension a un module et un angle. Le courant résiduel est la somme
vectorielle Io = I1 + I2 + I3. Détails et diagrammes de Fresnel :
[`defauts_fresnel.md`](defauts_fresnel.md).

| Défaut | Phases | Courants de défaut | Io | Tension barre | Protection attendue |
|---|---|---|---|---|---|
| Aucun | — | charge 150 / 250 / 200 A ± 2 % | quelques A | 20 kV | — |
| Monophasé terre | 1 phase + Terre | 300 A sur la phase (en phase avec sa tension) | 300 A | V touchée → 0, neutre décalé | Io> seule |
| Biphasé isolé | 2 phases | Icc2 ≈ 3460 A, opposés | ≈ 0 | creux sur les 2 phases | I> |
| Biphasé terre | 2 phases + Terre | Icc2 + 300 A vers la terre | 300 A | creux + neutre décalé | I> et Io> (la plus rapide) |
| Triphasé | L1-L2-L3 | Icc3 = 4000 A, retard 75° | ≈ 0 | creux à 60 % | I> |
| Sur le jeu de barres | au choix | vus par l'arrivée seulement (Icc3 barre = 8000 A) | selon le type | effondrement | arrivée : SLP |

**Nature du défaut** :

| Nature | Comportement simulé | Résultat attendu (RRL en service) |
|---|---|---|
| Fugitif | disparaît dès que le circuit est hors tension | RR réussi |
| Semi-permanent | disparaît après 5 s hors tension | RR échoue, RL réussi |
| Permanent | reste jusqu'à sa suppression (ou réparation) | déclenchement définitif |

- Le courant de charge suit la tension composée : il baisse pendant un creux
  de tension.
- DJ ouvert : courants du départ à 0. DJ arrivée ouvert : tout à 0.
- Temps de manœuvre d'un disjoncteur : ouverture 60 ms, fermeture 80 ms.

### Mode aléatoire

Le mode aléatoire représente le **fonctionnement normal** d'un poste, en
accéléré. Il se met en marche et à l'arrêt depuis la page Banc de test.

- **Charge** : elle suit une « journée » en 3 minutes (± 30 %).
- **Apparition des défauts** : en moyenne toutes les **40 s**, un seul à la fois.
- **Lieu** : 95 % sur un départ sous tension, 5 % sur le jeu de barres.
- **Type** : monophasé terre 70 %, biphasé isolé 12 %, biphasé terre 8 %, triphasé 10 %.
- **Nature** : fugitif 70 %, semi-permanent 20 %, permanent 10 %.
- **Réparation** : un défaut permanent est retiré 60 s après son apparition
  (équipe d'intervention). L'opérateur doit ensuite acquitter et refermer.

## 8. Scénarios de démonstration

1. **Fugitif** : monophasé L1-terre fugitif sur le départ 1. Déclenchement
   Io> après 1 s, RR 0,3 s plus tard, et 10 s après : « cycle réussi,
   éliminé par le RR ».
2. **Semi-permanent** : biphasé L1-L2 semi-permanent sur le départ 2.
   Déclenchement, RR, redéclenchement, RL 15 s plus tard, puis cycle réussi.
3. **Permanent** : triphasé permanent sur le départ 3. Trois déclenchements,
   puis déclenchement définitif. Supprimer le défaut, acquitter, refermer.
4. **SLP** : défaut sur le jeu de barres. L'arrivée déclenche en 200 ms ;
   refaire l'essai avec la SLP hors service : 1000 ms.
5. **Sélectivité** : un défaut sur un départ ne fait jamais déclencher
   l'arrivée.
6. **Mode aléatoire** : laisser tourner et observer le journal, le relevé et
   les tendances ; intervenir quand un départ est verrouillé.

## 9. Architecture

- Un seul **serveur Modbus TCP** : l'automate (cycle 20 ms).
- Deux clients :
  - la **simulation** écrit les mesures, les positions et l'état des défauts,
    et lit les ordres, le banc de test et le mode aléatoire ;
  - **Node-RED** lit tout et écrit les télécommandes, les réglages et le
    banc de test.
- La table des adresses Modbus est dans `src/demirame/mapping.py`,
  documentée dans [`mapping_modbus.md`](mapping_modbus.md).
