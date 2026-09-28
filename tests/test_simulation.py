"""Tests du modèle du poste (simulation.py), sans réseau."""

from demirame.mapping import AUCUN_DEFAUT, DEFAUT_PHASE, DEFAUT_TERRE
from demirame.simulation import COURANT_COURT_CIRCUIT_A, COURANT_DEFAUT_TERRE_A, Poste

DT = 100
AUCUN_ORDRE = [False] * 4
SANS_DEFAUT = [AUCUN_DEFAUT] * 3


def test_fonctionnement_normal():
    poste = Poste()
    poste.pas(AUCUN_ORDRE, AUCUN_ORDRE, SANS_DEFAUT, DT)
    assert 19.8 <= poste.tension_kv <= 20.2
    assert all(100 <= i <= 300 for i in poste.courant_depart)
    assert all(io <= 3 for io in poste.courant_residuel)
    assert poste.courant_arrivee == sum(poste.courant_depart)


def test_court_circuit_franc():
    poste = Poste()
    poste.pas(AUCUN_ORDRE, AUCUN_ORDRE, [AUCUN_DEFAUT, DEFAUT_PHASE, AUCUN_DEFAUT], DT)
    assert poste.courant_depart[1] == COURANT_COURT_CIRCUIT_A
    assert poste.courant_depart[0] < 800


def test_defaut_terre_franc():
    poste = Poste()
    poste.pas(AUCUN_ORDRE, AUCUN_ORDRE, [DEFAUT_TERRE, AUCUN_DEFAUT, AUCUN_DEFAUT], DT)
    assert poste.courant_residuel[0] == COURANT_DEFAUT_TERRE_A
    assert poste.courant_depart[0] < 800  # invisible pour la protection phase


def test_ouverture_dj_coupe_le_courant():
    poste = Poste()
    ouvrir_depart_1 = [True, False, False, False]
    poste.pas(ouvrir_depart_1, AUCUN_ORDRE, [DEFAUT_PHASE, AUCUN_DEFAUT, AUCUN_DEFAUT], DT)
    assert not poste.dj_ferme[0]
    assert poste.courant_depart[0] == 0
    assert poste.courant_residuel[0] == 0


def test_fermeture_dj():
    poste = Poste()
    poste.dj_ferme[2] = False
    poste.pas(AUCUN_ORDRE, [False, False, True, False], SANS_DEFAUT, DT)
    assert poste.dj_ferme[2]


def test_arrivee_ouverte_barre_hors_tension():
    poste = Poste()
    ouvrir_arrivee = [False, False, False, True]
    poste.pas(ouvrir_arrivee, AUCUN_ORDRE, SANS_DEFAUT, DT)
    assert poste.tension_kv == 0
    assert poste.courant_depart == [0, 0, 0]
    assert poste.courant_arrivee == 0
