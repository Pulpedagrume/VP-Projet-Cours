"""Simulation du poste : client Modbus qui fait vivre le procédé.

Lancement :  uv run demirame-sim   (après avoir lancé l'automate)

Toutes les 10 ms :
1. lire dans l'automate les ordres des disjoncteurs, les défauts demandés
   par le banc de test et l'état du mode aléatoire ;
2. faire évoluer le poste (simulation.py, aleatoire.py) ;
3. écrire dans l'automate les positions des DJ, les mesures (modules),
   les phaseurs (angles) et l'état des défauts (qui peuvent disparaître
   seuls : fugitif, semi-permanent, réparation).
"""

import time

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from demirame import aleatoire
from demirame.mapping import (
    BLOC_ARRIVEE,
    CO_MODE_ALEATOIRE,
    CO_ORDRE_FERMETURE,
    CO_ORDRE_OUVERTURE,
    CO_POSITION_DJ,
    ECHELLE_TENSION,
    ECHELLE_TENSION_SIMPLE,
    HR_DEFAUT_INJECTE,
    HR_I_L1,
    HR_NATURE_DEFAUT,
    HR_TENSION_BARRE,
    NB_ADRESSES,
    NB_BLOCS,
    PH_ANGLE_I_L1,
    PH_V1,
    PORT,
    adresse,
    adresse_phaseur,
)
from demirame.simulation import Poste, angle_deg, type_defaut

PAS_MS = 10


def angle_entier(z):
    """Angle en degrés entiers (0 à 359) ; 0 si le phaseur est quasi nul."""
    return round(angle_deg(z)) % 360 if abs(z) > 0.5 else 0


def nom_bloc(bloc):
    return "Jeu de barres" if bloc == BLOC_ARRIVEE else f"Départ {bloc}"


def ecrire_mesures(client, poste):
    """Écrit positions, modules et angles de chaque cellule dans l'automate."""
    for bloc in range(NB_BLOCS):
        courants = poste.courants[bloc]
        io = poste.courant_residuel(bloc)
        client.write_coil(adresse(bloc, CO_POSITION_DJ), poste.dj_ferme[bloc])
        # Zone principale : modules (ce que lisent les protections)
        client.write_registers(adresse(bloc, HR_I_L1),
                               [round(abs(i)) for i in courants] + [round(abs(io))])
        # Zone des phaseurs : angles (pour les diagrammes de Fresnel)
        client.write_registers(adresse_phaseur(bloc, PH_ANGLE_I_L1),
                               [angle_entier(i) for i in courants] + [angle_entier(io)])

    client.write_register(adresse(BLOC_ARRIVEE, HR_TENSION_BARRE),
                          round(poste.tension_kv * ECHELLE_TENSION))
    tensions = poste.tensions + [poste.tension_residuelle]
    client.write_registers(
        adresse_phaseur(BLOC_ARRIVEE, PH_V1),
        [round(abs(v) * ECHELLE_TENSION_SIMPLE) for v in tensions]
        + [round(angle_deg(v)) % 360 if abs(v) > 0.05 else 0 for v in tensions],
    )


def main():
    client = ModbusTcpClient("127.0.0.1", port=PORT)
    poste = Poste()
    mode_aleatoire = aleatoire.ModeAleatoire()
    aleatoire_en_marche = False
    # Derniers bits de défaut connus dans la mémoire de l'automate (un par bloc).
    # Seul un changement des BITS déclenche une action : la nature est lue en
    # même temps. (Le banc écrit d'abord la nature, puis les bits.)
    connus = [0] * NB_BLOCS
    print(f"Simulation démarrée, connexion à l'automate (port {PORT})...")

    precedent = time.monotonic()
    while True:
        debut = time.monotonic()
        dt_ms = round((debut - precedent) * 1000)
        precedent = debut
        try:
            if not client.connected:
                client.connect()

            # 1. Lire les ordres, les défauts demandés et le mode aléatoire
            co = client.read_coils(0, count=NB_ADRESSES).bits
            hr = client.read_holding_registers(0, count=NB_ADRESSES).registers
            ordres_ouverture = [co[adresse(b, CO_ORDRE_OUVERTURE)] for b in range(NB_BLOCS)]
            ordres_fermeture = [co[adresse(b, CO_ORDRE_FERMETURE)] for b in range(NB_BLOCS)]

            # Le banc de test a-t-il changé un défaut ? -> on l'applique
            for bloc in range(NB_BLOCS):
                bits = hr[adresse(bloc, HR_DEFAUT_INJECTE)]
                if bits != connus[bloc]:
                    poste.injecter(bloc, bits, hr[adresse(bloc, HR_NATURE_DEFAUT)])
                    connus[bloc] = bits
                    print(f"{nom_bloc(bloc)} : banc de test, défaut {type_defaut(bits)}")

            if co[adresse(BLOC_ARRIVEE, CO_MODE_ALEATOIRE)] != aleatoire_en_marche:
                aleatoire_en_marche = not aleatoire_en_marche
                print("Mode aléatoire", "EN MARCHE" if aleatoire_en_marche else "ARRÊTÉ")
                if not aleatoire_en_marche:
                    aleatoire.arreter(poste)

            # 2. Faire évoluer le poste
            if aleatoire_en_marche:
                evenement = mode_aleatoire.pas(poste, dt_ms)
                if evenement:
                    print("Mode aléatoire :", evenement)
            poste.pas(ordres_ouverture, ordres_fermeture, dt_ms)

            # 3. Écrire positions, mesures, phaseurs
            ecrire_mesures(client, poste)

            # ... et les défauts qui ont changé tout seuls (extinction, mode aléatoire)
            for bloc in range(NB_BLOCS):
                if poste.defauts[bloc] != connus[bloc]:
                    client.write_register(adresse(bloc, HR_NATURE_DEFAUT), poste.natures[bloc])
                    client.write_register(adresse(bloc, HR_DEFAUT_INJECTE), poste.defauts[bloc])
                    if not poste.defauts[bloc]:
                        print(f"{nom_bloc(bloc)} : défaut disparu")
                    connus[bloc] = poste.defauts[bloc]

        except ModbusException:
            print("Automate injoignable, nouvel essai dans 1 s...")
            client.close()
            time.sleep(1)
            precedent = time.monotonic()
            continue

        duree = time.monotonic() - debut
        time.sleep(max(0.0, PAS_MS / 1000 - duree))


if __name__ == "__main__":
    main()
