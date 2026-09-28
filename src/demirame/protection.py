"""Programme de l'automate : protection et commande des disjoncteurs.

Ce fichier ne fait AUCUNE communication réseau. Il reçoit des valeurs
(courants, positions, ordres ACR) et calcule des sorties (ordres aux
disjoncteurs, alarmes). On peut donc le tester seul.

Analogie avec un automate réel :
- une classe = un bloc fonctionnel (FB) ;
- un objet  = une instance de ce bloc, avec sa propre mémoire.

Le temps est compté en millisecondes entières (dt_ms = durée d'un cycle)
pour éviter les erreurs d'arrondi des nombres à virgule.
"""

# ---------------------------------------------------------------------------
# Réglages des protections (voir docs/specification.md, §5)
# ---------------------------------------------------------------------------
SEUIL_PHASE_A = 800           # protection phase (51) : seuil en ampères
TEMPO_PHASE_MS = 500          # temporisation avant déclenchement
SEUIL_HOMOPOLAIRE_A = 40      # protection homopolaire (51N) : seuil Io
TEMPO_HOMOPOLAIRE_MS = 1000


class Tempo:
    """Temporisation au travail, comme le bloc TON d'un automate.

    - entree : condition surveillée (IN)
    - duree_ms : durée à atteindre (PT)
    - q : sortie, vraie quand l'entrée est restée vraie pendant duree_ms (Q)
    """

    def __init__(self, duree_ms):
        self.duree_ms = duree_ms
        self.ecoule_ms = 0
        self.q = False

    def cycle(self, entree, dt_ms):
        if entree:
            self.ecoule_ms = min(self.ecoule_ms + dt_ms, self.duree_ms)
        else:
            self.ecoule_ms = 0  # l'entrée retombe : la tempo repart à zéro
        self.q = entree and self.ecoule_ms >= self.duree_ms
        return self.q


class CommandeDisjoncteur:
    """Gère les ordres d'ouverture et de fermeture d'un disjoncteur.

    Un ordre reste actif jusqu'à ce que le disjoncteur confirme sa position
    (retour « ouvert » ou « fermé »). L'ouverture est toujours prioritaire.
    """

    def __init__(self):
        self.ordre_ouverture = False
        self.ordre_fermeture = False

    def cycle(self, dj_ferme, demande_ouverture, demande_fermeture):
        if demande_ouverture:
            self.ordre_ouverture = True
        if demande_fermeture:
            self.ordre_fermeture = True

        # Priorité à l'ouverture : en cas de doute, on coupe.
        if self.ordre_ouverture:
            self.ordre_fermeture = False

        # Position atteinte : l'ordre n'a plus lieu d'être.
        if not dj_ferme:
            self.ordre_ouverture = False
        if dj_ferme:
            self.ordre_fermeture = False


class ProtectionDepart:
    """Protection d'un départ : phase (51) + homopolaire (51N) + verrouillage."""

    def __init__(self):
        self.tempo_phase = Tempo(TEMPO_PHASE_MS)
        self.tempo_homopolaire = Tempo(TEMPO_HOMOPOLAIRE_MS)
        self.disjoncteur = CommandeDisjoncteur()

        # Signalisations (recalculées à chaque cycle)
        self.seuil_phase_depasse = False
        self.seuil_homopolaire_depasse = False

        # Alarmes mémorisées : restent vraies jusqu'à l'acquittement
        self.declenchement_phase = False
        self.declenchement_homopolaire = False

    @property
    def verrouille(self):
        """Vrai si le départ a déclenché et n'a pas encore été acquitté."""
        return self.declenchement_phase or self.declenchement_homopolaire

    def cycle(self, courant, courant_residuel, dj_ferme,
              acr_ouverture, acr_fermeture, acquittement, dt_ms):
        # 1. Détection : comparaison aux seuils
        self.seuil_phase_depasse = courant > SEUIL_PHASE_A
        self.seuil_homopolaire_depasse = courant_residuel > SEUIL_HOMOPOLAIRE_A

        # 2. Temporisation puis 3. déclenchement mémorisé
        if self.tempo_phase.cycle(self.seuil_phase_depasse, dt_ms):
            self.declenchement_phase = True
        if self.tempo_homopolaire.cycle(self.seuil_homopolaire_depasse, dt_ms):
            self.declenchement_homopolaire = True

        # 7. Acquittement : seulement si le défaut n'est plus mesuré
        defaut_present = self.seuil_phase_depasse or self.seuil_homopolaire_depasse
        if acquittement and not defaut_present:
            self.declenchement_phase = False
            self.declenchement_homopolaire = False

        # 4, 5, 6. Ordres au disjoncteur
        self.disjoncteur.cycle(
            dj_ferme,
            demande_ouverture=self.verrouille or acr_ouverture,
            demande_fermeture=acr_fermeture and not self.verrouille,
        )
