"""Modèle du procédé : le poste HTA « physique » (disjoncteurs, courants, tensions).

Ce fichier ne fait AUCUNE communication réseau : on lui donne les ordres
de l'automate et les défauts à créer, il calcule l'état du poste.

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
| Phases | Terre | Type de défaut   | Courants de défaut                           |
|--------|-------|------------------|----------------------------------------------|
| 1      | oui   | monophasé terre  | 300 A en phase avec la tension de la phase   |
| 2      | non   | biphasé isolé    | Icc2 = 0,866 x Icc3, opposés sur les 2 phases|
| 2      | oui   | biphasé terre    | Icc2 + courant de terre 300 A                |
| 3      | -     | triphasé         | Icc3 sur les 3 phases, système équilibré     |
| 1      | non   | aucun (une phase isolée ne fait pas de défaut)                  |

Un défaut peut être sur un départ (bloc 1 à 3) ou sur le jeu de barres
(bloc 0) : dans ce cas seule l'arrivée voit le courant de défaut.

NATURE DU DÉFAUT
----------------
- fugitif        : disparaît dès que le circuit est mis hors tension ;
- semi-permanent : disparaît s'il reste hors tension au moins 5 s ;
- permanent      : reste jusqu'à la réparation (suppression sur le banc).

Le neutre HTA est mis à la terre par une résistance : le courant de défaut
à la terre est limité (300 A) et en phase avec la tension qui le crée.
Les courants de court-circuit sont en retard de 75° sur leur tension
(réseau surtout inductif). La charge a un cos phi de 0,9.
"""

import cmath
import math
import random

from demirame.mapping import (
    BIT_TERRE,
    BITS_PHASES,
    NATURE_FUGITIF,
    NATURE_PERMANENT,
    NATURE_SEMI_PERMANENT,
    NB_BLOCS,
    NB_DEPARTS,
)

TENSION_COMPOSEE_KV = 20.0
TENSION_SIMPLE_KV = TENSION_COMPOSEE_KV / math.sqrt(3)   # 11,55 kV
BRUIT_TENSION = 0.005                # ± 0,5 %
CHARGE_DEPARTS_A = [150, 250, 200]   # courant de charge nominal de chaque départ
BRUIT_CHARGE = 0.02                  # ± 2 %
DEPHASAGE_CHARGE_DEG = 25.8          # cos phi = 0,9
ANGLE_COURT_CIRCUIT_DEG = 75         # retard du courant de court-circuit
ICC_TRIPHASE_A = 4000                # court-circuit triphasé sur un départ
ICC_TRIPHASE_BARRE_A = 8000          # sur le jeu de barres, plus près du transformateur
ICC_BIPHASE_A = round(math.sqrt(3) / 2 * ICC_TRIPHASE_A)   # 3464 A
I_DEFAUT_TERRE_A = 300               # limité par la résistance de neutre
PROFONDEUR_CREUX = 0.4               # le jeu de barres « voit » 40 % de la chute d'un défaut départ
DUREE_EXTINCTION_SEMI_PERMANENT_MS = 5000
TEMPS_OUVERTURE_DJ_MS = 60           # temps de manœuvre d'un disjoncteur HTA
TEMPS_FERMETURE_DJ_MS = 80

# Indice des disjoncteurs et des défauts dans les listes : 0 = arrivée/barre, 1..3 = départs
ARRIVEE = 0
BARRE = 0


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


def est_un_defaut(defaut):
    return type_defaut(defaut) != "aucun"


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


def courants_de_defaut(defaut, icc_triphase):
    """Phaseurs [I1, I2, I3] du seul courant de défaut (sans la charge)."""
    v = TENSIONS_NORMALES
    courants = [0j, 0j, 0j]
    phases = phases_du_defaut(defaut)
    terre = bool(defaut & BIT_TERRE)

    if len(phases) == 3:
        # Triphasé : Icc3 en retard de 75° sur chaque tension simple
        courants = [phaseur(icc_triphase, angle_deg(v[p]) - ANGLE_COURT_CIRCUIT_DEG)
                    for p in range(3)]
    elif len(phases) == 2:
        # Biphasé : le courant circule de la phase b vers la phase c,
        # poussé par la tension composée Ubc
        b, c = phases
        icc2 = phaseur(math.sqrt(3) / 2 * icc_triphase,
                       angle_deg(v[b] - v[c]) - ANGLE_COURT_CIRCUIT_DEG)
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
        courants[a] = phaseur(I_DEFAUT_TERRE_A, angle_deg(v[a]))
    return courants


