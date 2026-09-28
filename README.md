# Demi-rame HTA virtuelle

Projet GEII : contrôle-commande virtuel d'une **demi-rame HTA de poste
source** (1 arrivée + 3 départs).

- **Simulation** du procédé en Python (courants, défauts, disjoncteurs)
- **Automate virtuel** en Python (protections, commande des disjoncteurs)
- **Modbus TCP** entre les composants (`pymodbus`)
- **IHM ACR** avec Node-RED (Dashboard 2.0)

Documentation :
- [`docs/specification.md`](docs/specification.md) : ce que fait le système
- [`docs/mapping_modbus.md`](docs/mapping_modbus.md) : table des adresses Modbus

## Architecture

```
 SIMULATION (client)  --- mesures, positions DJ --->  AUTOMATE          <--- commandes ACR ---  NODE-RED (client)
 sim_main.py          <--- ordres DJ -------------    serveur Modbus    --- états, alarmes -->  IHM :1880/dashboard
                                                      port 5020
                                                      plc_main.py
```

## Installation

Prérequis : [uv](https://docs.astral.sh/uv/) (version récente) et Node.js 22.9 ou plus.

```bash
git clone https://github.com/Pulpedagrume/VP-Projet-Cours.git
cd VP-Projet-Cours
uv sync                       # Python : crée .venv et installe pymodbus
cd node-red && npm install    # Node-RED + Dashboard + nœuds Modbus
```

Remarque : `node-red/package.json` contient une rubrique `overrides`. Le paquet
`node-red-contrib-modbus` télécharge normalement une de ses dépendances hors
du registre npm (dl.cloudsmith.io), ce qui est souvent bloqué par les
réseaux d'école ou d'entreprise. On la remplace par le paquet d'origine
`modbus-serial`, publié sur npm.

## Lancement (3 terminaux)

```bash
# Terminal 1 : l'automate (à lancer en premier, c'est le serveur)
uv run demirame-plc

# Terminal 2 : la simulation du poste
uv run demirame-sim

# Terminal 3 : l'IHM
cd node-red
npm start
```

Puis ouvrir **http://localhost:1880/dashboard** :
- page **Poste de conduite (ACR)** : synoptique, mesures, commandes, courbes, journal ;
- page **Banc de test** : injection d'un défaut phase ou terre sur un départ.

L'éditeur Node-RED est sur http://localhost:1880.

## Démonstration rapide

1. Banc de test → Départ 2 → **Défaut phase** : après 0,5 s le DJ du départ 2
   s'ouvre (rouge), alarme « Défaut phase ».
2. Poste → **Fermer** le départ 2 : refusé, l'alarme n'est pas acquittée.
3. Banc de test → Départ 2 → **Aucun**, puis **Acquitter**, puis **Fermer** :
   le départ revient en service.
4. Même chose avec **Défaut terre** : seul Io monte, déclenchement après 1 s.

## Tests

```bash
uv run pytest
```

## Organisation

```
src/demirame/
    mapping.py      table des adresses Modbus (unique)
    protection.py   programme de l'automate (seuils, tempos, verrouillage)
    plc_main.py     automate : serveur Modbus + cycle de 100 ms
    simulation.py   modèle du poste (disjoncteurs, courants, tension)
    sim_main.py     simulation : client Modbus, pas de 100 ms
node-red/
    package.json    dépendances Node-RED
    flows.json      l'IHM (à ouvrir dans l'éditeur Node-RED)
tests/
docs/
```
