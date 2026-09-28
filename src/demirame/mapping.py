"""Table des adresses Modbus : LE SEUL endroit où les adresses sont écrites.

Le serveur Modbus est dans l'automate (plc_main.py). La simulation et
Node-RED sont des clients qui viennent lire et écrire dans sa mémoire.

Adresses en base 0 (comme dans pymodbus et node-red-contrib-modbus).
Pour les disjoncteurs (DJ) et les départs, on ajoute l'indice :
    0 = départ 1, 1 = départ 2, 2 = départ 3, 3 = arrivée.
Exemple : ordre d'ouverture du DJ départ 2 -> CO_ORDRE_OUVERTURE + 1 = 11.

Le tableau complet est dans docs/mapping_modbus.md.
"""

PORT = 5020                 # port TCP du serveur (502 demande les droits root)
NB_DEPARTS = 3
NB_DJ = 4                   # 3 départs + 1 arrivée
ARRIVEE = 3                 # indice de l'arrivée dans les tableaux de DJ

# ---------------------------------------------------------------------------
# COILS (bits)
# ---------------------------------------------------------------------------
# Simulation -> automate
CO_POSITION_DJ = 0              # 0..3   position DJ (1 = fermé)
# Automate -> simulation
CO_ORDRE_OUVERTURE = 10         # 10..13 ordre d'ouverture DJ
CO_ORDRE_FERMETURE = 20         # 20..23 ordre de fermeture DJ
# IHM (ACR) -> automate : impulsions, remises à 0 par l'automate
CO_ACR_OUVERTURE = 30           # 30..33 demande d'ouverture DJ
CO_ACR_FERMETURE = 40           # 40..43 demande de fermeture DJ
CO_ACR_ACQUITTEMENT = 50        # 50     acquittement des alarmes
# Automate -> IHM : états et alarmes
CO_SEUIL_PHASE = 60             # 60..62 seuil phase dépassé (tempo en cours)
CO_SEUIL_HOMOPOLAIRE = 70       # 70..72 seuil homopolaire dépassé
CO_DECLENCHEMENT_PHASE = 80     # 80..82 alarme : déclenché sur défaut phase
CO_DECLENCHEMENT_HOMOPOLAIRE = 90  # 90..92 alarme : déclenché sur défaut terre
CO_VOYANT_ALARME = 100          # 100    au moins une alarme active

NB_COILS = 101                  # nombre de coils à lire pour tout avoir

# ---------------------------------------------------------------------------
# HOLDING REGISTERS (mots de 16 bits, entiers de 0 à 65535)
# ---------------------------------------------------------------------------
# Simulation -> automate : mesures
HR_COURANT_DEPART = 0           # 0..2   courant de phase départ (A)
HR_COURANT_ARRIVEE = 3          # 3      courant arrivée (A)
HR_COURANT_RESIDUEL = 4         # 4..6   courant résiduel Io départ (A)
HR_TENSION_BARRE = 7            # 7      tension barre en kV x 10 (200 = 20,0 kV)
NB_MESURES = 8
# Automate -> IHM
HR_COMPTEUR_VIE = 20            # 20     +1 à chaque cycle : l'automate tourne
# IHM (banc de test) -> simulation : défaut injecté (l'automate l'ignore)
HR_DEFAUT_INJECTE = 100         # 100..102 : 0 = aucun, 1 = phase, 2 = terre

NB_REGISTRES = 103

# Codes des défauts injectés
AUCUN_DEFAUT = 0
DEFAUT_PHASE = 1
DEFAUT_TERRE = 2

# Échelle de la tension
ECHELLE_TENSION = 10            # valeur Modbus = kV x 10
