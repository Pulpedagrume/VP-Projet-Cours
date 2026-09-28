"""Tests du modèle du poste (simulation.py), sans réseau."""

import math

import pytest

from demirame.mapping import BIT_L1, BIT_L2, BIT_L3, BIT_TERRE
from demirame.simulation import (
    ANGLE_COURT_CIRCUIT_DEG,
    ICC_BIPHASE_A,
    ICC_TRIPHASE_A,
    I_DEFAUT_TERRE_A,
    TEMPS_OUVERTURE_DJ_MS,
    TENSION_SIMPLE_KV,
    Poste,
    angle_deg,
    tensions_au_point_de_defaut,
    type_defaut,
)

DT = 10
AUCUN_ORDRE = [False] * 4
SANS_DEFAUT = [0, 0, 0]


def poste_avec_defaut(defaut_depart_1):
    poste = Poste()
    poste.pas(AUCUN_ORDRE, AUCUN_ORDRE, [defaut_depart_1, 0, 0], DT)
    return poste


def modules(courants):
    return [abs(i) for i in courants]


def ecart_angle(a, b):
    """Écart entre deux angles en degrés, entre -180 et 180."""
    return (a - b + 180) % 360 - 180


# --- Fonctionnement normal -------------------------------------------------

def test_fonctionnement_normal():
    poste = poste_avec_defaut(0)
    assert 19.8 <= poste.tension_kv <= 20.2
    for bloc in (1, 2, 3):
        assert all(100 <= i <= 300 for i in modules(poste.courants[bloc]))
        assert abs(poste.courant_residuel(bloc)) < 15   # petit déséquilibre
    assert abs(poste.tension_residuelle) < 0.2


def test_systeme_direct_et_cos_phi():
    poste = poste_avec_defaut(0)
    v = poste.tensions
    assert ecart_angle(angle_deg(v[1]), angle_deg(v[0])) == pytest.approx(-120, abs=1)
    # Le courant de charge est en retard d'environ 25,8° (cos phi = 0,9)
    retard = ecart_angle(angle_deg(v[0]), angle_deg(poste.courants[1][0]))
    assert retard == pytest.approx(25.8, abs=1)


def test_arrivee_somme_vectorielle_des_departs():
    poste = poste_avec_defaut(0)
    for p in range(3):
        somme = sum(poste.courants[b][p] for b in (1, 2, 3))
        assert abs(poste.courants[0][p] - somme) < 1e-9


# --- Défauts ---------------------------------------------------------------

def test_triphase():
    poste = poste_avec_defaut(BIT_L1 | BIT_L2 | BIT_L3)
    assert modules(poste.courants[1]) == pytest.approx([ICC_TRIPHASE_A] * 3)
    assert abs(poste.courant_residuel(1)) < 1        # système équilibré
    assert poste.tension_kv == pytest.approx(12, abs=0.2)   # creux à 60 %
    retard = ecart_angle(angle_deg(poste.tensions[0]), angle_deg(poste.courants[1][0]))
    assert retard == pytest.approx(ANGLE_COURT_CIRCUIT_DEG, abs=1)


def test_biphase_isole_courants_opposes():
    poste = poste_avec_defaut(BIT_L2 | BIT_L3)
    i1, i2, i3 = poste.courants[1]
    assert abs(i2) == pytest.approx(ICC_BIPHASE_A, abs=300)   # Icc2 + charge
    assert abs(i3) == pytest.approx(ICC_BIPHASE_A, abs=300)
    # Les courants de défaut sont opposés : leur somme se réduit à la charge
    assert abs(i2 + i3) < 300
    assert abs(i1) < 300                              # phase saine
    assert abs(poste.courant_residuel(1)) < 15


def test_biphase_terre():
    poste = poste_avec_defaut(BIT_L1 | BIT_L2 | BIT_TERRE)
    assert all(abs(i) > 3000 for i in poste.courants[1][:2])
    assert abs(poste.courant_residuel(1)) == pytest.approx(I_DEFAUT_TERRE_A, abs=15)


def test_monophase_terre():
    poste = poste_avec_defaut(BIT_L3 | BIT_TERRE)
    io = poste.courant_residuel(1)
    assert abs(io) == pytest.approx(I_DEFAUT_TERRE_A, abs=15)
    assert 400 < abs(poste.courants[1][2]) < 800      # invisible pour I> (800 A)
    # La tension de la phase en défaut s'effondre, les autres montent à 20 kV
    assert abs(poste.tensions[2]) < 0.2
    assert abs(poste.tensions[0]) == pytest.approx(20, abs=0.3)
    # Tension composée inchangée : pas de creux vu par les clients
    assert poste.tension_kv > 19.5
    # Io est en opposition de phase avec V0 (base des protections directionnelles)
    v0 = poste.tension_residuelle
    assert abs(v0) == pytest.approx(TENSION_SIMPLE_KV, abs=0.2)
    assert abs(ecart_angle(angle_deg(io), angle_deg(v0))) == pytest.approx(180, abs=5)


def test_une_phase_sans_terre_n_est_pas_un_defaut():
    poste = poste_avec_defaut(BIT_L1)
    assert all(abs(i) < 300 for i in poste.courants[1])
    assert type_defaut(BIT_L1) == "aucun"


def test_tensions_au_point_de_defaut():
    v_tri = tensions_au_point_de_defaut(BIT_L1 | BIT_L2 | BIT_L3)
    assert all(abs(v) == 0 for v in v_tri)
    v_bi = tensions_au_point_de_defaut(BIT_L2 | BIT_L3)
    assert abs(v_bi[1] - v_bi[2]) < 1e-9             # V2 = V3
    v_mono = tensions_au_point_de_defaut(BIT_L1 | BIT_TERRE)
    assert abs(v_mono[0]) < 1e-9
    assert abs(v_mono[1]) == pytest.approx(TENSION_SIMPLE_KV * math.sqrt(3))


# --- Disjoncteurs ----------------------------------------------------------

def test_temps_d_ouverture_du_disjoncteur():
    poste = Poste()
    ouvrir_depart_1 = [False, True, False, False]
    for _ in range(TEMPS_OUVERTURE_DJ_MS // DT - 1):
        poste.pas(ouvrir_depart_1, AUCUN_ORDRE, SANS_DEFAUT, DT)
    assert poste.dj_ferme[1]
    poste.pas(ouvrir_depart_1, AUCUN_ORDRE, SANS_DEFAUT, DT)
    assert not poste.dj_ferme[1]
    assert modules(poste.courants[1]) == [0, 0, 0]


def test_arrivee_ouverte_barre_hors_tension():
    poste = Poste()
    ouvrir_arrivee = [True, False, False, False]
    for _ in range(10):
        poste.pas(ouvrir_arrivee, AUCUN_ORDRE, SANS_DEFAUT, DT)
    assert poste.tension_kv == 0
    assert all(modules(poste.courants[b]) == [0, 0, 0] for b in range(4))
