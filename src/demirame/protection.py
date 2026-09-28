"""Programme de l'automate : protection et commande des disjoncteurs.

Ce fichier ne fait AUCUNE communication réseau. Il reçoit des valeurs
(courants, positions, ordres ACR) et calcule des sorties (ordres aux
disjoncteurs, alarmes, relevé des temps). On peut donc le tester seul.

Analogie avec un automate réel :
- une classe = un bloc fonctionnel (FB) ;
- un objet  = une instance de ce bloc, avec sa propre mémoire.

Le temps est compté en millisecondes (dt_ms = durée réelle du cycle).

Protections d'un départ (à temps constant) :
- I>  (ANSI 51)  : maximum de courant de phase, sur L1, L2 et L3 ;
- Io> (ANSI 51N) : maximum de courant résiduel (défaut à la terre).
"""

from demirame.mapping import BIT_TERRE, BITS_PHASES, ORIGINE_PHASE, ORIGINE_TERRE

# ---------------------------------------------------------------------------
# Réglages par défaut (modifiables depuis l'IHM, page « Réglages »)
# ---------------------------------------------------------------------------
SEUIL_PHASE_A = 800
TEMPO_PHASE_MS = 500
SEUIL_TERRE_A = 40
TEMPO_TERRE_MS = 1000

# Plages autorisées : un réglage hors plage est ramené dans la plage
PLAGE_SEUIL_PHASE_A = (50, 8000)
PLAGE_SEUIL_TERRE_A = (5, 1000)
PLAGE_TEMPO_MS = (0, 10000)


def borner(valeur, plage):
    """Ramène une valeur dans la plage (mini, maxi)."""
    mini, maxi = plage
    return max(mini, min(valeur, maxi))


class Tempo:
    """Temporisation au travail, comme le bloc TON d'un automate.

    - entree : condition surveillée (IN)
    - duree_ms : durée à atteindre (PT), modifiable à tout moment
    - q : sortie, vraie quand l'entrée est restée vraie pendant duree_ms (Q)

    Le temps est compté à partir du cycle où l'entrée passe à 1.
    """

    def __init__(self, duree_ms):
        self.duree_ms = duree_ms
        self.ecoule_ms = 0
        self.entree_precedente = False
        self.q = False

    def cycle(self, entree, dt_ms):
        if entree and self.entree_precedente:
            self.ecoule_ms += dt_ms
        else:
            self.ecoule_ms = 0  # front montant ou entrée à 0 : on repart de zéro
        self.entree_precedente = entree
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


class ReleveTemps:
    """Chronomètre le défaut, comme l'enregistreur d'un relais de protection.

    t = 0 au premier cycle où un seuil est dépassé. On relève :
    - temps_protection   : t de l'ordre de déclenchement (≈ temporisation réglée) ;
    - temps_ouverture_dj : durée entre l'ordre et le retour « DJ ouvert » ;
    - temps_elimination  : t du retour « DJ ouvert » (durée totale du défaut vu).
    """

    def __init__(self):
        self.en_cours = False       # chronomètre en marche
        self.chrono_ms = 0
        self.attente_ouverture = False
        # Dernier relevé (conservé après l'acquittement)
        self.temps_protection = 0
        self.temps_ouverture_dj = 0
        self.temps_elimination = 0
        self.phases_defaut = 0
        self.origine = 0            # ORIGINE_PHASE et/ou ORIGINE_TERRE
        self.nb_declenchements = 0

    def cycle(self, defaut_vu, origine, phases, dj_ferme, dt_ms):
        """origine = protection(s) ayant déclenché ce cycle (0 si aucune)."""
        # Démarrage du chronomètre à l'apparition du défaut
        if defaut_vu and not self.en_cours:
            self.en_cours = True
            self.chrono_ms = 0
        elif self.en_cours:
            self.chrono_ms += dt_ms

        # Front montant du déclenchement : on note le temps de la protection
        if origine and self.en_cours and not self.attente_ouverture:
            self.attente_ouverture = True
            self.temps_protection = self.chrono_ms
            self.phases_defaut = phases
            self.origine = origine
            self.temps_ouverture_dj = 0
            self.temps_elimination = 0
            self.nb_declenchements += 1

        # Retour « DJ ouvert » : fin de l'élimination du défaut
        if self.attente_ouverture and not dj_ferme:
            self.temps_elimination = self.chrono_ms
            self.temps_ouverture_dj = self.chrono_ms - self.temps_protection
            self.attente_ouverture = False
            self.en_cours = False

        # Défaut disparu avant le déclenchement : rien à relever
        if not defaut_vu and not self.attente_ouverture:
            self.en_cours = False


