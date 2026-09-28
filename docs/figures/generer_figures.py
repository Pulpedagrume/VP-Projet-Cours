"""Génère les diagrammes de Fresnel et les formes d'onde des défauts (fichiers SVG).

Lancement :  uv run python docs/figures/generer_figures.py

Les phaseurs viennent directement du modèle de simulation (simulation.py),
sans bruit : les figures montrent exactement ce que simule le projet.
"""

import cmath
import math
from pathlib import Path

from demirame import simulation
from demirame.mapping import BIT_L1, BIT_L2, BIT_L3, BIT_TERRE

DOSSIER = Path(__file__).parent

# Couleurs des phases (palette validée daltonisme) ; résiduels en noir pointillé
COULEURS = ["#2a78d6", "#eb6834", "#1baf7a"]
NOIR = "#1f2328"
GRIS = "#57606a"
GRILLE = "#d0d7de"

DEFAUTS = [
    ("normal", "Fonctionnement normal", 0),
    ("monophase_terre", "Défaut monophasé L1-terre", BIT_L1 | BIT_TERRE),
    ("biphase_isole", "Défaut biphasé isolé L2-L3", BIT_L2 | BIT_L3),
    ("biphase_terre", "Défaut biphasé L2-L3-terre", BIT_L2 | BIT_L3 | BIT_TERRE),
    ("triphase", "Défaut triphasé", BIT_L1 | BIT_L2 | BIT_L3),
]


def phaseurs(defaut):
    """Courants du départ 1, Io, tensions simples et V0 pour un défaut donné (sans bruit)."""
    simulation.BRUIT_CHARGE = 0
    simulation.BRUIT_TENSION = 0
    poste = simulation.Poste()
    poste.injecter(1, defaut)
    poste.pas([False] * 4, [False] * 4, 10)
    return poste.courants[1], poste.courant_residuel(1), poste.tensions, poste.tension_residuelle


# ---------------------------------------------------------------------------
# Petits outils SVG
# ---------------------------------------------------------------------------

def fleche(x0, y0, z, echelle, couleur, epaisseur, pointille=False, nom=""):
    """Vecteur de Fresnel : l'axe réel vers la droite, l'axe imaginaire vers le haut."""
    if abs(z) * echelle < 2:
        return ""
    x1, y1 = x0 + z.real * echelle, y0 - z.imag * echelle
    tirets = ' stroke-dasharray="6 4"' if pointille else ""
    id_marqueur = "m" + couleur.strip("#")
    svg = (f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{couleur}" '
           f'stroke-width="{epaisseur}"{tirets} marker-end="url(#{id_marqueur})"/>')
    if nom and abs(z) * echelle > 24:
        # Étiquette un peu au-delà de la pointe (les petits vecteurs sont dans le tableau)
        u = z / abs(z)
        xt, yt = x1 + u.real * 16, y1 - u.imag * 16 + 4
        svg += f'<text x="{xt:.1f}" y="{yt:.1f}" text-anchor="middle" class="nom">{nom}</text>'
    return svg


