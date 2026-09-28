"""Automate virtuel : serveur Modbus TCP + cycle de scrutation.

Lancement :  uv run demirame-plc

Fonctionnement :
1. On démarre le serveur Modbus (la « mémoire » de l'automate) dans un
   thread. La simulation et Node-RED viennent y lire et écrire.
2. Le programme de l'automate accède à cette mémoire avec un client
   Modbus, comme les autres. Il n'y a donc qu'une seule façon de lire et
   d'écrire dans tout le projet : read_coils, write_coils, etc.
3. Toutes les 20 ms : LIRE les entrées -> TRAITER (protection.py)
   -> ÉCRIRE les sorties. C'est le cycle d'un automate réel.
   La durée réelle de chaque cycle est mesurée et utilisée par les
   temporisations : le temps compté est donc le vrai temps écoulé.
"""

import threading
import time

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.server import StartTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

from demirame.mapping import (
    BLOC_ARRIVEE,
    BLOCS_DEPARTS,
    CO_ACR_ACQUITTEMENT,
    CO_ACR_FERMETURE,
    CO_ACR_OUVERTURE,
    CO_DEMARRAGE_PHASE,
    CO_ORDRE_OUVERTURE,
    CO_POSITION_DJ,
    CO_VOYANT_ALARME,
    HR_DUREE_CYCLE,
    HR_I_L1,
    HR_IO,
    HR_MOT_DE_VIE,
    HR_ORIGINE_DECLENCHEMENT,
    HR_REGLAGE_SEUIL_PHASE,
    HR_TEMPS_PROTECTION,
    NB_ADRESSES,
    PORT,
    adresse,
)
from demirame.protection import CommandeDisjoncteur, ProtectionDepart

CYCLE_MS = 20


def demarrer_serveur():
    """Crée la mémoire Modbus (80 coils + 80 registres) et lance le serveur."""
    memoire = SimDevice(
        id=0,  # 0 = répond quel que soit le numéro d'esclave demandé
        simdata=(
            [SimData(0, count=NB_ADRESSES, values=False, datatype=DataType.BITS)],     # coils
            [SimData(0, count=1, values=False, datatype=DataType.BITS)],               # discrete inputs (inutilisés)
            [SimData(0, count=NB_ADRESSES, values=0, datatype=DataType.REGISTERS)],    # holding registers
            [SimData(0, count=1, values=0, datatype=DataType.REGISTERS)],              # input registers (inutilisés)
        ),
    )
    serveur = threading.Thread(
        target=StartTcpServer,
        args=(memoire,),
        kwargs={"address": ("0.0.0.0", PORT)},
        daemon=True,  # le thread s'arrête avec le programme
    )
    serveur.start()


def ecrire_reglages(client, protections):
    """Écrit les réglages en vigueur dans la mémoire (visibles par l'IHM)."""
    for bloc, p in zip(BLOCS_DEPARTS, protections):
        client.write_registers(
            adresse(bloc, HR_REGLAGE_SEUIL_PHASE),
            [p.seuil_phase, p.tempo_phase.duree_ms, p.seuil_terre, p.tempo_terre.duree_ms],
        )


