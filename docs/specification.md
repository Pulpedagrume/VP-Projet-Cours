# Spécification — Version 1

## 1. Système étudié

Une **demi-rame HTA de poste source** : un jeu de barres 20 kV alimenté par
**1 arrivée** (transformateur HTB/HTA) et distribuant **3 départs**. Chaque
départ possède un disjoncteur (DJ) et une protection.

Un **automate virtuel** mesure les courants des trois phases, déclenche le
disjoncteur du départ en défaut, chronomètre l'élimination du défaut et
exécute les ordres du poste de conduite (**ACR**).

```
                 TR HTB/HTA
                      │
                 Arrivée (DJ A)
                      │
   ═══════════════════╪═══════════════════  Jeu de barres 20 kV
        │             │             │
      DJ 1          DJ 2          DJ 3
        │             │             │
    Départ 1      Départ 2      Départ 3
```

## 2. Périmètre

| Inclus | Exclu (versions suivantes) |
|---|---|
| Défauts **francs** construits phase par phase : monophasé terre, biphasé isolé, biphasé terre, triphasé | Défauts résistants (impédants) |
| Protection I> (ANSI 51) sur L1, L2, L3 et Io> (ANSI 51N), à temps constant, sur chaque départ | Sélectivité logique (SLP) |
| Réglages (seuils, temporisations) modifiables depuis l'IHM | Protection de l'arrivée, secours, défaillance DJ |
| Relevé des temps : protection, ouverture DJ, élimination | Réenclencheur |
| Ordres d'ouverture et de fermeture ACR (4 DJ), sélection puis exécution | Défaut de mesure, défaut du jeu de barres |
| Verrouillage après déclenchement, acquittement ACR | |

L'arrivée n'a **pas de protection** : son disjoncteur est seulement commandé
par l'ACR. S'il est ouvert, la barre n'est plus alimentée (tension et
courants à 0).

## 3. Entrées de l'automate (par départ, sauf mention)

| Nom | Type | Unité | Rôle |
|---|---|---|---|
| I L1, I L2, I L3 | Analogique | A | Courants de phase (surveillés par I>) |
| Io | Analogique | A | Courant résiduel (surveillé par Io>) |
| Tension barre (arrivée) | Analogique | kV | Présence de tension, creux de tension |
| Position DJ (4 DJ) | TOR | 1 = fermé | Retour de position |
| Télécommandes ACR ouverture / fermeture (4 DJ) | TOR (impulsion) | — | Ordres de l'opérateur |
| Acquittement ACR | TOR (impulsion) | — | Acquittement des alarmes |
| Réglages I> et Io> (seuil, tempo) | Registres | A, ms | Réglages de la protection |

## 4. Sorties de l'automate

| Nom | Type | Rôle |
|---|---|---|
| Ordre d'ouverture / de fermeture (4 DJ) | TOR | Maintenu jusqu'au retour de position |
| Démarrage I>, démarrage Io> | TOR | Seuil dépassé, temporisation en cours |
| Déclenchement I>, déclenchement Io> | TOR | Alarme mémorisée jusqu'à l'acquittement |
| Voyant alarme générale | TOR | Au moins une alarme mémorisée |
| Relevé : t protection, t ouverture DJ, t élimination, phases vues, protection d'origine, nombre de déclenchements | Registres | Chronométrage du dernier déclenchement |
| Mot de vie, durée de cycle | Registres | Surveillance de l'automate |

## 5. Réglages par défaut

| Protection | Seuil | Temporisation | Plages autorisées |
|---|---|---|---|
| I> (51) | **800 A** | **500 ms** | 50 – 8000 A, 0 – 10000 ms |
| Io> (51N) | **40 A** | **1000 ms** | 5 – 1000 A, 0 – 10000 ms |

Une valeur hors plage envoyée par l'IHM est ramenée dans la plage par
l'automate, qui réécrit la valeur réellement appliquée.

## 6. Logique de commande (pour un départ, cycle de 20 ms)

1. **Détection** : chaque phase est comparée au seuil I> ; Io est comparé
   au seuil Io>. On note les phases vues en défaut.
2. **Temporisation** : chaque seuil lance une temporisation au travail (TON),
   comptée à partir du cycle où le seuil est dépassé. Si le seuil disparaît
   avant la fin, la tempo repart à zéro : pas de déclenchement.
3. **Déclenchement** : à la fin de la tempo, l'alarme est **mémorisée** et le
   départ est **verrouillé**.
