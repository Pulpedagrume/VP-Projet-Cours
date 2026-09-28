"""Mode aléatoire : la vie « normale » d'un poste source, accélérée.

Quand le mode est en marche (bouton sur la page Banc de test de l'IHM) :
1. la charge des départs suit une courbe lente (une « journée » en 3 minutes)
   avec de petites variations aléatoires ;
2. de temps en temps (en moyenne toutes les 40 s) un défaut apparaît, tiré
   au hasard avec des proportions proches de la réalité ;
3. un défaut permanent est « réparé » par l'équipe d'intervention 60 s après
   son apparition. Le départ reste ensuite verrouillé : l'opérateur doit
   acquitter et refermer depuis l'IHM.

Ce fichier ne fait pas de réseau : il agit sur un objet Poste (simulation.py).
"""

import math
import random

from demirame.mapping import (
    BIT_L1,
    BIT_L2,
    BIT_L3,
    BIT_TERRE,
    NATURE_FUGITIF,
    NATURE_PERMANENT,
    NATURE_SEMI_PERMANENT,
    NB_BLOCS,
)
from demirame.simulation import BARRE, CHARGE_DEPARTS_A

INTERVALLE_MOYEN_S = 40          # temps moyen entre deux défauts
DUREE_REPARATION_S = 60          # un défaut permanent est réparé au bout de 60 s
PERIODE_JOURNEE_S = 180          # la courbe de charge fait un cycle en 3 minutes
AMPLITUDE_JOURNEE = 0.30         # la charge varie de ± 30 %

# Tirages : (valeur, poids). Les poids reflètent les statistiques des réseaux
# aériens : surtout des défauts à la terre, surtout fugitifs.
LIEUX = [("depart", 95), ("barre", 5)]
TYPES = [("monophasé terre", 70), ("biphasé isolé", 12), ("biphasé terre", 8), ("triphasé", 10)]
NATURES = [(NATURE_FUGITIF, 70), (NATURE_SEMI_PERMANENT, 20), (NATURE_PERMANENT, 10)]
NOMS_NATURES = {NATURE_FUGITIF: "fugitif", NATURE_SEMI_PERMANENT: "semi-permanent",
                NATURE_PERMANENT: "permanent"}


def tirer(rng, choix):
    """Tire une valeur dans une liste de (valeur, poids)."""
    valeurs = [v for v, _ in choix]
    poids = [p for _, p in choix]
    return rng.choices(valeurs, weights=poids)[0]


class ModeAleatoire:
    def __init__(self, graine=None):
        self.rng = random.Random(graine)   # graine fixe = tirages reproductibles (tests)
        self.temps_s = 0.0
        self.age_defaut_s = [0.0] * NB_BLOCS   # depuis quand chaque défaut permanent existe

    def pas(self, poste, dt_ms):
        """Fait évoluer le poste pendant dt_ms. Renvoie un texte si un défaut apparaît."""
        dt = dt_ms / 1000
        self.temps_s += dt
        self._faire_varier_la_charge(poste)
        self._reparer(poste, dt)

        # Un seul défaut à la fois, et seulement sur un poste sous tension
        if any(poste.defauts) or not poste.dj_ferme[BARRE]:
            return None
        if self.rng.random() < dt / INTERVALLE_MOYEN_S:
            return self._creer_defaut(poste)
        return None

    def _faire_varier_la_charge(self, poste):
        for n, nominal in enumerate(CHARGE_DEPARTS_A):
            journee = math.sin(2 * math.pi * self.temps_s / PERIODE_JOURNEE_S + n)
            poste.charges[n] = nominal * (1 + AMPLITUDE_JOURNEE * journee)

    def _reparer(self, poste, dt):
        for bloc in range(NB_BLOCS):
            if poste.defauts[bloc] and poste.natures[bloc] == NATURE_PERMANENT:
                self.age_defaut_s[bloc] += dt
                if self.age_defaut_s[bloc] >= DUREE_REPARATION_S:
                    poste.injecter(bloc, 0)         # réparé par l'équipe d'intervention
            else:
                self.age_defaut_s[bloc] = 0.0

    def _creer_defaut(self, poste):
        if tirer(self.rng, LIEUX) == "barre":
            bloc = BARRE
        else:
            alimentes = [b for b in (1, 2, 3) if poste.sous_tension(b)]
            if not alimentes:
                return None
            bloc = self.rng.choice(alimentes)

        type_ = tirer(self.rng, TYPES)
        phases = [BIT_L1, BIT_L2, BIT_L3]
        if type_ == "monophasé terre":
            defaut = self.rng.choice(phases) | BIT_TERRE
        elif type_ == "triphasé":
            defaut = BIT_L1 | BIT_L2 | BIT_L3
        else:
            a, b = self.rng.sample(phases, 2)
            defaut = a | b | (BIT_TERRE if type_ == "biphasé terre" else 0)

        nature = tirer(self.rng, NATURES)
        poste.injecter(bloc, defaut, nature)
        lieu = "jeu de barres" if bloc == BARRE else f"départ {bloc}"
        return f"défaut {type_} {NOMS_NATURES[nature]} sur le {lieu}"


def arreter(poste):
    """Arrêt du mode aléatoire : les charges reviennent à leur valeur nominale."""
    poste.charges[:] = CHARGE_DEPARTS_A
