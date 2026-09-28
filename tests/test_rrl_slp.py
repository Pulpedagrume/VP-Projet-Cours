"""Tests du réenclencheur (RRL) et de la sélectivité logique (SLP), sans réseau.

Un petit modèle de disjoncteur remplace la simulation : il change de
position au cycle qui suit l'ordre.
"""

from demirame.mapping import (
    ETAPE_DEFINITIF,
    ETAPE_RECUPERATION_RL,
    ETAPE_RECUPERATION_RR,
    ETAPE_REPOS,
    ETAPE_TEMPS_MORT_RL,
    ETAPE_TEMPS_MORT_RR,
    ORIGINE_PHASE,
    ORIGINE_SLP,
    RESULTAT_DEFINITIF,
    RESULTAT_REUSSI_RL,
    RESULTAT_REUSSI_RR,
)
from demirame.protection import (
    TEMPO_PHASE_ARRIVEE_MS,
    TEMPO_PHASE_MS,
    TEMPO_SLP_MS,
    TEMPS_MORT_RL_MS,
    TEMPS_MORT_RR_MS,
    TEMPS_RECUPERATION_MS,
    ProtectionArrivee,
    ProtectionDepart,
)

DT = 20
CHARGE = [200, 200, 200]
DEFAUT = [4000, 4000, 4000]


