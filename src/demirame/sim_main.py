"""Simulation du poste : client Modbus qui fait vivre le procédé.

Lancement :  uv run demirame-sim   (après avoir lancé l'automate)

Toutes les 10 ms :
1. lire dans l'automate les ordres des disjoncteurs et les défauts injectés ;
2. faire évoluer le poste (simulation.py) ;
3. écrire dans l'automate les positions des DJ et les mesures.
"""

import time

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from demirame.mapping import (
    BLOC_ARRIVEE,
    BLOCS_DEPARTS,
    CO_ORDRE_FERMETURE,
    CO_ORDRE_OUVERTURE,
    CO_POSITION_DJ,
    ECHELLE_TENSION,
    HR_DEFAUT_INJECTE,
    HR_I_L1,
    HR_TENSION_BARRE,
    NB_ADRESSES,
    NB_BLOCS,
    PORT,
    adresse,
)
from demirame.simulation import Poste, type_defaut

PAS_MS = 10


def main():
    client = ModbusTcpClient("127.0.0.1", port=PORT)
    poste = Poste()
    defauts_precedents = [0] * len(BLOCS_DEPARTS)
    print(f"Simulation démarrée, connexion à l'automate (port {PORT})...")

    precedent = time.monotonic()
    while True:
        debut = time.monotonic()
        dt_ms = round((debut - precedent) * 1000)
        precedent = debut
        try:
            if not client.connected:
                client.connect()

            # 1. Lire les ordres de l'automate et les défauts injectés
            co = client.read_coils(0, count=NB_ADRESSES).bits
            hr = client.read_holding_registers(0, count=NB_ADRESSES).registers
            ordres_ouverture = [co[adresse(b, CO_ORDRE_OUVERTURE)] for b in range(NB_BLOCS)]
            ordres_fermeture = [co[adresse(b, CO_ORDRE_FERMETURE)] for b in range(NB_BLOCS)]
            defauts = [hr[adresse(b, HR_DEFAUT_INJECTE)] for b in BLOCS_DEPARTS]

            for n, defaut in enumerate(defauts):
                if defaut != defauts_precedents[n]:
                    print(f"Départ {n + 1} : défaut {type_defaut(defaut)}")
            defauts_precedents = defauts

            # 2. Faire évoluer le poste
            poste.pas(ordres_ouverture, ordres_fermeture, defauts, dt_ms)

            # 3. Écrire les positions et les mesures de chaque cellule
            for bloc in range(NB_BLOCS):
                client.write_coil(adresse(bloc, CO_POSITION_DJ), poste.dj_ferme[bloc])
                client.write_registers(adresse(bloc, HR_I_L1),
                                       poste.courants[bloc] + [poste.courant_residuel[bloc]])
            client.write_register(adresse(BLOC_ARRIVEE, HR_TENSION_BARRE),
                                  round(poste.tension_kv * ECHELLE_TENSION))

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
