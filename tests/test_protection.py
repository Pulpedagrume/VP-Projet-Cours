"""Tests de la logique automate (protection.py), sans réseau.

Chaque test rejoue un scénario cycle par cycle, comme le ferait l'automate.
"""

from demirame.protection import CommandeDisjoncteur, ProtectionDepart, Tempo

DT = 100  # durée d'un cycle automate en ms


def faire_cycles(protection, nb_cycles, courant=200, courant_residuel=0,
                 dj_ferme=True, acr_ouverture=False, acr_fermeture=False,
                 acquittement=False):
    """Exécute plusieurs cycles avec les mêmes entrées."""
    for _ in range(nb_cycles):
        protection.cycle(courant, courant_residuel, dj_ferme,
                         acr_ouverture, acr_fermeture, acquittement, DT)


# --- Tempo (TON) -----------------------------------------------------------

def test_tempo_monte_apres_la_duree():
    tempo = Tempo(500)
    for _ in range(4):
        assert tempo.cycle(True, DT) is False
    assert tempo.cycle(True, DT) is True  # 5 x 100 ms = 500 ms


def test_tempo_repart_a_zero_si_entree_retombe():
    tempo = Tempo(500)
    for _ in range(4):
        tempo.cycle(True, DT)
    tempo.cycle(False, DT)
    assert tempo.ecoule_ms == 0
    assert tempo.cycle(True, DT) is False


# --- Commande disjoncteur --------------------------------------------------

def test_ordre_ouverture_maintenu_jusqu_au_retour_ouvert():
    dj = CommandeDisjoncteur()
    dj.cycle(dj_ferme=True, demande_ouverture=True, demande_fermeture=False)
    assert dj.ordre_ouverture
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
    faire_cycles(p, 50, courant=250, courant_residuel=2)
    assert not p.verrouille
    assert not p.disjoncteur.ordre_ouverture


def test_court_circuit_declenche_apres_500_ms():
    p = ProtectionDepart()
    faire_cycles(p, 4, courant=4000)
    assert p.seuil_phase_depasse
    assert not p.disjoncteur.ordre_ouverture  # tempo en cours

    faire_cycles(p, 1, courant=4000)
    assert p.declenchement_phase
    assert not p.declenchement_homopolaire
    assert p.disjoncteur.ordre_ouverture


def test_defaut_terre_franc_vu_seulement_par_l_homopolaire():
    p = ProtectionDepart()
    # courant de phase = 200 A de charge + 300 A de défaut : sous le seuil 800 A
    faire_cycles(p, 9, courant=500, courant_residuel=300)
    assert not p.disjoncteur.ordre_ouverture

    faire_cycles(p, 1, courant=500, courant_residuel=300)  # 1000 ms
    assert p.declenchement_homopolaire
    assert not p.declenchement_phase
    assert p.disjoncteur.ordre_ouverture


def test_depassement_trop_court_ne_declenche_pas():
    p = ProtectionDepart()
    faire_cycles(p, 3, courant=4000)  # 300 ms seulement
    faire_cycles(p, 10, courant=200)
    assert not p.verrouille


def test_fermeture_refusee_tant_que_non_acquitte():
    p = ProtectionDepart()
    faire_cycles(p, 5, courant=4000)            # déclenchement
    faire_cycles(p, 1, courant=0, dj_ferme=False)  # le DJ s'est ouvert

    faire_cycles(p, 1, courant=0, dj_ferme=False, acr_fermeture=True)
    assert not p.disjoncteur.ordre_fermeture


def test_acquittement_puis_fermeture():
    p = ProtectionDepart()
    faire_cycles(p, 5, courant=4000)
    faire_cycles(p, 1, courant=0, dj_ferme=False)

    faire_cycles(p, 1, courant=0, dj_ferme=False, acquittement=True)
    assert not p.verrouille

    faire_cycles(p, 1, courant=0, dj_ferme=False, acr_fermeture=True)
    assert p.disjoncteur.ordre_fermeture


def test_acquittement_ignore_si_defaut_toujours_present():
    p = ProtectionDepart()
    faire_cycles(p, 5, courant=4000)
    faire_cycles(p, 1, courant=4000, acquittement=True)
    assert p.declenchement_phase


def test_defaut_permanent_redeclenche_a_la_refermeture():
    p = ProtectionDepart()
    faire_cycles(p, 5, courant=4000)
    faire_cycles(p, 1, courant=0, dj_ferme=False, acquittement=True)
    faire_cycles(p, 1, courant=0, dj_ferme=False, acr_fermeture=True)

    # Le DJ se referme sur le défaut toujours présent
    faire_cycles(p, 5, courant=4000, dj_ferme=True)
    assert p.declenchement_phase
    assert p.disjoncteur.ordre_ouverture


def test_ouverture_et_fermeture_par_l_acr():
    p = ProtectionDepart()
    faire_cycles(p, 1, acr_ouverture=True)
    assert p.disjoncteur.ordre_ouverture
    faire_cycles(p, 1, courant=0, dj_ferme=False)
    assert not p.disjoncteur.ordre_ouverture

    faire_cycles(p, 1, courant=0, dj_ferme=False, acr_fermeture=True)
    assert p.disjoncteur.ordre_fermeture
    faire_cycles(p, 1, dj_ferme=True)
    assert not p.disjoncteur.ordre_fermeture
