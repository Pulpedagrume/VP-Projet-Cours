"""Tests du modèle du poste (simulation.py), sans réseau."""

from demirame.mapping import BIT_L1, BIT_L2, BIT_L3, BIT_TERRE
from demirame.simulation import (
    ICC_BIPHASE_A,
    ICC_TRIPHASE_A,
    I_DEFAUT_TERRE_A,
    TEMPS_OUVERTURE_DJ_MS,
    Poste,
    type_defaut,
)

DT = 10
AUCUN_ORDRE = [False] * 4
SANS_DEFAUT = [0, 0, 0]


def poste_avec_defaut(defaut_depart_1):
    poste = Poste()
    poste.pas(AUCUN_ORDRE, AUCUN_ORDRE, [defaut_depart_1, 0, 0], DT)
    return poste


def test_fonctionnement_normal():
    poste = poste_avec_defaut(0)
    assert 19.8 <= poste.tension_kv <= 20.2
    for bloc in (1, 2, 3):
        assert all(100 <= i <= 300 for i in poste.courants[bloc])
        assert poste.courant_residuel[bloc] <= 3
    # L'arrivée voit la somme des départs, phase par phase
    assert poste.courants[0][0] == sum(poste.courants[b][0] for b in (1, 2, 3))


def test_triphase():
    poste = poste_avec_defaut(BIT_L1 | BIT_L2 | BIT_L3)
    assert poste.courants[1] == [ICC_TRIPHASE_A] * 3
    assert poste.courant_residuel[1] <= 3
    assert poste.tension_kv < 13  # creux de tension


def test_biphase_isole():
    poste = poste_avec_defaut(BIT_L2 | BIT_L3)
    assert poste.courants[1][1:] == [ICC_BIPHASE_A, ICC_BIPHASE_A]
    assert poste.courants[1][0] < 300
    assert poste.courant_residuel[1] <= 3


def test_biphase_terre():
    poste = poste_avec_defaut(BIT_L1 | BIT_L2 | BIT_TERRE)
    assert poste.courants[1][:2] == [ICC_BIPHASE_A, ICC_BIPHASE_A]
    assert poste.courant_residuel[1] == I_DEFAUT_TERRE_A


def test_monophase_terre():
    poste = poste_avec_defaut(BIT_L3 | BIT_TERRE)
    assert poste.courant_residuel[1] == I_DEFAUT_TERRE_A
    assert 400 < poste.courants[1][2] < 800  # invisible pour I>
    assert poste.tension_kv > 19  # pas de creux de tension


def test_une_phase_sans_terre_n_est_pas_un_defaut():
    poste = poste_avec_defaut(BIT_L1)
    assert all(i < 300 for i in poste.courants[1])
    assert type_defaut(BIT_L1) == "aucun"


def test_temps_d_ouverture_du_disjoncteur():
    poste = Poste()
    ouvrir_depart_1 = [False, True, False, False]
    for _ in range(TEMPS_OUVERTURE_DJ_MS // DT - 1):
        poste.pas(ouvrir_depart_1, AUCUN_ORDRE, SANS_DEFAUT, DT)
    assert poste.dj_ferme[1]
    poste.pas(ouvrir_depart_1, AUCUN_ORDRE, SANS_DEFAUT, DT)
    assert not poste.dj_ferme[1]
    assert poste.courants[1] == [0, 0, 0]


def test_arrivee_ouverte_barre_hors_tension():
    poste = Poste()
    ouvrir_arrivee = [True, False, False, False]
    for _ in range(10):
        poste.pas(ouvrir_arrivee, AUCUN_ORDRE, SANS_DEFAUT, DT)
    assert poste.tension_kv == 0
    assert all(poste.courants[b] == [0, 0, 0] for b in range(4))
