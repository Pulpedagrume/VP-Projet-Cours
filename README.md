# Demi-rame HTA virtuelle

Projet GEII : contrôle-commande virtuel d'une **demi-rame HTA de poste
source** (1 arrivée + 3 départs).

- **Simulation** du procédé en Python (courants, défauts, disjoncteurs)
- **Automate virtuel** en Python (protections, commande des disjoncteurs)
- **Modbus TCP** entre les composants (`pymodbus`)
- **IHM ACR** avec Node-RED

La spécification est dans [`docs/specification.md`](docs/specification.md).

## État d'avancement

| Étape | État |
|---|---|
| Spécification version 1 (défaut franc phase + homopolaire) | fait |
| Logique automate `protection.py` + tests | fait |
| Simulation du procédé | à faire |
| Communication Modbus TCP | à faire |
| IHM Node-RED | à faire |

## Installation

Prérequis : [uv](https://docs.astral.sh/uv/) (version récente).

```bash
git clone https://github.com/Pulpedagrume/VP-Projet-Cours.git
cd VP-Projet-Cours
uv sync          # crée .venv et installe les dépendances
```

## Lancer les tests

```bash
uv run pytest
```

## Organisation

```
src/demirame/
    protection.py   programme de l'automate (seuils, tempos, verrouillage)
tests/
    test_protection.py
docs/
    specification.md
```
