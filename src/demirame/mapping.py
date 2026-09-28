"""Table des adresses Modbus : LE SEUL endroit où les adresses sont écrites.

Le serveur Modbus est dans l'automate (plc_main.py). La simulation et
Node-RED sont des clients qui viennent lire et écrire dans sa mémoire.

ORGANISATION EN BLOCS DE 20 ADRESSES
------------------------------------
Chaque cellule du poste a son bloc, dans les coils ET dans les registres :

    bloc 0 : arrivée + informations générales   adresses  0 à 19
    bloc 1 : départ 1                             adresses 20 à 39
    bloc 2 : départ 2                             adresses 40 à 59
    bloc 3 : départ 3                             adresses 60 à 79

Adresse = 20 x numéro de bloc + décalage.
Exemple : courant L2 du départ 3 = 20 x 3 + HR_I_L2 = 61.

Les décalages des disjoncteurs (position, ordres, commandes ACR) sont les
mêmes dans tous les blocs, arrivée comprise.

Adresses en base 0. Le tableau complet est dans docs/mapping_modbus.md.
"""

PORT = 5020                 # port TCP du serveur (502 demande les droits root)
TAILLE_BLOC = 20
NB_DEPARTS = 3
NB_BLOCS = 4                # arrivée + 3 départs
BLOC_ARRIVEE = 0
BLOCS_DEPARTS = [1, 2, 3]
NB_ADRESSES = TAILLE_BLOC * NB_BLOCS   # 80 coils et 80 registres


def adresse(bloc, decalage):
    """Adresse Modbus d'une variable : bloc 0 = arrivée, 1 à 3 = départs."""
    return TAILLE_BLOC * bloc + decalage


# ---------------------------------------------------------------------------
# COILS (bits) : décalages dans chaque bloc
# ---------------------------------------------------------------------------
# Disjoncteur (tous les blocs)
CO_POSITION_DJ = 0          # 1 = fermé                         simulation -> automate
CO_ORDRE_OUVERTURE = 1      # ordre à la bobine d'ouverture      automate -> simulation
CO_ORDRE_FERMETURE = 2      # ordre à la bobine de fermeture     automate -> simulation
CO_ACR_OUVERTURE = 3        # télécommande ACR (impulsion)       IHM -> automate
CO_ACR_FERMETURE = 4        # télécommande ACR (impulsion)       IHM -> automate
# Général (bloc 0 seulement)
CO_ACR_ACQUITTEMENT = 5     # acquittement (impulsion)           IHM -> automate
CO_VOYANT_ALARME = 6        # au moins une alarme mémorisée      automate -> IHM
# Protections (blocs départs)
CO_DEMARRAGE_PHASE = 10     # I > seuil : temporisation en cours automate -> IHM
CO_DEMARRAGE_TERRE = 11     # Io > seuil : temporisation en cours
CO_DECLENCHEMENT_PHASE = 12  # alarme mémorisée : déclenché par I>
CO_DECLENCHEMENT_TERRE = 13  # alarme mémorisée : déclenché par Io>

# ---------------------------------------------------------------------------
# HOLDING REGISTERS (mots de 16 bits) : décalages dans chaque bloc
# ---------------------------------------------------------------------------
# Mesures (tous les blocs)                                        simulation -> automate
HR_I_L1 = 0                 # courant phase L1 (A)
HR_I_L2 = 1                 # courant phase L2 (A)
HR_I_L3 = 2                 # courant phase L3 (A)
HR_IO = 3                   # courant résiduel Io (A)
# Général (bloc 0 seulement)
HR_TENSION_BARRE = 4        # kV x 10 (200 = 20,0 kV)            simulation -> automate
HR_MOT_DE_VIE = 10          # +1 à chaque cycle                  automate -> IHM
HR_DUREE_CYCLE = 11         # durée du dernier cycle (ms)        automate -> IHM
# Réglages des protections (blocs départs)                        IHM -> automate
HR_REGLAGE_SEUIL_PHASE = 5  # seuil I> (A)
HR_REGLAGE_TEMPO_PHASE = 6  # temporisation I> (ms)
HR_REGLAGE_SEUIL_TERRE = 7  # seuil Io> (A)
HR_REGLAGE_TEMPO_TERRE = 8  # temporisation Io> (ms)
# Relevé du dernier déclenchement (blocs départs)                 automate -> IHM
HR_TEMPS_PROTECTION = 10    # apparition du défaut -> ordre de déclenchement (ms)
HR_TEMPS_OUVERTURE_DJ = 11  # ordre de déclenchement -> DJ ouvert (ms)
HR_TEMPS_ELIMINATION = 12   # apparition du défaut -> DJ ouvert (ms)
HR_PHASES_DEFAUT = 13       # phases vues en défaut (bits, voir ci-dessous)
HR_NB_DECLENCHEMENTS = 14   # compteur de déclenchements
HR_ORIGINE_DECLENCHEMENT = 16  # protection qui a déclenché : 1 = I>, 2 = Io>, 3 = les deux
# Banc de test (blocs départs)                                    IHM -> simulation
HR_DEFAUT_INJECTE = 15      # défaut appliqué (bits, voir ci-dessous) - l'automate ne le lit pas

# ---------------------------------------------------------------------------
# Codage des phases en défaut (HR_PHASES_DEFAUT et HR_DEFAUT_INJECTE)
# ---------------------------------------------------------------------------
BIT_L1 = 1
BIT_L2 = 2
BIT_L3 = 4
BIT_TERRE = 8
BITS_PHASES = [BIT_L1, BIT_L2, BIT_L3]

# Codage de HR_ORIGINE_DECLENCHEMENT
ORIGINE_PHASE = 1           # I>  (ANSI 51)
ORIGINE_TERRE = 2           # Io> (ANSI 51N)

ECHELLE_TENSION = 10        # valeur Modbus = kV x 10

# ---------------------------------------------------------------------------
# ZONE DES PHASEURS (holding registers 80 à 159) : pour les diagrammes de Fresnel
# ---------------------------------------------------------------------------
# Même découpage en blocs de 20, décalé de 80 : adresse = 80 + 20 x bloc + décalage.
# Écrite par la simulation, lue par l'IHM. L'automate n'en a pas besoin :
# ses protections travaillent sur les modules (valeurs efficaces).
ZONE_PHASEURS = 80
NB_REGISTRES = ZONE_PHASEURS + NB_ADRESSES   # 160 holding registers au total

PH_ANGLE_I_L1 = 0           # angle du courant L1 (degrés, 0 à 359) - tous les blocs
PH_ANGLE_I_L2 = 1
PH_ANGLE_I_L3 = 2
PH_ANGLE_IO = 3             # angle du courant résiduel Io
# Bloc 0 : tensions simples du jeu de barres
PH_V1 = 4                   # module V1 en kV x 100 (1155 = 11,55 kV)
PH_V2 = 5
PH_V3 = 6
PH_V0 = 7                   # tension résiduelle V0 = (V1 + V2 + V3) / 3
PH_ANGLE_V1 = 8             # angles en degrés
PH_ANGLE_V2 = 9
PH_ANGLE_V3 = 10
PH_ANGLE_V0 = 11
ECHELLE_TENSION_SIMPLE = 100   # valeur Modbus = kV x 100


def adresse_phaseur(bloc, decalage):
    """Adresse d'une donnée de la zone des phaseurs."""
    return ZONE_PHASEURS + adresse(bloc, decalage)
