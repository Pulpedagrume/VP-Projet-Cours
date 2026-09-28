"""Tests de la logique automate (protection.py), sans réseau.

Chaque test rejoue un scénario cycle par cycle, comme le ferait l'automate.
"""

from demirame.mapping import BIT_L1, BIT_L2, BIT_L3, BIT_TERRE, ORIGINE_PHASE, ORIGINE_TERRE
from demirame.protection import CommandeDisjoncteur, ProtectionDepart, Tempo

DT = 20  # durée d'un cycle automate en ms
CHARGE = [200, 200, 200]


def faire_cycles(p, nb_cycles, courants=CHARGE, io=0, dj_ferme=True,
                 acr_ouverture=False, acr_fermeture=False, acquittement=False):
    """Exécute plusieurs cycles avec les mêmes entrées."""
    for _ in range(nb_cycles):
        p.cycle(courants, io, dj_ferme, acr_ouverture, acr_fermeture, acquittement, DT)


def cycles_pour(duree_ms):
    """Nombre de cycles pour qu'une tempo de duree_ms arrive au bout.

    Le premier cycle (détection) compte 0 ms.
    """
    return duree_ms // DT + 1


# --- Tempo (TON) -----------------------------------------------------------

def test_tempo_compte_a_partir_du_front_montant():
    tempo = Tempo(100)
    resultats = [tempo.cycle(True, DT) for _ in range(6)]
    # 0, 20, 40, 60, 80 ms -> faux ; 100 ms -> vrai
    assert resultats == [False] * 5 + [True]


def test_tempo_repart_a_zero_si_entree_retombe():
    tempo = Tempo(100)
    for _ in range(5):
        tempo.cycle(True, DT)
    tempo.cycle(False, DT)
    assert tempo.ecoule_ms == 0
    assert tempo.cycle(True, DT) is False


# --- Commande disjoncteur --------------------------------------------------

def test_ordre_ouverture_maintenu_jusqu_au_retour_ouvert():
    dj = CommandeDisjoncteur()
    dj.cycle(dj_ferme=True, demande_ouverture=True, demande_fermeture=False)
    dj.cycle(dj_ferme=True, demande_ouverture=False, demande_fermeture=False)
    assert dj.ordre_ouverture  # le DJ n'a pas encore bougé
    dj.cycle(dj_ferme=False, demande_ouverture=False, demande_fermeture=False)
    assert not dj.ordre_ouverture


def test_ouverture_prioritaire_sur_fermeture():
    dj = CommandeDisjoncteur()
    dj.cycle(dj_ferme=True, demande_ouverture=True, demande_fermeture=True)
    assert dj.ordre_ouverture
    assert not dj.ordre_fermeture


# --- Protection départ -----------------------------------------------------

def test_fonctionnement_normal_pas_de_declenchement():
    p = ProtectionDepart()
    faire_cycles(p, 200, io=2)
    assert not p.verrouille
    assert not p.disjoncteur.ordre_ouverture


def test_triphase_declenche_apres_la_tempo_phase():
    p = ProtectionDepart()
    faire_cycles(p, cycles_pour(500) - 1, courants=[4000, 4000, 4000])
    assert p.demarrage_phase
    assert not p.disjoncteur.ordre_ouverture  # tempo en cours

    faire_cycles(p, 1, courants=[4000, 4000, 4000])
    assert p.declenchement_phase
    assert not p.declenchement_terre
    assert p.disjoncteur.ordre_ouverture
    assert p.releve.phases_defaut == BIT_L1 | BIT_L2 | BIT_L3
    assert p.releve.origine == ORIGINE_PHASE


def test_biphase_indique_les_phases_en_defaut():
    p = ProtectionDepart()
    faire_cycles(p, cycles_pour(500), courants=[3464, 3464, 200])
    assert p.declenchement_phase
    assert p.releve.phases_defaut == BIT_L1 | BIT_L2


def test_monophase_terre_vu_seulement_par_io():
    p = ProtectionDepart()
    # L3 = 200 A de charge + 300 A de défaut : sous le seuil de 800 A
    faire_cycles(p, cycles_pour(1000) - 1, courants=[200, 200, 500], io=300)
    assert not p.disjoncteur.ordre_ouverture

    faire_cycles(p, 1, courants=[200, 200, 500], io=300)
    assert p.declenchement_terre
    assert not p.declenchement_phase
    assert p.releve.phases_defaut == BIT_TERRE
    assert p.releve.origine == ORIGINE_TERRE