class Depart:
    """Un départ : protection + disjoncteur + défaut qui peut disparaître."""

    def __init__(self, rrl=True):
        self.p = ProtectionDepart()
        self.p.reenclencheur.en_service = rrl
        self.dj_ferme = True
        self.defaut = False
        self.hors_tension_ms = 0

    def cycle(self, nature=None, acr_ouverture=False, acr_fermeture=False, acquittement=False):
        courants = DEFAUT if (self.defaut and self.dj_ferme) else (CHARGE if self.dj_ferme else [0, 0, 0])
        self.p.cycle(courants, 0, self.dj_ferme, acr_ouverture, acr_fermeture, acquittement, DT)
        # Disjoncteur : obéit aux ordres au cycle suivant
        if self.p.disjoncteur.ordre_ouverture:
            self.dj_ferme = False
        elif self.p.disjoncteur.ordre_fermeture:
            self.dj_ferme = True
        # Extinction du défaut selon sa nature
        if self.defaut and not self.dj_ferme:
            self.hors_tension_ms += DT
            if nature == "fugitif" or (nature == "semi" and self.hors_tension_ms >= 5000):
                self.defaut = False
        else:
            self.hors_tension_ms = 0

    def attendre(self, duree_ms, **kw):
        for _ in range(duree_ms // DT):
            self.cycle(**kw)


# --- Réenclencheur -----------------------------------------------------------

def test_defaut_fugitif_elimine_par_le_rr():
    d = Depart()
    d.defaut = True
    d.attendre(TEMPO_PHASE_MS + 100, nature="fugitif")
    assert not d.dj_ferme
    assert d.p.reenclencheur.etape == ETAPE_TEMPS_MORT_RR
    d.attendre(TEMPS_MORT_RR_MS + 100, nature="fugitif")
    assert d.dj_ferme                                   # refermé automatiquement
    assert d.p.reenclencheur.etape == ETAPE_RECUPERATION_RR
    d.attendre(TEMPS_RECUPERATION_MS + 100, nature="fugitif")
    assert d.p.reenclencheur.etape == ETAPE_REPOS
    assert d.p.reenclencheur.resultat == RESULTAT_REUSSI_RR
    assert not d.p.declenchement_phase                  # indication effacée
    assert not d.p.verrouille


def test_defaut_semi_permanent_elimine_par_le_rl():
    d = Depart()
    d.defaut = True
    d.attendre(TEMPO_PHASE_MS + 100, nature="semi")
    d.attendre(TEMPS_MORT_RR_MS + 100, nature="semi")    # RR : le défaut est toujours là
    d.attendre(TEMPO_PHASE_MS + 100, nature="semi")      # 2e déclenchement
    assert not d.dj_ferme
    assert d.p.reenclencheur.etape == ETAPE_TEMPS_MORT_RL
    d.attendre(TEMPS_MORT_RL_MS + 100, nature="semi")    # 15 s hors tension : le défaut a disparu
    assert d.dj_ferme
    assert d.p.reenclencheur.etape == ETAPE_RECUPERATION_RL
    d.attendre(TEMPS_RECUPERATION_MS + 100, nature="semi")
    assert d.p.reenclencheur.resultat == RESULTAT_REUSSI_RL
    assert d.p.releve.nb_declenchements == 2


def test_defaut_permanent_declenchement_definitif():
    d = Depart()
    d.defaut = True
    d.attendre(TEMPO_PHASE_MS + TEMPS_MORT_RR_MS + TEMPO_PHASE_MS + TEMPS_MORT_RL_MS
               + TEMPO_PHASE_MS + 1000, nature="permanent")
    assert not d.dj_ferme
    assert d.p.verrouille
    assert d.p.reenclencheur.etape == ETAPE_DEFINITIF
    assert d.p.reenclencheur.resultat == RESULTAT_DEFINITIF
    assert d.p.releve.nb_declenchements == 3

    # Fermeture refusée tant que non acquitté
    d.attendre(200, acr_fermeture=True)
    assert not d.dj_ferme
    # Réparation, acquittement, fermeture
    d.defaut = False
    d.attendre(100, acquittement=True)
    d.attendre(100, acr_fermeture=True)
    assert d.dj_ferme
    assert not d.p.verrouille


def test_rrl_hors_service_definitif_des_le_premier_declenchement():
    d = Depart(rrl=False)
    d.defaut = True
    d.attendre(TEMPO_PHASE_MS + 1000, nature="fugitif")
    assert not d.dj_ferme
    assert d.p.verrouille


def test_commande_acr_interrompt_le_cycle():
    d = Depart()
    d.defaut = True
    d.attendre(TEMPO_PHASE_MS + 100, nature="fugitif")
    assert d.p.reenclencheur.etape == ETAPE_TEMPS_MORT_RR
    d.cycle(acr_ouverture=True)
    assert d.p.reenclencheur.etape == ETAPE_REPOS
    d.attendre(TEMPS_MORT_RR_MS + 200)
    assert not d.dj_ferme                                 # pas de refermeture automatique


# --- Sélectivité logique ---------------------------------------------------------

def faire_cycles(arrivee, nb, courants, attente_logique, **kw):
    for _ in range(nb):
        arrivee.cycle(courants, 0, True, attente_logique,
                      kw.get("acr_ouverture", False), False, False, DT)


def test_defaut_barre_declenchement_accelere_par_la_slp():
    a = ProtectionArrivee()
    faire_cycles(a, TEMPO_SLP_MS // DT, [8000] * 3, attente_logique=False)
    assert not a.disjoncteur.ordre_ouverture
    faire_cycles(a, 1, [8000] * 3, attente_logique=False)
    assert a.disjoncteur.ordre_ouverture                  # 200 ms au lieu de 1000 ms
    assert a.declenchement_slp
    assert a.releve.origine == ORIGINE_PHASE | ORIGINE_SLP
    assert a.verrouille


def test_defaut_depart_l_arrivee_attend_sa_tempo_longue():
    a = ProtectionArrivee()
    # Un départ voit le défaut : attente logique -> pas de déclenchement rapide
    faire_cycles(a, TEMPO_PHASE_MS // DT + 5, [4600] * 3, attente_logique=True)
    assert not a.disjoncteur.ordre_ouverture
    # Secours : si le départ n'a pas éliminé le défaut, l'arrivée déclenche
    faire_cycles(a, (TEMPO_PHASE_ARRIVEE_MS - TEMPO_PHASE_MS) // DT, [4600] * 3, attente_logique=True)
    assert a.disjoncteur.ordre_ouverture
    assert not a.declenchement_slp


def test_slp_hors_service_defaut_barre_elimine_en_tempo_longue():
    a = ProtectionArrivee()
    a.slp_en_service = False
    faire_cycles(a, TEMPO_PHASE_ARRIVEE_MS // DT, [8000] * 3, attente_logique=False)
    assert not a.disjoncteur.ordre_ouverture
    faire_cycles(a, 1, [8000] * 3, attente_logique=False)
    assert a.disjoncteur.ordre_ouverture
    assert not a.declenchement_slp
