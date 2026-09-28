"""Modèle du procédé : le poste HTA « physique » (disjoncteurs, courants, tensions).

Ce fichier ne fait AUCUNE communication réseau : on lui donne les ordres
de l'automate et les défauts injectés, il calcule l'état du poste.

PHASEURS (représentation de Fresnel)
------------------------------------
Chaque grandeur sinusoïdale (courant ou tension d'une phase) est un
PHASEUR : un nombre complexe dont le module est la valeur efficace et
l'argument le déphasage. Python sait calculer avec les complexes :
    cmath.rect(module, angle_en_radians)  -> crée un phaseur
    abs(z)                                -> module
    cmath.phase(z)                        -> angle (radians)

Référence : V1 à 0°, V2 à -120°, V3 à +120° (système direct).
Le courant résiduel est la somme vectorielle : Io = I1 + I2 + I3.

DÉFAUTS FRANCS (sans résistance de défaut)
------------------------------------------
| Phases | Terre | Type de défaut   | Courants                                     |
|--------|-------|------------------|----------------------------------------------|
| 1      | oui   | monophasé terre  | + 300 A en phase avec la tension de la phase |
| 2      | non   | biphasé isolé    | Icc2 = 0,866 x Icc3, opposés sur les 2 phases|
| 2      | oui   | biphasé terre    | Icc2 + courant de terre 300 A                |
| 3      | -     | triphasé         | Icc3 sur les 3 phases, système équilibré     |
| 1      | non   | aucun (une phase isolée ne fait pas de défaut)                  |

Le neutre HTA est mis à la terre par une résistance : le courant de défaut
à la terre est limité (300 A) et en phase avec la tension qui le crée.
Les courants de court-circuit sont en retard de 75° sur leur tension
(réseau surtout inductif). La charge a un cos phi de 0,9.
"""

import cmath
import math
import random

from demirame.mapping import BIT_TERRE, BITS_PHASES, NB_BLOCS, NB_DEPARTS

TENSION_COMPOSEE_KV = 20.0
TENSION_SIMPLE_KV = TENSION_COMPOSEE_KV / math.sqrt(3)   # 11,55 kV
BRUIT_TENSION = 0.005                # ± 0,5 %
CHARGE_DEPARTS_A = [150, 250, 200]   # courant de charge de chaque départ
BRUIT_CHARGE = 0.02                  # ± 2 %
DEPHASAGE_CHARGE_DEG = 25.8          # cos phi = 0,9
ANGLE_COURT_CIRCUIT_DEG = 75         # retard du courant de court-circuit
ICC_TRIPHASE_A = 4000                # courant de court-circuit triphasé
ICC_BIPHASE_A = round(math.sqrt(3) / 2 * ICC_TRIPHASE_A)   # 3464 A
I_DEFAUT_TERRE_A = 300               # limité par la résistance de neutre
PROFONDEUR_CREUX = 0.4               # le jeu de barres « voit » 40 % de la chute du point de défaut
TEMPS_OUVERTURE_DJ_MS = 60           # temps de manœuvre d'un disjoncteur HTA
TEMPS_FERMETURE_DJ_MS = 80

# Indice des disjoncteurs dans les listes : 0 = arrivée, 1..3 = départs
ARRIVEE = 0


def phaseur(module, angle_deg):
    """Crée un phaseur (nombre complexe) à partir d'un module et d'un angle en degrés."""
    return cmath.rect(module, math.radians(angle_deg))


def angle_deg(z):
    """Angle d'un phaseur en degrés, entre 0 et 360."""
    return math.degrees(cmath.phase(z)) % 360


# Tensions simples avant défaut : V1 à 0°, V2 à -120°, V3 à +120°
TENSIONS_NORMALES = [phaseur(TENSION_SIMPLE_KV, a) for a in (0, -120, 120)]


def phases_du_defaut(defaut):
    """Liste des indices de phases touchées (0 = L1, 1 = L2, 2 = L3)."""
    return [i for i, bit in enumerate(BITS_PHASES) if defaut & bit]


def type_defaut(defaut):
    """Nom du défaut correspondant aux bits (affiché dans les journaux)."""
    n = len(phases_du_defaut(defaut))
    terre = bool(defaut & BIT_TERRE)
    if n == 3:
        return "triphasé"
    if n == 2:
        return "biphasé terre" if terre else "biphasé isolé"
    if n == 1 and terre:
        return "monophasé terre"
    return "aucun"


def tensions_au_point_de_defaut(defaut):
    """Tensions simples (par rapport à la terre) au point de défaut franc."""
    v = list(TENSIONS_NORMALES)
    phases = phases_du_defaut(defaut)
    terre = bool(defaut & BIT_TERRE)
    if len(phases) == 3:
        return [0j, 0j, 0j]
    if len(phases) == 2:
        b, c = phases
        commun = (v[b] + v[c]) / 2          # les deux phases sont reliées entre elles
        if terre:
            # ... et à la terre : ce point est à 0 V, tout le système se décale
            return [x - commun for x in [commun if i in phases else v[i] for i in range(3)]]
        v[b] = v[c] = commun
        return v
    if len(phases) == 1 and terre:
        a = phases[0]
        return [x - v[a] for x in v]         # la phase touchée est à 0 V : le neutre se décale
    return v


