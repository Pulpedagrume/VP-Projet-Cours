"""Automate virtuel : serveur Modbus TCP + cycle de scrutation.

Lancement :  uv run demirame-plc

Fonctionnement :
1. On démarre le serveur Modbus (la « mémoire » de l'automate) dans un
   thread. La simulation et Node-RED viennent y lire et écrire.
2. Le programme de l'automate accède à cette mémoire avec un client
   Modbus, comme les autres. Il n'y a donc qu'une seule façon de lire et
   d'écrire dans tout le projet : read_coils, write_coils, etc.
3. Toutes les 100 ms : LIRE les entrées -> TRAITER (protection.py)
   -> ÉCRIRE les sorties. C'est le cycle d'un automate réel.
"""

import threading
import time

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.server import StartTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

from demirame.mapping import (
    ARRIVEE,
    CO_ACR_ACQUITTEMENT,
    CO_ACR_FERMETURE,
    CO_ACR_OUVERTURE,
    CO_DECLENCHEMENT_HOMOPOLAIRE,
    CO_DECLENCHEMENT_PHASE,
    CO_ORDRE_FERMETURE,
    CO_ORDRE_OUVERTURE,
    CO_POSITION_DJ,
    CO_SEUIL_HOMOPOLAIRE,
    CO_SEUIL_PHASE,
    CO_VOYANT_ALARME,
    HR_COMPTEUR_VIE,
    HR_COURANT_DEPART,
    HR_COURANT_RESIDUEL,
    NB_COILS,
    NB_DEPARTS,
    NB_MESURES,
    NB_REGISTRES,
    PORT,
)
from demirame.protection import CommandeDisjoncteur, ProtectionDepart

CYCLE_MS = 100


def demarrer_serveur():
    """Crée la mémoire Modbus et lance le serveur dans un thread."""
    memoire = SimDevice(
        id=0,  # 0 = répond quel que soit le numéro d'esclave demandé
        simdata=(
            [SimData(0, count=NB_COILS, values=False, datatype=DataType.BITS)],  # coils
            [SimData(0, count=1, values=False, datatype=DataType.BITS)],         # discrete inputs (inutilisés)
            [SimData(0, count=NB_REGISTRES, values=0, datatype=DataType.REGISTERS)],  # holding registers
            [SimData(0, count=1, values=0, datatype=DataType.REGISTERS)],        # input registers (inutilisés)
        ),
    )
    serveur = threading.Thread(
        target=StartTcpServer,
        args=(memoire,),
        kwargs={"address": ("0.0.0.0", PORT)},
        daemon=True,  # le thread s'arrête avec le programme
    )
    serveur.start()


def main():
    demarrer_serveur()
    time.sleep(0.5)  # laisse au serveur le temps de démarrer

    client = ModbusTcpClient("127.0.0.1", port=PORT)
    client.connect()
    print(f"Automate démarré : serveur Modbus TCP sur le port {PORT}")

    protections = [ProtectionDepart() for _ in range(NB_DEPARTS)]
    arrivee = CommandeDisjoncteur()
    compteur_vie = 0

    while True:
        debut = time.monotonic()
        try:
            # ---------- 1. LECTURE DES ENTRÉES ----------
            coils = client.read_coils(0, count=NB_COILS).bits
            mesures = client.read_holding_registers(0, count=NB_MESURES).registers
            acquittement = coils[CO_ACR_ACQUITTEMENT]

            # ---------- 2. TRAITEMENT ----------
            for n, protection in enumerate(protections):
                protection.cycle(
                    courant=mesures[HR_COURANT_DEPART + n],
                    courant_residuel=mesures[HR_COURANT_RESIDUEL + n],
                    dj_ferme=coils[CO_POSITION_DJ + n],
                    acr_ouverture=coils[CO_ACR_OUVERTURE + n],
                    acr_fermeture=coils[CO_ACR_FERMETURE + n],
                    acquittement=acquittement,
                    dt_ms=CYCLE_MS,
                )
            arrivee.cycle(
                dj_ferme=coils[CO_POSITION_DJ + ARRIVEE],
                demande_ouverture=coils[CO_ACR_OUVERTURE + ARRIVEE],
                demande_fermeture=coils[CO_ACR_FERMETURE + ARRIVEE],
            )

            # ---------- 3. ÉCRITURE DES SORTIES ----------
            disjoncteurs = [p.disjoncteur for p in protections] + [arrivee]
            client.write_coils(CO_ORDRE_OUVERTURE, [dj.ordre_ouverture for dj in disjoncteurs])
            client.write_coils(CO_ORDRE_FERMETURE, [dj.ordre_fermeture for dj in disjoncteurs])
            client.write_coils(CO_SEUIL_PHASE, [p.seuil_phase_depasse for p in protections])
            client.write_coils(CO_SEUIL_HOMOPOLAIRE, [p.seuil_homopolaire_depasse for p in protections])
            client.write_coils(CO_DECLENCHEMENT_PHASE, [p.declenchement_phase for p in protections])
            client.write_coils(CO_DECLENCHEMENT_HOMOPOLAIRE, [p.declenchement_homopolaire for p in protections])
            client.write_coil(CO_VOYANT_ALARME, any(p.verrouille for p in protections))

            compteur_vie = (compteur_vie + 1) % 65536
            client.write_register(HR_COMPTEUR_VIE, compteur_vie)

            # Les commandes ACR sont des impulsions : on les remet à 0
            # une fois prises en compte.
            for adresse in range(CO_ACR_OUVERTURE, CO_ACR_ACQUITTEMENT + 1):
                if coils[adresse]:
                    client.write_coil(adresse, False)

        except ModbusException as erreur:
            print(f"Erreur Modbus : {erreur}")
            client.connect()

        # Attendre la fin du cycle de 100 ms
        duree = time.monotonic() - debut
        time.sleep(max(0.0, CYCLE_MS / 1000 - duree))


if __name__ == "__main__":
    main()