4. **Relevé** : le chronomètre part au premier dépassement de seuil (t = 0).
   On relève t protection (ordre de déclenchement), t ouverture DJ (de l'ordre
   au retour « ouvert ») et t élimination (de t = 0 au retour « ouvert »).
5. **Ordre d'ouverture** : actif tant que le départ est verrouillé et que le
   DJ est fermé, ou après une télécommande ACR, jusqu'au retour « ouvert ».
6. **Ordre de fermeture** : sur télécommande ACR, **seulement si le départ
   n'est pas verrouillé**. Maintenu jusqu'au retour « fermé ».
7. **Priorité à l'ouverture** : une demande d'ouverture annule toute demande
   de fermeture (en cas de doute, on coupe).
8. **Acquittement** : les alarmes et le verrouillage s'effacent **seulement si
   le défaut n'est plus mesuré**. Le relevé des temps est conservé.
9. **Retour normal** : après acquittement, l'ACR peut refermer le DJ. Si le
   défaut est toujours là (défaut permanent), la protection redéclenche.

La durée réelle de chaque cycle est mesurée et utilisée par les
temporisations : les temps relevés sont précis à un cycle près (≈ 20 ms).

## 7. Simulation du procédé (pas de 10 ms)

Le modèle travaille en **phaseurs** (nombres complexes) : chaque courant et
chaque tension a un module et un angle. Le courant résiduel est la somme
vectorielle Io = I1 + I2 + I3. Détails et diagrammes de Fresnel :
[`defauts_fresnel.md`](defauts_fresnel.md).

On choisit sur le banc de test les phases touchées et la mise à la terre :

| Défaut | Phases | Courants simulés | Io | Tension barre | Protection attendue |
|---|---|---|---|---|---|
| Aucun | — | charge 150 / 250 / 200 A ± 2 % | 0 à 3 A | 20 kV ± 0,1 | — |
| Monophasé terre | 1 phase + Terre | phase touchée + 300 A (en phase avec sa tension) | 300 A | 20 kV (V touchée → 0, neutre décalé) | Io> seule |
| Biphasé isolé | 2 phases | Icc2 = 0,866 × Icc3 ≈ 3460 A, opposés | ≈ 0 | creux sur les 2 phases | I> |
| Biphasé terre | 2 phases + Terre | Icc2 sur les 2 phases | 300 A | creux + neutre décalé | I> et Io> (la plus rapide) |
| Triphasé | L1-L2-L3 | Icc3 = 4000 A, retard 75° | ≈ 0 | creux à 60 % | I> |

- Le neutre HTA est mis à la terre par une résistance : le courant de défaut
  à la terre est limité à 300 A. C'est pour cela qu'un défaut monophasé n'est
  **vu que par Io>** : le courant de phase reste sous le seuil de 800 A.
- Une phase seule sans terre ne constitue pas un défaut.
- DJ ouvert : courants et Io du départ à 0. DJ arrivée ouvert : tension et
  tous les courants à 0.
- Temps de manœuvre d'un disjoncteur : ouverture 60 ms, fermeture 80 ms.
- Le défaut reste présent jusqu'à ce qu'on le supprime (défaut permanent).

## 8. Scénarios de démonstration

1. **Biphasé L1-L2 sur le départ 2** : I L1 et I L2 ≈ 3460 A → après 500 ms
   le DJ 2 s'ouvre, alarme « déclenchement I> (L1-L2) ». Relevé : t protection
   ≈ 500 ms, t ouverture DJ ≈ 60 à 80 ms.
2. **Monophasé L3-terre sur le départ 3** : Io = 300 A, I L3 ≈ 500 A → seule
   Io> démarre → déclenchement après 1000 ms.
3. **Modification d'un réglage** : tempo I> du départ 1 à 250 ms, puis défaut
   triphasé → le relevé indique ≈ 250 ms.
4. **Fermeture refusée** : fermeture ACR avant acquittement → l'automate
   refuse.
5. **Défaut permanent** : acquittement puis fermeture avec le défaut toujours
   appliqué → redéclenchement, compteur de déclenchements à 2.
6. **Retour normal** : supprimer le défaut, acquitter, fermer.

## 9. Architecture

- Un seul **serveur Modbus TCP** : l'automate (cycle 20 ms).
- Deux clients : la **simulation** (écrit mesures et positions, lit les
  ordres et le défaut injecté) et **Node-RED** (lit tout, écrit les
  télécommandes, les réglages et le défaut du banc de test).
- La table des adresses Modbus est dans `src/demirame/mapping.py`,
  documentée dans [`mapping_modbus.md`](mapping_modbus.md).