def marqueurs():
    svg = "<defs>"
    for c in COULEURS + [NOIR, GRIS]:
        svg += (f'<marker id="m{c.strip("#")}" viewBox="0 0 10 10" refX="9" refY="5" '
                f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>')
    return svg + "</defs>"


def diagramme_fresnel(x0, y0, rayon, courants, io, tensions, v0):
    """Diagramme de Fresnel : tensions en traits fins, courants en traits épais."""
    svg = f'<circle cx="{x0}" cy="{y0}" r="{rayon}" fill="none" stroke="{GRILLE}"/>'
    svg += f'<circle cx="{x0}" cy="{y0}" r="{rayon / 2}" fill="none" stroke="{GRILLE}" stroke-dasharray="2 3"/>'
    svg += f'<line x1="{x0 - rayon - 10}" y1="{y0}" x2="{x0 + rayon + 10}" y2="{y0}" stroke="{GRILLE}"/>'
    svg += f'<line x1="{x0}" y1="{y0 - rayon - 10}" x2="{x0}" y2="{y0 + rayon + 10}" stroke="{GRILLE}"/>'

    echelle_v = rayon / (simulation.TENSION_SIMPLE_KV * math.sqrt(3))       # 20 kV = rayon
    i_max = max([abs(i) for i in courants] + [abs(io), 1])
    echelle_i = 0.92 * rayon / i_max

    for p in range(3):
        svg += fleche(x0, y0, tensions[p], echelle_v, COULEURS[p], 1.5, nom=f"V{p + 1}")
    svg += fleche(x0, y0, v0, echelle_v, GRIS, 1.5, pointille=True, nom="V0")
    for p in range(3):
        svg += fleche(x0, y0, courants[p], echelle_i, COULEURS[p], 3.5, nom=f"I{p + 1}")
    svg += fleche(x0, y0, io, echelle_i, NOIR, 3, pointille=True, nom="Io")

    svg += (f'<text x="{x0}" y="{y0 + rayon + 34}" text-anchor="middle" class="petit">'
            f'Cercle : 20 kV pour les tensions, {i_max:.0f} A pour les courants</text>')
    return svg


def formes_d_onde(x0, y0, largeur, hauteur, avant, apres, titre, unite, residuel_avant, residuel_apres):
    """Courbes instantanées sur 60 ms : défaut à t = 20 ms."""
    duree_ms, t_defaut = 60, 20
    omega = 2 * math.pi * 50
    crete = math.sqrt(2) * max([abs(z) for z in apres + avant + [residuel_apres]] + [1e-9])

    def y(valeur):
        return y0 + hauteur / 2 - valeur / crete * (hauteur / 2 - 6)

    def x(t_ms):
        return x0 + t_ms / duree_ms * largeur

    svg = f'<rect x="{x0}" y="{y0}" width="{largeur}" height="{hauteur}" fill="none" stroke="{GRILLE}"/>'
    svg += f'<line x1="{x0}" y1="{y(0):.1f}" x2="{x0 + largeur}" y2="{y(0):.1f}" stroke="{GRILLE}"/>'
    svg += (f'<line x1="{x(t_defaut):.1f}" y1="{y0}" x2="{x(t_defaut):.1f}" y2="{y0 + hauteur}" '
            f'stroke="{GRIS}" stroke-dasharray="4 3"/>')
    svg += f'<text x="{x(t_defaut) + 4:.1f}" y="{y0 + 12}" class="petit">défaut</text>'
    svg += f'<text x="{x0}" y="{y0 - 6}" class="titre-courbe">{titre}</text>'
    svg += f'<text x="{x0 - 6}" y="{y0 + 10}" text-anchor="end" class="petit">{crete:.0f} {unite}</text>'
    for t in (0, 20, 40, 60):
        svg += f'<text x="{x(t):.1f}" y="{y0 + hauteur + 14}" text-anchor="middle" class="petit">{t} ms</text>'

    series = [(avant[p], apres[p], COULEURS[p], "") for p in range(3)]
    series.append((residuel_avant, residuel_apres, NOIR, ' stroke-dasharray="5 3"'))
    for z_avant, z_apres, couleur, tirets in series:
        points = []
        for k in range(301):
            t = k / 300 * duree_ms
            z = z_avant if t < t_defaut else z_apres
            valeur = math.sqrt(2) * abs(z) * math.sin(omega * t / 1000 + cmath.phase(z))
            points.append(f"{x(t):.1f},{y(valeur):.1f}")
        svg += f'<polyline points="{" ".join(points)}" fill="none" stroke="{couleur}" stroke-width="2"{tirets}/>'
    return svg


def ligne_valeur(x, y, nom, z, unite, couleur):
    """Une ligne du tableau : pastille de couleur, nom, module, angle."""
    angle = math.degrees(cmath.phase(z)) % 360 if abs(z) > 0.05 else 0
    return (f'<rect x="{x}" y="{y - 9}" width="10" height="10" fill="{couleur}"/>'
            f'<text x="{x + 16}" y="{y}" class="nom">{nom}</text>'
            f'<text x="{x + 150}" y="{y}" text-anchor="end" class="valeur">{abs(z):.1f} {unite}</text>'
            f'<text x="{x + 205}" y="{y}" text-anchor="end" class="valeur">{angle:.0f}°</text>')


def tableau(x0, y0, courants, io, tensions, v0):
    """Modules et angles de tous les phaseurs, sous le diagramme."""
    x_courants = x0 + 225
    svg = (f'<text x="{x0}" y="{y0}" class="titre-courbe">Tensions simples</text>'
           f'<text x="{x_courants}" y="{y0}" class="titre-courbe">Courants</text>')
    for p in range(3):
        y = y0 + 20 + 17 * p
        svg += ligne_valeur(x0, y, f"V{p + 1}", tensions[p], "kV", COULEURS[p])
        svg += ligne_valeur(x_courants, y, f"I{p + 1}", courants[p], "A", COULEURS[p])
    svg += ligne_valeur(x0, y0 + 71, "V0", v0, "kV", GRIS)
    svg += ligne_valeur(x_courants, y0 + 71, "Io", io, "A", NOIR)
    return svg


def legende(x0, y0):
    svg = ""
    for p, c in enumerate(COULEURS):
        svg += f'<line x1="{x0 + p * 70}" y1="{y0}" x2="{x0 + p * 70 + 18}" y2="{y0}" stroke="{c}" stroke-width="3"/>'
        svg += f'<text x="{x0 + p * 70 + 23}" y="{y0 + 4}" class="petit">L{p + 1}</text>'
    svg += f'<line x1="{x0 + 210}" y1="{y0}" x2="{x0 + 228}" y2="{y0}" stroke="{NOIR}" stroke-width="2.5" stroke-dasharray="5 3"/>'
    svg += f'<text x="{x0 + 233}" y="{y0 + 4}" class="petit">résiduel (Io, V0)</text>'
    return svg


def figure(nom_fichier, titre, defaut):
    courants, io, tensions, v0 = phaseurs(defaut)
    courants_avant, io_avant, tensions_avant, v0_avant = phaseurs(0)

    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 540" width="920" height="540" '
           'font-family="Segoe UI, Roboto, Arial, sans-serif">',
           '<style>.titre{font-size:18px;font-weight:600;fill:#1f2328}'
           '.nom{font-size:13px;font-weight:600;fill:#1f2328}'
           '.petit{font-size:11px;fill:#57606a}'
           '.titre-courbe{font-size:13px;font-weight:600;fill:#1f2328}'
           '.valeur{font-size:12px;fill:#1f2328;font-family:Consolas, monospace}</style>',
           '<rect width="920" height="540" fill="#ffffff"/>',
           marqueurs(),
           f'<text x="20" y="30" class="titre">{titre}</text>',
           legende(20, 52),
           diagramme_fresnel(210, 235, 145, courants, io, tensions, v0),
           formes_d_onde(470, 90, 420, 130, tensions_avant, tensions, "Tensions simples v(t)", "kV", v0_avant, v0),
           formes_d_onde(470, 270, 420, 130, courants_avant, courants, "Courants i(t) du départ", "A", io_avant, io),
           tableau(40, 440, courants, io, tensions, v0),
           '<text x="470" y="440" class="petit">Défaut franc sur le départ 1, apparu à t = 20 ms.</text>',
           '<text x="470" y="456" class="petit">Formes d\'onde reconstruites à partir des phaseurs (régime établi,</text>',
           '<text x="470" y="472" class="petit">sans composante continue transitoire). Valeurs de crête indiquées.</text>',
           "</svg>"]
    (DOSSIER / f"{nom_fichier}.svg").write_text("\n".join(svg), encoding="utf-8")

    # Tableau des valeurs (affiché dans la console, repris dans la doc)
    def fmt(z, unite):
        return f"{abs(z):7.1f} {unite} ∠ {math.degrees(cmath.phase(z)) % 360:5.0f}°"
    print(f"\n{titre}")
    for p in range(3):
        print(f"  V{p + 1} = {fmt(tensions[p], 'kV')}    I{p + 1} = {fmt(courants[p], 'A')}")
    print(f"  V0 = {fmt(v0, 'kV')}    Io = {fmt(io, 'A')}")


if __name__ == "__main__":
    for nom, titre, defaut in DEFAUTS:
        figure(f"fresnel_{nom}", titre, defaut)
    print(f"\nFigures écrites dans {DOSSIER}")
