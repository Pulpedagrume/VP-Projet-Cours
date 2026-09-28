# Spécification — Version 1 (périmètre minimal)

## 1. Système étudié

Une **demi-rame HTA de poste source** : un jeu de barres 20 kV alimenté par
**1 arrivée** et distribuant **3 départs**. Chaque départ possède un
disjoncteur (DJ) et une protection.

Un **automate virtuel** surveille les courants, déclenche le disjoncteur du
départ en défaut et exécute les ordres du poste de conduite (**ACR**).

```
                 Arrivée (DJ A)
                      │
   ═══════════════════╪═══════════════════  Jeu de barres 20 kV
        │             │             │
      DJ 1          DJ 2          DJ 3
        │             │             │
    Départ 1      Départ 2      Départ 3
```

## 2. Périmètre de la version 1

| Inclus | Exclu (versions suivantes) |
|---|---|
| Défaut **franc** sur un départ : **phase** (court-circuit) et **homopolaire** (défaut à la terre) | Sélectivité logique (SLP) |
| Protection maximum de courant de phase (51) sur chaque départ | Protection de l'arrivée, secours, défaillance DJ |
| Protection maximum de courant résiduel (51N) sur chaque départ | Réenclencheur |
| Ordres d'ouverture et de fermeture ACR (4 DJ) | Défaut de mesure |
| Verrouillage après déclenchement, acquittement ACR | Défaut du jeu de barres |
| | Défauts résistants (impédants) : seuls les défauts francs sont simulés |

L'arrivée n'a **pas de protection** en version 1 : son disjoncteur est
seulement commandé par l'ACR. S'il est ouvert, la barre n'est plus alimentée
(tension et courants à 0).

## 3. Entrées de l'automate

| Nom | Type | Unité | Plage | Rôle |
|---|---|---|---|---|
| `courant_depart_n` (n = 1..3) | Analogique | A | 0 – 8000 | Courant de phase du départ |
| `courant_residuel_depart_n` | Analogique | A | 0 – 1000 | Courant résiduel Io (défaut à la terre) |
| `courant_arrivee` | Analogique | A | 0 – 8000 | Information (somme des départs) |
| `tension_barre` | Analogique | kV | 0 – 24 | Présence de tension |
| `position_dj_depart_n` | TOR | 1 = fermé | — | Retour de position |
| `position_dj_arrivee` | TOR | 1 = fermé | — | Retour de position |
| `acr_ouverture_dj_x` | TOR (impulsion) | — | — | Ordre ACR d'ouverture (x = départ 1..3 ou arrivée) |
| `acr_fermeture_dj_x` | TOR (impulsion) | — | — | Ordre ACR de fermeture |
| `acr_acquittement` | TOR (impulsion) | — | — | Acquittement des alarmes |

## 4. Sorties de l'automate

| Nom | Type | Rôle |
|---|---|---|
| `ordre_ouverture_dj_x` | TOR | Ouvre le disjoncteur (maintenu jusqu'au retour « ouvert ») |
| `ordre_fermeture_dj_x` | TOR | Ferme le disjoncteur (maintenu jusqu'au retour « fermé ») |
| `seuil_phase_depasse_n` | TOR | Signalisation : le courant dépasse le seuil (tempo en cours) |
| `seuil_homopolaire_depasse_n` | TOR | Idem pour Io |
| `declenchement_phase_n` | TOR | Alarme mémorisée : déclenché sur défaut phase |
| `declenchement_homopolaire_n` | TOR | Alarme mémorisée : déclenché sur défaut terre |
| `voyant_alarme` | TOR | Au moins une alarme mémorisée |

## 5. Réglages des protections

| Protection | Seuil | Temporisation |
|---|---|---|
| Phase (51) | I > **800 A** | **500 ms** |
| Homopolaire (51N) | Io > **40 A** | **1000 ms** |

Les temporisations sont volontairement longues pour que l'on voie la
séquence sur l'IHM.

## 6. Logique de commande (pour un départ)

1. **Détection** : si `I > 800 A`, le seuil de phase est dépassé ; si
   `Io > 40 A`, le seuil homopolaire est dépassé.
2. **Temporisation** : chaque seuil lance une temporisation au travail (TON).
   Si le seuil disparaît avant la fin, la tempo repart à zéro : pas de
   déclenchement (défaut trop court).
3. **Déclenchement** : à la fin de la tempo, l'alarme correspondante est
   **mémorisée** et le départ est **verrouillé**.
4. **Ordre d'ouverture** : actif tant que le départ est verrouillé et que le
   DJ est fermé, ou après un ordre ACR d'ouverture, jusqu'au retour « ouvert ».
5. **Ordre de fermeture** : sur ordre ACR, **seulement si le départ n'est pas
   verrouillé**. Maintenu jusqu'au retour « fermé ».
6. **Priorité à l'ouverture** : une demande d'ouverture annule toute demande
   de fermeture (sécurité : en cas de doute, on coupe).
7. **Acquittement** : l'ACR acquitte ; les alarmes et le verrouillage
   s'effacent **seulement si le défaut n'est plus mesuré**.
8. **Retour normal** : après acquittement, l'ACR peut refermer le DJ. Si le
   défaut est toujours là (défaut permanent), la protection redéclenche.

## 7. Simulation du procédé

| Grandeur | Normal | Défaut phase franc | Défaut terre franc |
|---|---|---|---|
| Courant départ | 100 à 300 A, bruit ± 3 % | 4000 A | charge + 300 A |
| Io départ | 0 à 3 A | 0 à 3 A | 300 A |
| Courant arrivée | somme des départs fermés | idem | idem |
| Tension barre | 20 kV ± 0,2 | 20 kV | 20 kV |

- DJ ouvert : courant et Io du départ à 0.
- DJ arrivée ouvert : tension et tous les courants à 0.
- Un disjoncteur change de position environ 100 ms après l'ordre.
- Le défaut injecté reste présent jusqu'à ce qu'on le retire (défaut permanent).

Remarque : sur un défaut terre franc, le courant de phase ne dépasse pas
800 A. **Seule la protection homopolaire le voit**, c'est pour cela qu'elle
existe.

## 8. Scénarios de démonstration

1. **Court-circuit départ 2** : I2 = 4000 A → 500 ms → DJ 2 ouvert, alarme
   « déclenchement phase départ 2 ». Les départs 1 et 3 restent alimentés.
2. **Défaut terre départ 1** : Io1 = 300 A → 1 s → DJ 1 ouvert, alarme
   « déclenchement homopolaire départ 1 ».
3. **Fermeture refusée** : fermeture ACR avant acquittement → rien ne se passe.
4. **Défaut permanent** : acquittement puis fermeture avec défaut toujours
   injecté → redéclenchement.
5. **Retour normal** : retirer le défaut, acquitter, fermer → départ en service.

## 9. Architecture (rappel)

- Un seul **serveur Modbus TCP** : l'automate.
- Deux clients : la **simulation** (écrit mesures et positions, lit les
  ordres) et **Node-RED** (lit états et alarmes, écrit les commandes ACR).
- La table des adresses Modbus est dans `src/demirame/mapping.py`,
  documentée dans [`mapping_modbus.md`](mapping_modbus.md).
