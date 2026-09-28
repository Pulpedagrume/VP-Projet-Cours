"""Simulation du poste : client Modbus qui fait vivre le procédé.

Lancement :  uv run demirame-sim   (après avoir lancé l'automate)

Toutes les 100 ms :
1. lire dans l'automate les ordres des disjoncteurs et les défauts injectés ;
2. faire évoluer le poste (simulation.py) ;
3. écrire dans l'automate les positions des DJ et les mesures.
"""

import time

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from demirame.mapping import (
    CO_ORDRE_FERMETURE,
    CO_ORDRE_OUVERTURE,
    CO_POSITION_DJ,
    ECHELLE_TENSION,
    HR_COURANT_ARRIVEE,
    HR_COURANT_DEPART,
    HR_COURANT_RESIDUEL,
    HR_DEFAUT_INJECTE,
    HR_TENSION_BARRE,
    NB_COILS,
    NB_DEPARTS,
    NB_DJ,
    PORT,
)
from demirame.simulation import Poste

PAS_MS = 100


def main():
    client = ModbusTcpClient("127.0.0.1", port=PORT)
    poste = Poste()
    print(f"Simulation démarrée, connexion à l'automate (port {PORT})...")

    while True:
        debut = time.monotonic()
        try:
            if not client.connected:
                client.connect()

            # 1. Lire les ordres de l'automate et les défauts injectés
            coils = client.read_coils(0, count=NB_COILS).bits
            ordres_ouverture = coils[CO_ORDRE_OUVERTURE:CO_ORDRE_OUVERTURE + NB_DJ]
            ordres_fermeture = coils[CO_ORDRE_FERMETURE:CO_ORDRE_FERMETURE + NB_DJ]
            defauts = client.read_holding_registers(HR_DEFAUT_INJECTE, count=NB_DEPARTS).registers

            # 2. Faire évoluer le poste
            poste.pas(ordres_ouverture, ordres_fermeture, defauts, PAS_MS)

            # 3. Écrire les positions et les mesures
            client.write_coils(CO_POSITION_DJ, poste.dj_ferme)
            client.write_registers(HR_COURANT_DEPART, poste.courant_depart)
            client.write_register(HR_COURANT_ARRIVEE, poste.courant_arrivee)
            client.write_registers(HR_COURANT_RESIDUEL, poste.courant_residuel)
            client.write_register(HR_TENSION_BARRE, round(poste.tension_kv * ECHELLE_TENSION))

        except ModbusException:
            print("Automate injoignable, nouvel essai dans 1 s...")
            client.close()
            time.sleep(1)
            continue

        duree = time.monotonic() - debut
        time.sleep(max(0.0, PAS_MS / 1000 - duree))


if __name__ == "__main__":
    main()
