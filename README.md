# Demi-rame HTA virtuelle

Projet GEII : contrôle-commande virtuel d'une **demi-rame HTA de poste
source** (1 arrivée + 3 départs).

- **Simulation** du procédé en Python (phaseurs, défauts francs fugitifs / semi-permanents / permanents,
  disjoncteurs, **mode aléatoire** qui représente la vie normale du poste)
- **Automate virtuel** en Python (protections I> / Io>, **réenclencheur RR + RL** sur les départs,
  protection de l'arrivée avec **sélectivité logique SLP**, relevé des temps)
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
| **Conduite** | Schéma unifilaire (DJ, voyants I> / Io> / SLP, état du réenclencheur, courants L1 L2 L3 et Io), commande par sélection puis exécution, alarmes actives et acquittement, tendances, journal des événements |
| **Relevé des temporisations** | Pour l'arrivée et chaque départ : phases vues, protection, réglage, t protection, écart, t ouverture DJ, t élimination, résultat du réenclencheur ; historique exportable en CSV |
| **Réglages protections** | SLP en / hors service, seuils et temporisations de l'arrivée et des départs, tempo SLP, réenclencheur en / hors service |
| **Banc de test** | **Mode aléatoire** (marche / arrêt) ; défaut manuel sur un départ ou sur le jeu de barres : phases L1, L2, L3, terre et nature (fugitif, semi-permanent, permanent) |
| **Fresnel et défauts** | Diagramme de Fresnel et formes d'onde en temps réel (arrivée ou départ), tableau module / angle, fiches théoriques de chaque défaut |

L'**éditeur Node-RED** est sur http://localhost:1880. Il montre les nœuds et
leurs connexions, rangés en 4 zones qui suivent le trajet des données :

1. **Démarrage** : chargement de la table des adresses Modbus ;
2. **Lecture de l'automate** : trois nœuds Modbus lisent les coils, les
   registres et les phaseurs toutes les 250 ms (l'état « active » sous chaque
   nœud indique que la connexion Modbus fonctionne), puis « Décodage état »
   construit l'objet envoyé aux pages ;
3. **Pages de l'IHM** : un nœud par page ou courbe du tableau de bord ;
4. **Commandes** : les boutons des pages envoient une commande, traduite en
   écriture Modbus dans l'automate.

## Démonstration rapide

1. **Réenclencheur, défaut fugitif** : Banc de test → Départ 1 → **L1 + Terre**,
   **Fugitif** → *Appliquer*. Io> déclenche après 1 s, le RR referme 0,3 s plus
   tard et le journal indique « cycle réussi, défaut éliminé par le RR ».
2. **Défaut semi-permanent** : Départ 2 → **L1 + L2**, **Semi-permanent**. Le RR
   échoue (redéclenchement), puis le RL referme au bout de 15 s et réussit.
3. **Défaut permanent** : Départ 3 → **L1 + L2 + L3**, **Permanent**. Après RR
   et RL : **déclenchement définitif**. Supprimer le défaut, puis Conduite →
   *Acquitter* → cliquer sur le DJ → *Fermer*.
4. **SLP** : Jeu de barres → **L1 + Terre** → *Appliquer*. L'arrivée déclenche
   en ≈ 200 ms (voyant SLP rouge). Réglages → *Mettre hors service* la SLP,
   recommencer : ≈ 1000 ms. Comparer dans le **Relevé des temporisations**.
5. **Mode aléatoire** : Banc de test → *Démarrer*. Laisser vivre le poste,
   suivre le journal et le relevé ; intervenir (acquitter, refermer) quand
   une cellule est verrouillée.

## Tests

```bash
uv run pytest
```

## Organisation

```
src/demirame/
    mapping.py      table des adresses Modbus (unique)
    protection.py   programme de l'automate (I>, Io>, réenclencheur, SLP, relevé des temps)
    plc_main.py     automate : serveur Modbus + cycle de 20 ms
    simulation.py   modèle du poste en phaseurs (disjoncteurs, courants, tensions, défauts)
    sim_main.py     simulation : client Modbus, pas de 10 ms
    aleatoire.py    mode aléatoire (charge variable, défauts tirés au hasard)
node-red/
    package.json    dépendances Node-RED
    flows.json      l'IHM (à ouvrir dans l'éditeur Node-RED)
tests/
docs/
    figures/        diagrammes de Fresnel (SVG) et leur script de génération
```
