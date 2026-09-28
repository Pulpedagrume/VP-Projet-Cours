"""Modèle du procédé : le poste HTA « physique » (disjoncteurs, courants, tension).

Ce fichier ne fait AUCUNE communication réseau : on lui donne les ordres
de l'automate et les défauts injectés, il calcule l'état du poste.
"""

import random

from demirame.mapping import (
    ARRIVEE,
    DEFAUT_PHASE,
    DEFAUT_TERRE,
    NB_DEPARTS,
    NB_DJ,
)

TENSION_NOMINALE_KV = 20.0
BRUIT_TENSION_KV = 0.2
CHARGE_DEPARTS_A = [150, 250, 200]  # courant de charge normal de chaque départ
BRUIT_CHARGE = 0.03                 # ± 3 %
IO_NORMAL_MAX_A = 3                 # petit courant résiduel en fonctionnement normal
COURANT_COURT_CIRCUIT_A = 4000      # défaut phase franc
COURANT_DEFAUT_TERRE_A = 300        # défaut terre franc (limité par le neutre)
TEMPS_MANOEUVRE_MS = 100            # temps de manœuvre d'un disjoncteur


class Poste:
    """État du poste : 3 départs + 1 arrivée."""

    def __init__(self):
        self.dj_ferme = [True] * NB_DJ           # au départ tout est fermé
        self.manoeuvre_ms = [0] * NB_DJ          # temps écoulé depuis l'ordre
        self.courant_depart = [0] * NB_DEPARTS
        self.courant_residuel = [0] * NB_DEPARTS
        self.courant_arrivee = 0
        self.tension_kv = 0.0

    def pas(self, ordres_ouverture, ordres_fermeture, defauts, dt_ms):
        """Fait avancer la simulation de dt_ms millisecondes.

        ordres_ouverture, ordres_fermeture : listes de 4 booléens (départs 1-3, arrivée)
        defauts : liste de 3 codes (AUCUN_DEFAUT, DEFAUT_PHASE, DEFAUT_TERRE)
        """
        self._manoeuvrer_disjoncteurs(ordres_ouverture, ordres_fermeture, dt_ms)
        self._calculer_mesures(defauts)

    def _manoeuvrer_disjoncteurs(self, ordres_ouverture, ordres_fermeture, dt_ms):
        for i in range(NB_DJ):
            # Un ordre n'a d'effet que s'il demande de changer de position.
            veut_ouvrir = ordres_ouverture[i] and self.dj_ferme[i]
            veut_fermer = ordres_fermeture[i] and not self.dj_ferme[i]
            if veut_ouvrir or veut_fermer:
                self.manoeuvre_ms[i] += dt_ms
                if self.manoeuvre_ms[i] >= TEMPS_MANOEUVRE_MS:
                    self.dj_ferme[i] = not self.dj_ferme[i]
                    self.manoeuvre_ms[i] = 0
            else:
                self.manoeuvre_ms[i] = 0

    def _calculer_mesures(self, defauts):
        barre_alimentee = self.dj_ferme[ARRIVEE]

        if barre_alimentee:
            bruit = random.uniform(-BRUIT_TENSION_KV, BRUIT_TENSION_KV)
            self.tension_kv = TENSION_NOMINALE_KV + bruit
        else:
            self.tension_kv = 0.0

        for n in range(NB_DEPARTS):
            if barre_alimentee and self.dj_ferme[n]:
                bruit = random.uniform(-BRUIT_CHARGE, BRUIT_CHARGE)
                courant = CHARGE_DEPARTS_A[n] * (1 + bruit)
                residuel = random.uniform(0, IO_NORMAL_MAX_A)
                if defauts[n] == DEFAUT_PHASE:
                    courant = COURANT_COURT_CIRCUIT_A
                elif defauts[n] == DEFAUT_TERRE:
                    courant += COURANT_DEFAUT_TERRE_A
                    residuel = COURANT_DEFAUT_TERRE_A
            else:
                # DJ ouvert ou barre hors tension : plus de courant
                courant = 0
                residuel = 0
            self.courant_depart[n] = round(courant)
            self.courant_residuel[n] = round(residuel)

        self.courant_arrivee = sum(self.courant_depart)
