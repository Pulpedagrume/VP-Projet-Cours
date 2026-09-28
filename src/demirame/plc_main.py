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
    CO_SLP_EN_SERVICE,
    CO_VOYANT_ALARME,
    HR_ETAPE_RRL,
    HR_I_L1,
    HR_IO,
    HR_MOT_DE_VIE,
    HR_ORIGINE_DECLENCHEMENT,
    HR_REGLAGE_SEUIL_PHASE,
    HR_TEMPS_PROTECTION,
    NB_ADRESSES,
    NB_REGISTRES,
    PORT,
    adresse,
)
from demirame.protection import ProtectionArrivee, ProtectionDepart

CYCLE_MS = 20


def demarrer_serveur():
    """Crée la mémoire Modbus (80 coils + 160 registres) et lance le serveur."""
    memoire = SimDevice(
        id=0,  # 0 = répond quel que soit le numéro d'esclave demandé
        simdata=(
            [SimData(0, count=NB_ADRESSES, values=False, datatype=DataType.BITS)],     # coils
            [SimData(0, count=1, values=False, datatype=DataType.BITS)],               # discrete inputs (inutilisés)
            [SimData(0, count=NB_REGISTRES, values=0, datatype=DataType.REGISTERS)],   # holding registers (dont zone des phaseurs)
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


def reglages_arrivee(a):
    """Réglages de l'arrivée, dans l'ordre de la mémoire (décalages 5 à 9)."""
    return [a.phase.seuil, a.phase.tempo.duree_ms, a.terre.seuil, a.terre.tempo.duree_ms,
            a.tempo_slp.duree_ms]


def reglages_depart(p):
    """Réglages d'un départ, dans l'ordre de la mémoire (décalages 5 à 9)."""
    return [p.phase.seuil, p.phase.tempo.duree_ms, p.terre.seuil, p.terre.tempo.duree_ms,
            int(p.reenclencheur.en_service)]


def ecrire_reglages(client, arrivee, departs):
    """Écrit les réglages en vigueur dans la mémoire (visibles par l'IHM)."""
    client.write_registers(adresse(BLOC_ARRIVEE, HR_REGLAGE_SEUIL_PHASE), reglages_arrivee(arrivee))
    for bloc, p in zip(BLOCS_DEPARTS, departs):
        client.write_registers(adresse(bloc, HR_REGLAGE_SEUIL_PHASE), reglages_depart(p))


def ecrire_releve(client, bloc, r):
    """Relevé du dernier déclenchement (l'adresse 15, entre les deux, est au banc de test)."""
    client.write_registers(adresse(bloc, HR_TEMPS_PROTECTION),
                           [r.temps_protection, r.temps_ouverture_dj, r.temps_elimination,
                            r.phases_defaut, r.nb_declenchements])
    client.write_register(adresse(bloc, HR_ORIGINE_DECLENCHEMENT), r.origine)


def main():
    demarrer_serveur()
    time.sleep(0.5)  # laisse au serveur le temps de démarrer

    client = ModbusTcpClient("127.0.0.1", port=PORT)
    client.connect()

    arrivee = ProtectionArrivee()
    departs = [ProtectionDepart() for _ in BLOCS_DEPARTS]
    for p in departs:
        p.reenclencheur.en_service = True       # RRL en service par défaut
    ecrire_reglages(client, arrivee, departs)
    client.write_coil(adresse(BLOC_ARRIVEE, CO_SLP_EN_SERVICE), True)   # SLP en service par défaut
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

            def mesures(bloc):
                i = adresse(bloc, HR_I_L1)
                return hr[i:i + 3], hr[adresse(bloc, HR_IO)]

            def reglages_lus(bloc):
                r = adresse(bloc, HR_REGLAGE_SEUIL_PHASE)
                return hr[r:r + 5]      # 4 réglages + RRL (départ) ou tempo SLP (arrivée)

            # ---------- 2. TRAITEMENT ----------
            # Départs : réglages, protection, réenclencheur
            for bloc, p in zip(BLOCS_DEPARTS, departs):
                lus = reglages_lus(bloc)
                p.regler(*lus[:4])
                p.reenclencheur.en_service = lus[4] != 0
                courants, io = mesures(bloc)
                p.cycle(courants, io,
                        dj_ferme=co[adresse(bloc, CO_POSITION_DJ)],
                        acr_ouverture=co[adresse(bloc, CO_ACR_OUVERTURE)],
                        acr_fermeture=co[adresse(bloc, CO_ACR_FERMETURE)],
                        acquittement=acquittement,
                        dt_ms=dt_ms)

            # Arrivée : un départ qui voit le défaut envoie l'« attente logique »
            attente_logique = any(p.demarrage_phase or p.demarrage_terre for p in departs)
            arrivee.regler(*reglages_lus(BLOC_ARRIVEE))
            arrivee.slp_en_service = co[adresse(BLOC_ARRIVEE, CO_SLP_EN_SERVICE)]
            courants, io = mesures(BLOC_ARRIVEE)
            arrivee.cycle(courants, io,
                          dj_ferme=co[adresse(BLOC_ARRIVEE, CO_POSITION_DJ)],
                          attente_logique=attente_logique,
                          acr_ouverture=co[adresse(BLOC_ARRIVEE, CO_ACR_OUVERTURE)],
                          acr_fermeture=co[adresse(BLOC_ARRIVEE, CO_ACR_FERMETURE)],
                          acquittement=acquittement,
                          dt_ms=dt_ms)

            # ---------- 3. ÉCRITURE DES SORTIES ----------
            # Arrivée
            client.write_coils(adresse(BLOC_ARRIVEE, CO_ORDRE_OUVERTURE),
                               [arrivee.disjoncteur.ordre_ouverture, arrivee.disjoncteur.ordre_fermeture])
            client.write_coils(adresse(BLOC_ARRIVEE, CO_DEMARRAGE_PHASE),
                               [arrivee.demarrage_phase, arrivee.demarrage_terre,
                                arrivee.declenchement_phase, arrivee.declenchement_terre,
                                arrivee.declenchement_slp])
            ecrire_releve(client, BLOC_ARRIVEE, arrivee.releve)

            # Départs
            for bloc, p in zip(BLOCS_DEPARTS, departs):
                client.write_coils(adresse(bloc, CO_ORDRE_OUVERTURE),
                                   [p.disjoncteur.ordre_ouverture, p.disjoncteur.ordre_fermeture])
                client.write_coils(adresse(bloc, CO_DEMARRAGE_PHASE),
                                   [p.demarrage_phase, p.demarrage_terre,
                                    p.declenchement_phase, p.declenchement_terre])
                ecrire_releve(client, bloc, p.releve)
                client.write_registers(adresse(bloc, HR_ETAPE_RRL),
                                       [p.reenclencheur.etape, p.reenclencheur.resultat])

            client.write_coil(adresse(BLOC_ARRIVEE, CO_VOYANT_ALARME),
                              arrivee.verrouille or any(p.verrouille for p in departs))

            # Réglages refusés (hors plage) : on réécrit les valeurs appliquées
            refuses = reglages_lus(BLOC_ARRIVEE) != reglages_arrivee(arrivee) or any(
                reglages_lus(b) != reglages_depart(p) for b, p in zip(BLOCS_DEPARTS, departs))
            if refuses:
                ecrire_reglages(client, arrivee, departs)

            # Mot de vie et durée de cycle (décalages 18 et 19 du bloc 0)
            mot_de_vie = (mot_de_vie + 1) % 65536
            client.write_registers(adresse(BLOC_ARRIVEE, HR_MOT_DE_VIE), [mot_de_vie, dt_ms])

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