def test_depassement_trop_court_ne_declenche_pas():
    p = ProtectionDepart()
    faire_cycles(p, 10, courants=[4000, 200, 200])  # 180 ms seulement
    faire_cycles(p, 50)
    assert not p.verrouille
    assert p.releve.nb_declenchements == 0


def test_reglages_modifiables_et_bornes():
    p = ProtectionDepart()
    p.regler(seuil_phase=1000, tempo_phase=200, seuil_terre=0, tempo_terre=99999)
    assert p.seuil_phase == 1000
    assert p.tempo_phase.duree_ms == 200
    assert p.seuil_terre == 5          # ramené au minimum
    assert p.tempo_terre.duree_ms == 10000  # ramené au maximum

    faire_cycles(p, cycles_pour(200), courants=[1200, 200, 200])
    assert p.declenchement_phase


# --- Relevé des temps ------------------------------------------------------

def test_releve_des_temps_de_declenchement():
    p = ProtectionDepart()
    faire_cycles(p, cycles_pour(500), courants=[4000, 4000, 4000])
    assert p.releve.temps_protection == 500

    # Le DJ met 3 cycles (60 ms) à s'ouvrir
    faire_cycles(p, 3, courants=[4000, 4000, 4000])
    faire_cycles(p, 1, courants=[0, 0, 0], dj_ferme=False)
    assert p.releve.temps_ouverture_dj == 80
    assert p.releve.temps_elimination == 580
    assert p.releve.nb_declenchements == 1


def test_releve_conserve_apres_acquittement():
    p = ProtectionDepart()
    faire_cycles(p, cycles_pour(500), courants=[4000, 4000, 4000])
    faire_cycles(p, 1, courants=[0, 0, 0], dj_ferme=False)
    faire_cycles(p, 1, courants=[0, 0, 0], dj_ferme=False, acquittement=True)
    assert not p.verrouille
    assert p.releve.temps_protection == 500


# --- Verrouillage et acquittement ------------------------------------------

def test_fermeture_refusee_tant_que_non_acquitte():
    p = ProtectionDepart()
    faire_cycles(p, cycles_pour(500), courants=[4000, 4000, 4000])
    faire_cycles(p, 1, courants=[0, 0, 0], dj_ferme=False)
    faire_cycles(p, 1, courants=[0, 0, 0], dj_ferme=False, acr_fermeture=True)
    assert not p.disjoncteur.ordre_fermeture


def test_acquittement_puis_fermeture():
    p = ProtectionDepart()
    faire_cycles(p, cycles_pour(500), courants=[4000, 4000, 4000])
    faire_cycles(p, 1, courants=[0, 0, 0], dj_ferme=False, acquittement=True)
    assert not p.verrouille
    faire_cycles(p, 1, courants=[0, 0, 0], dj_ferme=False, acr_fermeture=True)
    assert p.disjoncteur.ordre_fermeture


def test_acquittement_ignore_si_defaut_toujours_present():
    p = ProtectionDepart()
    faire_cycles(p, cycles_pour(500), courants=[4000, 4000, 4000])
    faire_cycles(p, 1, courants=[4000, 4000, 4000], acquittement=True)
    assert p.declenchement_phase


def test_defaut_permanent_redeclenche_a_la_refermeture():
    p = ProtectionDepart()
    faire_cycles(p, cycles_pour(500), courants=[4000, 4000, 4000])
    faire_cycles(p, 1, courants=[0, 0, 0], dj_ferme=False, acquittement=True)
    faire_cycles(p, 1, courants=[0, 0, 0], dj_ferme=False, acr_fermeture=True)

    # Le DJ se referme sur le défaut toujours présent
    faire_cycles(p, cycles_pour(500), courants=[4000, 4000, 4000])
    assert p.declenchement_phase
    assert p.disjoncteur.ordre_ouverture
    assert p.releve.nb_declenchements == 2


def test_ouverture_et_fermeture_par_l_acr():
    p = ProtectionDepart()
    faire_cycles(p, 1, acr_ouverture=True)
    assert p.disjoncteur.ordre_ouverture
    faire_cycles(p, 1, courants=[0, 0, 0], dj_ferme=False)
    assert not p.disjoncteur.ordre_ouverture

    faire_cycles(p, 1, courants=[0, 0, 0], dj_ferme=False, acr_fermeture=True)
    assert p.disjoncteur.ordre_fermeture
    faire_cycles(p, 1, dj_ferme=True)
    assert not p.disjoncteur.ordre_fermeture