class Poste:
    """État du poste : 1 arrivée + 3 départs, phaseurs de courant et de tension."""

    def __init__(self):
        self.dj_ferme = [True] * NB_BLOCS        # au départ tout est fermé
        self.manoeuvre_ms = [0] * NB_BLOCS       # temps écoulé depuis l'ordre
        self.charges = list(CHARGE_DEPARTS_A)    # courant de charge de chaque départ (A)
        # Défauts présents : defauts[bloc] = bits des phases (0 = aucun), bloc 0 = jeu de barres
        self.defauts = [0] * NB_BLOCS
        self.natures = [NATURE_PERMANENT] * NB_BLOCS
        self.hors_tension_ms = [0] * NB_BLOCS    # durée hors tension d'un circuit en défaut
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

    def sous_tension(self, bloc):
        """Le circuit du bloc est-il alimenté ? (bloc 0 = jeu de barres)"""
        barre = self.dj_ferme[ARRIVEE]
        return barre if bloc == BARRE else barre and self.dj_ferme[bloc]

    # ---------------- Défauts ----------------

    def injecter(self, bloc, defaut, nature=NATURE_PERMANENT):
        """Crée (ou supprime avec defaut = 0) un défaut sur un départ ou sur la barre."""
        self.defauts[bloc] = defaut
        self.natures[bloc] = nature if defaut else NATURE_PERMANENT
        self.hors_tension_ms[bloc] = 0

    def _eteindre_defauts(self, dt_ms):
        """Un défaut fugitif ou semi-permanent disparaît quand son circuit est coupé."""
        for bloc in range(NB_BLOCS):
            if not self.defauts[bloc] or self.sous_tension(bloc):
                self.hors_tension_ms[bloc] = 0
                continue
            self.hors_tension_ms[bloc] += dt_ms
            nature = self.natures[bloc]
            if nature == NATURE_FUGITIF or (
                nature == NATURE_SEMI_PERMANENT
                and self.hors_tension_ms[bloc] >= DUREE_EXTINCTION_SEMI_PERMANENT_MS
            ):
                self.injecter(bloc, 0)

    # ---------------- Évolution ----------------

    def pas(self, ordres_ouverture, ordres_fermeture, dt_ms):
        """Fait avancer la simulation de dt_ms millisecondes.

        ordres_ouverture, ordres_fermeture : 4 booléens (arrivée, départs 1-3)
        """
        self._manoeuvrer_disjoncteurs(ordres_ouverture, ordres_fermeture, dt_ms)
        self._eteindre_defauts(dt_ms)
        self._calculer_mesures()

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

    def _defaut_actif(self):
        """Défaut qui fixe les tensions du jeu de barres : (bits, profondeur)."""
        if est_un_defaut(self.defauts[BARRE]):
            return self.defauts[BARRE], 1.0          # défaut sur la barre elle-même
        actif = 0
        for bloc in range(1, NB_BLOCS):
            if self.sous_tension(bloc) and est_un_defaut(self.defauts[bloc]):
                if len(phases_du_defaut(self.defauts[bloc])) > len(phases_du_defaut(actif)):
                    actif = self.defauts[bloc]
        if type_defaut(actif) == "monophasé terre":
            return actif, 1.0    # courant limité : pas de chute, le neutre se décale partout
        return actif, PROFONDEUR_CREUX

    def _calculer_mesures(self):
        if not self.dj_ferme[ARRIVEE]:
            # Barre hors tension : plus rien
            self.courants = [[0j, 0j, 0j] for _ in range(NB_BLOCS)]
            self.tensions = [0j, 0j, 0j]
            return

        # 1. Tensions du jeu de barres
        defaut, profondeur = self._defaut_actif()
        point_defaut = tensions_au_point_de_defaut(defaut)
        self.tensions = [
            (v + profondeur * (vd - v)) * (1 + random.uniform(-BRUIT_TENSION, BRUIT_TENSION))
            for v, vd in zip(TENSIONS_NORMALES, point_defaut)
        ]

        # 2. Courants des départs : charge + courant de défaut éventuel
        for n in range(NB_DEPARTS):
            bloc = n + 1
            if self.dj_ferme[bloc]:
                courants = self._courants_de_charge(n)
                if est_un_defaut(self.defauts[bloc]):
                    fd = courants_de_defaut(self.defauts[bloc], ICC_TRIPHASE_A)
                    courants = [c + f for c, f in zip(courants, fd)]
                self.courants[bloc] = courants
            else:
                self.courants[bloc] = [0j, 0j, 0j]

        # 3. L'arrivée alimente les départs (somme vectorielle) et un éventuel défaut barre
        self.courants[ARRIVEE] = [
            sum(self.courants[bloc][p] for bloc in range(1, NB_BLOCS)) for p in range(3)
        ]
        if est_un_defaut(self.defauts[BARRE]):
            fd = courants_de_defaut(self.defauts[BARRE], ICC_TRIPHASE_BARRE_A)
            self.courants[ARRIVEE] = [c + f for c, f in zip(self.courants[ARRIVEE], fd)]

    def _courants_de_charge(self, n):
        """Charge d'un départ : en retard de 25,8° sur sa tension.

        Les charges HTA sont branchées entre phases (transformateurs HTA/BT) :
        leur courant suit la tension composée (il baisse pendant un creux,
        il ne change pas pendant un défaut monophasé à la terre).
        """
        rapport_tension = self.tension_kv / TENSION_COMPOSEE_KV
        courants = []
        for p in range(3):
            module = self.charges[n] * rapport_tension * (1 + random.uniform(-BRUIT_CHARGE, BRUIT_CHARGE))
            courants.append(phaseur(module, angle_deg(TENSIONS_NORMALES[p]) - DEPHASAGE_CHARGE_DEG))
        return courants
