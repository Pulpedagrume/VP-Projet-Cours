# Demi-rame HTA virtuelle

Projet GEII : contrôle-commande virtuel d'une **demi-rame HTA de poste
source** (1 arrivée + 3 départs).

- **Simulation** du procédé en Python (courants par phase, défauts francs, disjoncteurs)
- **Automate virtuel** en Python (protections I> / Io>, commande des disjoncteurs, relevé des temps)
- **Modbus TCP** entre les composants (`pymodbus`)
- **IHM ACR** avec Node-RED (Dashboard 2.0)

Documentation :
- [`docs/specification.md`](docs/specification.md) : ce que fait le système
- [`docs/mapping_modbus.md`](docs/mapping_modbus.md) : table des adresses Modbus
- [`docs/defauts_fresnel.md`](docs/defauts_fresnel.md) : courants de défaut et diagrammes de Fresnel
  (figures régénérables avec `uv run python docs/figures/generer_figures.py`)

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

| Page | Contenu |
|---|---|
| **Conduite** | Schéma unifilaire (DJ, voyants I> / Io>, courants L1 L2 L3 et Io), commande par sélection puis exécution, alarmes actives et acquittement, tendances, journal des événements |
| **Relevé des temporisations** | Pour chaque départ : phases vues, protection, réglage, t protection, écart, t ouverture DJ, t élimination ; historique exportable en CSV |
| **Réglages protections** | Seuils et temporisations I> / Io> de chaque départ |
| **Banc de test** | Construction d'un défaut franc : choix des phases L1, L2, L3 et de la terre |
| **Fresnel et défauts** | Diagramme de Fresnel et formes d'onde en temps réel (arrivée ou départ), tableau module / angle, fiches théoriques de chaque défaut |

L'éditeur Node-RED est sur http://localhost:1880.

## Démonstration rapide

1. **Banc de test** → Départ 2 : sélectionner **L1** et **L2** → *Appliquer*
   (biphasé isolé). Après 500 ms le DJ du départ 2 s'ouvre, alarme
   « déclenchement I> (L1-L2) ».
2. **Relevé des temporisations** : t protection ≈ 500 ms, t ouverture DJ,
   t élimination.
3. **Conduite** → cliquer sur le DJ du départ 2 → *Fermer* : l'automate
   refuse tant que l'alarme n'est pas acquittée.
4. **Banc de test** → *Supprimer*, puis **Conduite** → *Acquitter* → sélectionner
   le DJ → *Fermer* : le départ revient en service.
5. Recommencer avec **L3 + Terre** (monophasé terre) : seul Io> démarre,
   déclenchement après 1000 ms.
6. **Réglages** : passer la tempo I> à 250 ms, refaire un défaut, comparer le
   relevé.

## Tests

```bash
uv run pytest
```

## Organisation

```
src/demirame/
    mapping.py      table des adresses Modbus (unique)
    protection.py   programme de l'automate (I>, Io>, tempos, verrouillage, relevé des temps)
    plc_main.py     automate : serveur Modbus + cycle de 20 ms
    simulation.py   modèle du poste en phaseurs (disjoncteurs, courants, tensions, défauts)
    sim_main.py     simulation : client Modbus, pas de 10 ms
node-red/
    package.json    dépendances Node-RED
    flows.json      l'IHM (à ouvrir dans l'éditeur Node-RED)
tests/
docs/
    figures/        diagrammes de Fresnel (SVG) et leur script de génération
```