class Poste:
    """État du poste : 1 arrivée + 3 départs, phaseurs de courant et de tension."""

    def __init__(self):
        self.dj_ferme = [True] * NB_BLOCS        # au départ tout est fermé
        self.manoeuvre_ms = [0] * NB_BLOCS       # temps écoulé depuis l'ordre
        # courants[bloc] = [I1, I2, I3] (phaseurs en A) ; bloc 0 = arrivée
        self.courants = [[0j, 0j, 0j] for _ in range(NB_BLOCS)]
        self.tensions = [0j, 0j, 0j]             # tensions simples du jeu de barres (kV)

    # ---------------- Grandeurs déduites ----------------

    def courant_residuel(self, bloc):
        """Io = I1 + I2 + I3 (somme vectorielle)."""
        return sum(self.courants[bloc])

    @property
    def tension_residuelle(self):
        """V0 = (V1 + V2 + V3) / 3 : déplacement du point neutre (kV)."""
        return sum(self.tensions) / 3

    @property
    def tension_kv(self):
        """Moyenne des trois tensions composées U12, U23, U31 (kV)."""
        v = self.tensions
        return (abs(v[0] - v[1]) + abs(v[1] - v[2]) + abs(v[2] - v[0])) / 3

    # ---------------- Évolution ----------------

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
        if not self.dj_ferme[ARRIVEE]:
            # Barre hors tension : plus rien
            self.courants = [[0j, 0j, 0j] for _ in range(NB_BLOCS)]
            self.tensions = [0j, 0j, 0j]
            return

        # Courants de chaque départ
        defaut_actif = 0
        for n in range(NB_DEPARTS):
            bloc = n + 1
            if self.dj_ferme[bloc]:
                self.courants[bloc] = self._courants_depart(n, defauts[n])
                if type_defaut(defauts[n]) != "aucun":
                    defaut_actif = defauts[n]
            else:
                self.courants[bloc] = [0j, 0j, 0j]

        # L'arrivée alimente tous les départs : somme vectorielle phase par phase
        self.courants[ARRIVEE] = [
            sum(self.courants[bloc][p] for bloc in range(1, NB_BLOCS)) for p in range(3)
        ]

        # Tensions du jeu de barres
        point_defaut = tensions_au_point_de_defaut(defaut_actif)
        if type_defaut(defaut_actif) == "monophasé terre":
            profondeur = 1.0   # courant limité : pas de chute, le neutre se décale partout
        else:
            profondeur = PROFONDEUR_CREUX
        self.tensions = [
            (v + profondeur * (vd - v)) * (1 + random.uniform(-BRUIT_TENSION, BRUIT_TENSION))
            for v, vd in zip(TENSIONS_NORMALES, point_defaut)
        ]

    def _courants_depart(self, n, defaut):
        """Phaseurs [I1, I2, I3] d'un départ sous tension."""
        v = TENSIONS_NORMALES
        # Charge : en retard de 25,8° sur la tension de sa phase
        courants = [
            phaseur(CHARGE_DEPARTS_A[n] * (1 + random.uniform(-BRUIT_CHARGE, BRUIT_CHARGE)),
                    angle_deg(v[p]) - DEPHASAGE_CHARGE_DEG)
            for p in range(3)
        ]

        phases = phases_du_defaut(defaut)
        terre = bool(defaut & BIT_TERRE)

        if len(phases) == 3:
            # Triphasé : Icc3 en retard de 75° sur chaque tension simple
            courants = [phaseur(ICC_TRIPHASE_A, angle_deg(v[p]) - ANGLE_COURT_CIRCUIT_DEG)
                        for p in range(3)]
        elif len(phases) == 2:
            # Biphasé : le courant de défaut circule de la phase b vers la phase c,
            # poussé par la tension composée Ubc ; il s'ajoute à la charge
            b, c = phases
            icc2 = phaseur(ICC_BIPHASE_A, angle_deg(v[b] - v[c]) - ANGLE_COURT_CIRCUIT_DEG)
            courants[b] += icc2
            courants[c] -= icc2
            if terre:
                # Courant de terre : poussé par la tension du point commun (Vb + Vc) / 2
                i_terre = phaseur(I_DEFAUT_TERRE_A, angle_deg(v[b] + v[c]))
                courants[b] += i_terre / 2
                courants[c] += i_terre / 2
        elif len(phases) == 1 and terre:
            # Monophasé terre : courant en phase avec la tension de la phase touchée
            a = phases[0]
            courants[a] += phaseur(I_DEFAUT_TERRE_A, angle_deg(v[a]))

        return courants
