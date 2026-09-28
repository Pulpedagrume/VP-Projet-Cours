"""Modèle du procédé : le poste HTA « physique » (disjoncteurs, courants, tension).

Ce fichier ne fait AUCUNE communication réseau : on lui donne les ordres
de l'automate et les défauts injectés, il calcule l'état du poste.

DÉFAUTS FRANCS (sans résistance de défaut)
------------------------------------------
Sur le banc de test, on choisit les phases touchées (L1, L2, L3) et si le
défaut est relié à la terre. Le type de défaut en découle :

| Phases | Terre | Type de défaut              | Effet simulé                          |
|--------|-------|-----------------------------|---------------------------------------|
| 1      | oui   | monophasé terre             | Io = 300 A, phase touchée + 300 A     |
| 2      | non   | biphasé isolé               | 2 phases à Icc2 = 0,866 x Icc3        |
| 2      | oui   | biphasé terre               | 2 phases à Icc2 et Io = 300 A         |
| 3      | -     | triphasé                    | 3 phases à Icc3 (Io reste faible)     |
| 1      | non   | aucun (une phase isolée ne fait pas de défaut)                        |

Le neutre HTA est mis à la terre par une résistance : le courant de défaut
à la terre est limité (ici 300 A). Un court-circuit entre phases fait
chuter la tension du jeu de barres (creux de tension).
"""

import random

from demirame.mapping import BIT_TERRE, BITS_PHASES, NB_BLOCS, NB_DEPARTS

TENSION_NOMINALE_KV = 20.0
BRUIT_TENSION_KV = 0.1
CREUX_TENSION = 0.6                 # tension restante pendant un court-circuit entre phases
CHARGE_DEPARTS_A = [150, 250, 200]  # courant de charge de chaque départ
BRUIT_CHARGE = 0.02                 # ± 2 %
IO_NORMAL_MAX_A = 3                 # déséquilibre normal
ICC_TRIPHASE_A = 4000               # courant de court-circuit triphasé
ICC_BIPHASE_A = round(0.866 * ICC_TRIPHASE_A)
I_DEFAUT_TERRE_A = 300              # limité par la résistance de neutre
TEMPS_OUVERTURE_DJ_MS = 60          # temps de manœuvre d'un disjoncteur HTA
TEMPS_FERMETURE_DJ_MS = 80

# Indice des disjoncteurs dans les listes : 0 = arrivée, 1..3 = départs
ARRIVEE = 0


def nombre_phases(defaut):
    """Nombre de phases touchées dans un code de défaut."""
    return sum(1 for bit in BITS_PHASES if defaut & bit)


def type_defaut(defaut):
    """Nom du défaut correspondant aux bits (affiché dans les journaux)."""
    n = nombre_phases(defaut)
    terre = bool(defaut & BIT_TERRE)
    if n == 3:
        return "triphasé"
    if n == 2:
        return "biphasé terre" if terre else "biphasé isolé"
    if n == 1 and terre:
        return "monophasé terre"
    return "aucun"


class Poste:
    """État du poste : 1 arrivée + 3 départs, courants par phase."""

    def __init__(self):
        self.dj_ferme = [True] * NB_BLOCS        # au départ tout est fermé
        self.manoeuvre_ms = [0] * NB_BLOCS       # temps écoulé depuis l'ordre
        # courants[bloc] = [I L1, I L2, I L3] ; bloc 0 = arrivée
        self.courants = [[0, 0, 0] for _ in range(NB_BLOCS)]
        self.courant_residuel = [0] * NB_BLOCS
        self.tension_kv = 0.0

    def pas(self, ordres_ouverture, ordres_fermeture, defauts, dt_ms):
        """Fait avancer la simulation de dt_ms millisecondes.

        ordres_ouverture, ordres_fermeture : 4 booléens (arrivée, départs 1-3)
        defauts : 3 codes de défaut (départs 1-3), voir mapping.BIT_*
        """
        self._manoeuvrer_disjoncteurs(ordres_ouverture, ordres_fermeture, dt_ms)
        self._calculer_mesures(defauts)

    def _manoeuvrer_disjoncteurs(self, ordres_ouverture, ordres_fermeture, dt_ms):
        for i in range(NB_BLOCS):
            # Un ordre n'a d'effet que s'il demande de changer de position.
            if ordres_ouverture[i] and self.dj_ferme[i]:
                duree = TEMPS_OUVERTURE_DJ_MS
            elif ordres_fermeture[i] and not self.dj_ferme[i]:
                duree = TEMPS_FERMETURE_DJ_MS
            else:
                self.manoeuvre_ms[i] = 0
                continue
            self.manoeuvre_ms[i] += dt_ms
            if self.manoeuvre_ms[i] >= duree:
                self.dj_ferme[i] = not self.dj_ferme[i]
                self.manoeuvre_ms[i] = 0

    def _calculer_mesures(self, defauts):
        barre_alimentee = self.dj_ferme[ARRIVEE]
        court_circuit = False

        for n in range(NB_DEPARTS):
            bloc = n + 1
            if barre_alimentee and self.dj_ferme[bloc]:
                courants, residuel = self._courants_depart(n, defauts[n])
                if nombre_phases(defauts[n]) >= 2:
                    court_circuit = True
            else:
                courants, residuel = [0, 0, 0], 0   # départ hors tension
            self.courants[bloc] = [round(i) for i in courants]
            self.courant_residuel[bloc] = round(residuel)

        # L'arrivée alimente tous les départs : on additionne phase par phase
        self.courants[ARRIVEE] = [
            sum(self.courants[bloc][phase] for bloc in range(1, NB_BLOCS))
            for phase in range(3)
        ]
        self.courant_residuel[ARRIVEE] = sum(self.courant_residuel[1:])

        if not barre_alimentee:
            self.tension_kv = 0.0
        else:
            bruit = random.uniform(-BRUIT_TENSION_KV, BRUIT_TENSION_KV)
            self.tension_kv = TENSION_NOMINALE_KV + bruit
            if court_circuit:
                self.tension_kv *= CREUX_TENSION

    def _courants_depart(self, n, defaut):
        """Courants [L1, L2, L3] et Io d'un départ sous tension."""
        charge = CHARGE_DEPARTS_A[n]
        courants = [charge * (1 + random.uniform(-BRUIT_CHARGE, BRUIT_CHARGE))
                    for _ in range(3)]
        residuel = random.uniform(0, IO_NORMAL_MAX_A)

        phases = [i for i, bit in enumerate(BITS_PHASES) if defaut & bit]
        terre = bool(defaut & BIT_TERRE)

        if len(phases) == 3:
            courants = [ICC_TRIPHASE_A] * 3
        elif len(phases) == 2:
            for p in phases:
                courants[p] = ICC_BIPHASE_A
            if terre:
                residuel = I_DEFAUT_TERRE_A
        elif len(phases) == 1 and terre:
            courants[phases[0]] += I_DEFAUT_TERRE_A
            residuel = I_DEFAUT_TERRE_A

        return courants, residuel