def main():
    demarrer_serveur()
    time.sleep(0.5)  # laisse au serveur le temps de démarrer

    client = ModbusTcpClient("127.0.0.1", port=PORT)
    client.connect()

    protections = [ProtectionDepart() for _ in BLOCS_DEPARTS]
    arrivee = CommandeDisjoncteur()
    ecrire_reglages(client, protections)
    print(f"Automate démarré : serveur Modbus TCP sur le port {PORT}, cycle {CYCLE_MS} ms")

    mot_de_vie = 0
    precedent = time.monotonic()

    while True:
        debut = time.monotonic()
        dt_ms = round((debut - precedent) * 1000)  # durée réelle depuis le cycle précédent
        precedent = debut
        try:
            # ---------- 1. LECTURE DES ENTRÉES ----------
            co = client.read_coils(0, count=NB_ADRESSES).bits
            hr = client.read_holding_registers(0, count=NB_ADRESSES).registers
            acquittement = co[adresse(BLOC_ARRIVEE, CO_ACR_ACQUITTEMENT)]

            # ---------- 2. TRAITEMENT ----------
            for bloc, p in zip(BLOCS_DEPARTS, protections):
                reglages = hr[adresse(bloc, HR_REGLAGE_SEUIL_PHASE):adresse(bloc, HR_REGLAGE_SEUIL_PHASE) + 4]
                p.regler(*reglages)
                p.cycle(
                    courants=hr[adresse(bloc, HR_I_L1):adresse(bloc, HR_I_L1) + 3],
                    courant_residuel=hr[adresse(bloc, HR_IO)],
                    dj_ferme=co[adresse(bloc, CO_POSITION_DJ)],
                    acr_ouverture=co[adresse(bloc, CO_ACR_OUVERTURE)],
                    acr_fermeture=co[adresse(bloc, CO_ACR_FERMETURE)],
                    acquittement=acquittement,
                    dt_ms=dt_ms,
                )
                # Réglage refusé (hors plage) : on réécrit la valeur appliquée
                appliques = [p.seuil_phase, p.tempo_phase.duree_ms, p.seuil_terre, p.tempo_terre.duree_ms]
                if appliques != reglages:
                    client.write_registers(adresse(bloc, HR_REGLAGE_SEUIL_PHASE), appliques)

            arrivee.cycle(
                dj_ferme=co[adresse(BLOC_ARRIVEE, CO_POSITION_DJ)],
                demande_ouverture=co[adresse(BLOC_ARRIVEE, CO_ACR_OUVERTURE)],
                demande_fermeture=co[adresse(BLOC_ARRIVEE, CO_ACR_FERMETURE)],
            )

            # ---------- 3. ÉCRITURE DES SORTIES ----------
            client.write_coils(adresse(BLOC_ARRIVEE, CO_ORDRE_OUVERTURE),
                               [arrivee.ordre_ouverture, arrivee.ordre_fermeture])
            for bloc, p in zip(BLOCS_DEPARTS, protections):
                client.write_coils(adresse(bloc, CO_ORDRE_OUVERTURE),
                                   [p.disjoncteur.ordre_ouverture, p.disjoncteur.ordre_fermeture])
                client.write_coils(adresse(bloc, CO_DEMARRAGE_PHASE),
                                   [p.demarrage_phase, p.demarrage_terre,
                                    p.declenchement_phase, p.declenchement_terre])
                r = p.releve
                client.write_registers(adresse(bloc, HR_TEMPS_PROTECTION),
                                       [r.temps_protection, r.temps_ouverture_dj, r.temps_elimination,
                                        r.phases_defaut, r.nb_declenchements])
                # (l'adresse 15, entre les deux, appartient au banc de test : on n'y écrit pas)
                client.write_register(adresse(bloc, HR_ORIGINE_DECLENCHEMENT), r.origine)
            client.write_coil(adresse(BLOC_ARRIVEE, CO_VOYANT_ALARME),
                              any(p.verrouille for p in protections))

            mot_de_vie = (mot_de_vie + 1) % 65536
            client.write_register(adresse(BLOC_ARRIVEE, HR_MOT_DE_VIE), mot_de_vie)
            client.write_register(adresse(BLOC_ARRIVEE, HR_DUREE_CYCLE), dt_ms)

            # Les commandes ACR sont des impulsions : on les remet à 0
            # une fois prises en compte.
            for bloc in [BLOC_ARRIVEE] + BLOCS_DEPARTS:
                for decalage in (CO_ACR_OUVERTURE, CO_ACR_FERMETURE):
                    if co[adresse(bloc, decalage)]:
                        client.write_coil(adresse(bloc, decalage), False)
            if acquittement:
                client.write_coil(adresse(BLOC_ARRIVEE, CO_ACR_ACQUITTEMENT), False)

        except ModbusException as erreur:
            print(f"Erreur Modbus : {erreur}")
            client.connect()

        # Attendre la fin du cycle
        duree = time.monotonic() - debut
        time.sleep(max(0.0, CYCLE_MS / 1000 - duree))


if __name__ == "__main__":
    main()