class ProtectionDepart:
    """Protection d'un départ : I> + Io> + verrouillage + relevé des temps."""

    def __init__(self):
        # Réglages (modifiables pendant le fonctionnement)
        self.seuil_phase = SEUIL_PHASE_A
        self.seuil_terre = SEUIL_TERRE_A
        self.tempo_phase = Tempo(TEMPO_PHASE_MS)
        self.tempo_terre = Tempo(TEMPO_TERRE_MS)

        self.disjoncteur = CommandeDisjoncteur()
        self.releve = ReleveTemps()

        # Démarrages (recalculés à chaque cycle)
        self.demarrage_phase = False
        self.demarrage_terre = False
        self.phases_vues = 0        # bits des phases au-dessus du seuil

        # Alarmes mémorisées : restent vraies jusqu'à l'acquittement
        self.declenchement_phase = False
        self.declenchement_terre = False

    def regler(self, seuil_phase, tempo_phase, seuil_terre, tempo_terre):
        """Applique de nouveaux réglages (ramenés dans les plages autorisées)."""
        self.seuil_phase = borner(seuil_phase, PLAGE_SEUIL_PHASE_A)
        self.tempo_phase.duree_ms = borner(tempo_phase, PLAGE_TEMPO_MS)
        self.seuil_terre = borner(seuil_terre, PLAGE_SEUIL_TERRE_A)
        self.tempo_terre.duree_ms = borner(tempo_terre, PLAGE_TEMPO_MS)

    @property
    def verrouille(self):
        """Vrai si le départ a déclenché et n'a pas encore été acquitté."""
        return self.declenchement_phase or self.declenchement_terre

    def cycle(self, courants, courant_residuel, dj_ferme,
              acr_ouverture, acr_fermeture, acquittement, dt_ms):
        """courants = [I L1, I L2, I L3] en ampères."""
        # 1. Détection : comparaison aux seuils, phase par phase
        self.phases_vues = 0
        for bit, courant in zip(BITS_PHASES, courants):
            if courant > self.seuil_phase:
                self.phases_vues |= bit
        self.demarrage_phase = self.phases_vues != 0
        self.demarrage_terre = courant_residuel > self.seuil_terre
        if self.demarrage_terre:
            self.phases_vues |= BIT_TERRE

        # 2. Temporisation puis 3. déclenchement mémorisé
        if self.tempo_phase.cycle(self.demarrage_phase, dt_ms):
            self.declenchement_phase = True
        if self.tempo_terre.cycle(self.demarrage_terre, dt_ms):
            self.declenchement_terre = True

        # 4. Relevé des temps
        origine = 0
        if self.declenchement_phase:
            origine |= ORIGINE_PHASE
        if self.declenchement_terre:
            origine |= ORIGINE_TERRE
        self.releve.cycle(
            defaut_vu=self.demarrage_phase or self.demarrage_terre,
            origine=origine,
            phases=self.phases_vues,
            dj_ferme=dj_ferme,
            dt_ms=dt_ms,
        )

        # 5. Acquittement : seulement si le défaut n'est plus mesuré
        defaut_present = self.demarrage_phase or self.demarrage_terre
        if acquittement and not defaut_present:
            self.declenchement_phase = False
            self.declenchement_terre = False

        # 6. Ordres au disjoncteur (ouverture prioritaire)
        self.disjoncteur.cycle(
            dj_ferme,
            demande_ouverture=self.verrouille or acr_ouverture,
            demande_fermeture=acr_fermeture and not self.verrouille,
        )
