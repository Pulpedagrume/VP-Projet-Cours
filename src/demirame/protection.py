"""Programme de l'automate : protections, réenclencheur, SLP, commande des disjoncteurs.

Ce fichier ne fait AUCUNE communication réseau. Il reçoit des valeurs
(courants, positions, ordres ACR) et calcule des sorties (ordres aux
disjoncteurs, alarmes, relevé des temps). On peut donc le tester seul.

Analogie avec un automate réel :
- une classe = un bloc fonctionnel (FB) ;
- un objet  = une instance de ce bloc, avec sa propre mémoire.

Le temps est compté en millisecondes (dt_ms = durée réelle du cycle).

Contenu :
- Tempo, SeuilTemporise, CommandeDisjoncteur, ReleveTemps : briques de base ;
- Reenclencheur : cycle RR (rapide) puis RL (lent) des départs ;
- ProtectionDepart : I> (51) + Io> (51N) + réenclencheur ;
- ProtectionArrivee : I> + Io> de secours + sélectivité logique (SLP).
"""

from demirame.mapping import (
    BIT_TERRE,
    BITS_PHASES,
    ETAPE_DEFINITIF,
    ETAPE_RECUPERATION_RL,
    ETAPE_RECUPERATION_RR,
    ETAPE_REPOS,
    ETAPE_TEMPS_MORT_RL,
    ETAPE_TEMPS_MORT_RR,
    ORIGINE_PHASE,
    ORIGINE_SLP,
    ORIGINE_TERRE,
    RESULTAT_AUCUN,
    RESULTAT_DEFINITIF,
    RESULTAT_REUSSI_RL,
    RESULTAT_REUSSI_RR,
)

# ---------------------------------------------------------------------------
# Réglages par défaut (modifiables depuis l'IHM, page « Réglages »)
# ---------------------------------------------------------------------------
# Départs
SEUIL_PHASE_A = 800
TEMPO_PHASE_MS = 500
SEUIL_TERRE_A = 40
TEMPO_TERRE_MS = 1000
# Arrivée : temporisations plus longues que celles des départs (sélectivité
# chronométrique) : un défaut sur un départ est éliminé par le départ.
SEUIL_PHASE_ARRIVEE_A = 2500
TEMPO_PHASE_ARRIVEE_MS = 1000
SEUIL_TERRE_ARRIVEE_A = 40
TEMPO_TERRE_ARRIVEE_MS = 1500
TEMPO_SLP_MS = 200                  # déclenchement accéléré sur défaut barre

# Réenclencheur (constantes du cycle)
TEMPS_MORT_RR_MS = 300              # réenclenchement rapide
TEMPS_MORT_RL_MS = 15000            # réenclenchement lent
TEMPS_RECUPERATION_MS = 10000       # surveillance après chaque réenclenchement

# Plages autorisées : un réglage hors plage est ramené dans la plage
PLAGE_SEUIL_PHASE_A = (50, 8000)
PLAGE_SEUIL_TERRE_A = (5, 1000)
PLAGE_TEMPO_MS = (0, 10000)


def borner(valeur, plage):
    """Ramène une valeur dans la plage (mini, maxi)."""
    mini, maxi = plage
    return max(mini, min(valeur, maxi))


def bits_phases(courants, seuil):
    """Bits des phases dont le courant dépasse le seuil (BIT_L1, BIT_L2, BIT_L3)."""
    bits = 0
    for bit, courant in zip(BITS_PHASES, courants):
        if courant > seuil:
            bits |= bit
    return bits


# ===========================================================================
# BRIQUES DE BASE
# ===========================================================================

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


class SeuilTemporise:
    """Un élément de protection à temps constant : seuil + temporisation.

    C'est le principe des fonctions ANSI 51 (I>) et 51N (Io>) :
    démarrage quand la mesure dépasse le seuil, ordre de déclenchement
    quand le dépassement dure plus que la temporisation.
    """

    def __init__(self, seuil, tempo_ms):
        self.seuil = seuil
        self.tempo = Tempo(tempo_ms)
        self.demarrage = False

    def cycle(self, mesure, dt_ms):
        self.demarrage = mesure > self.seuil
        return self.tempo.cycle(self.demarrage, dt_ms)


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
        self.origine = 0            # bits ORIGINE_*
        self.nb_declenchements = 0

    def cycle(self, defaut_vu, origine, phases, dj_ferme, dt_ms):
        """origine = protection(s) ayant déclenché ce cycle (0 si aucune)."""
        # Démarrage du chronomètre à l'apparition du défaut
        if defaut_vu and not self.en_cours:
            self.en_cours = True
            self.chrono_ms = 0
        elif self.en_cours:
            self.chrono_ms += dt_ms

        # Déclenchement : on note le temps de la protection
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


# ===========================================================================
# RÉENCLENCHEUR (RRL)
# ===========================================================================

class Reenclencheur:
    """Cycle de réenclenchement d'un départ : RR puis RL, puis définitif.

    La plupart des défauts sur une ligne aérienne sont FUGITIFS (branche,
    oiseau, amorçage) : ils disparaissent dès que la ligne est coupée. Le
    réenclencheur referme donc automatiquement le disjoncteur :

        1er déclenchement -> temps mort RR (0,3 s)  -> refermeture
        2e déclenchement  -> temps mort RL (15 s)   -> refermeture
        3e déclenchement  -> DÉFINITIF (verrouillage, acquittement nécessaire)

    Après chaque refermeture, si aucun déclenchement n'arrive pendant le
    temps de récupération (10 s), le cycle est réussi et on revient au repos.

    C'est un GRAFCET : une étape active à la fois (self.etape), des
    transitions dans cycle(). Codage des étapes : mapping.ETAPE_*.
    """

    def __init__(self):
        self.en_service = False
        self.etape = ETAPE_REPOS
        self.tempo = Tempo(0)
        self.refermeture_demandee = False
        self.ordre_fermeture = False     # sortie : ordre de refermeture automatique
        self.resultat = RESULTAT_AUCUN
        self.cycle_reussi = False        # impulsion : le cycle vient de réussir

    def _activer(self, etape, duree_ms=0):
        """Active une étape et relance la temporisation associée."""
        self.etape = etape
        self.tempo = Tempo(duree_ms)
        self.refermeture_demandee = False

    def acquitter(self):
        """Fin du verrouillage après un déclenchement définitif."""
        if self.etape == ETAPE_DEFINITIF:
            self._activer(ETAPE_REPOS)

    def cycle(self, declenchement, dj_ferme, commande_acr, dt_ms):
        """declenchement : impulsion (front montant) de l'ordre de la protection."""
        self.ordre_fermeture = False
        self.cycle_reussi = False

        # Une commande de l'opérateur interrompt le cycle : il reprend la main.
        if commande_acr and self.etape not in (ETAPE_REPOS, ETAPE_DEFINITIF):
            self._activer(ETAPE_REPOS)
            return

        # Transitions sur déclenchement
        if declenchement:
            if self.etape == ETAPE_REPOS and self.en_service:
                self.resultat = RESULTAT_AUCUN
                self._activer(ETAPE_TEMPS_MORT_RR, TEMPS_MORT_RR_MS)
            elif self.etape == ETAPE_RECUPERATION_RR:
                self._activer(ETAPE_TEMPS_MORT_RL, TEMPS_MORT_RL_MS)
            else:
                self.resultat = RESULTAT_DEFINITIF
                self._activer(ETAPE_DEFINITIF)
            return

        # Temps mort : compté DJ ouvert, puis ordre de refermeture
        if self.etape in (ETAPE_TEMPS_MORT_RR, ETAPE_TEMPS_MORT_RL):
            if self.tempo.cycle(not dj_ferme, dt_ms):
                self.refermeture_demandee = True
            if self.refermeture_demandee:
                if dj_ferme:
                    suivante = self.etape + 1   # TEMPS_MORT_xx -> RECUPERATION_xx
                    self._activer(suivante, TEMPS_RECUPERATION_MS)
                else:
                    self.ordre_fermeture = True

        # Récupération : DJ resté fermé assez longtemps -> cycle réussi
        elif self.etape in (ETAPE_RECUPERATION_RR, ETAPE_RECUPERATION_RL):
            if self.tempo.cycle(dj_ferme, dt_ms):
                if self.etape == ETAPE_RECUPERATION_RR:
                    self.resultat = RESULTAT_REUSSI_RR
                else:
                    self.resultat = RESULTAT_REUSSI_RL
                self.cycle_reussi = True
                self._activer(ETAPE_REPOS)


# ===========================================================================
# PROTECTION D'UN DÉPART
# ===========================================================================

class ProtectionDepart:
    """Protection d'un départ : I> + Io> + réenclencheur + relevé des temps."""

    def __init__(self):
        self.phase = SeuilTemporise(SEUIL_PHASE_A, TEMPO_PHASE_MS)
        self.terre = SeuilTemporise(SEUIL_TERRE_A, TEMPO_TERRE_MS)
        self.reenclencheur = Reenclencheur()
        self.disjoncteur = CommandeDisjoncteur()
        self.releve = ReleveTemps()

        self.phases_vues = 0            # bits des phases au-dessus du seuil
        self.ordre_precedent = False
        # Indications du dernier déclenchement : effacées par l'acquittement
        # ou par la réussite du cycle de réenclenchement
        self.declenchement_phase = False
        self.declenchement_terre = False

    # --- Accès simples (utilisés par plc_main.py et les tests) ---
    @property
    def seuil_phase(self):
        return self.phase.seuil

    @property
    def seuil_terre(self):
        return self.terre.seuil

    @property
    def tempo_phase(self):
        return self.phase.tempo

    @property
    def tempo_terre(self):
        return self.terre.tempo

    @property
    def demarrage_phase(self):
        return self.phase.demarrage

    @property
    def demarrage_terre(self):
        return self.terre.demarrage

    @property
    def verrouille(self):
        """Vrai après un déclenchement définitif non acquitté."""
        return self.reenclencheur.etape == ETAPE_DEFINITIF

    def regler(self, seuil_phase, tempo_phase, seuil_terre, tempo_terre):
        """Applique de nouveaux réglages (ramenés dans les plages autorisées)."""
        self.phase.seuil = borner(seuil_phase, PLAGE_SEUIL_PHASE_A)
        self.phase.tempo.duree_ms = borner(tempo_phase, PLAGE_TEMPO_MS)
        self.terre.seuil = borner(seuil_terre, PLAGE_SEUIL_TERRE_A)
        self.terre.tempo.duree_ms = borner(tempo_terre, PLAGE_TEMPO_MS)

    def cycle(self, courants, courant_residuel, dj_ferme,
              acr_ouverture, acr_fermeture, acquittement, dt_ms):
        """courants = [I L1, I L2, I L3] en ampères."""
        # 1. Détection et temporisation
        ordre_phase = self.phase.cycle(max(courants), dt_ms)
        ordre_terre = self.terre.cycle(courant_residuel, dt_ms)
        self.phases_vues = bits_phases(courants, self.phase.seuil)
        if self.terre.demarrage:
            self.phases_vues |= BIT_TERRE

        # 2. Déclenchement = front montant de l'ordre de la protection
        ordre = ordre_phase or ordre_terre
        declenchement = ordre and not self.ordre_precedent
        self.ordre_precedent = ordre
        origine = 0
        if declenchement:
            self.declenchement_phase = ordre_phase
            self.declenchement_terre = ordre_terre
            origine = (ORIGINE_PHASE if ordre_phase else 0) | (ORIGINE_TERRE if ordre_terre else 0)

        # 3. Relevé des temps
        self.releve.cycle(
            defaut_vu=self.phase.demarrage or self.terre.demarrage,
            origine=origine,
            phases=self.phases_vues,
            dj_ferme=dj_ferme,
            dt_ms=dt_ms,
        )

        # 4. Réenclencheur
        self.reenclencheur.cycle(declenchement, dj_ferme, acr_ouverture or acr_fermeture, dt_ms)
        if self.reenclencheur.cycle_reussi:
            self.declenchement_phase = False
            self.declenchement_terre = False

        # 5. Acquittement : seulement si le défaut n'est plus mesuré
        defaut_present = self.phase.demarrage or self.terre.demarrage
        if acquittement and not defaut_present:
            self.reenclencheur.acquitter()
            self.declenchement_phase = False
            self.declenchement_terre = False

        # 6. Ordres au disjoncteur (ouverture prioritaire)
        self.disjoncteur.cycle(
            dj_ferme,
            demande_ouverture=ordre or self.verrouille or acr_ouverture,
            demande_fermeture=self.reenclencheur.ordre_fermeture
            or (acr_fermeture and not self.verrouille),
        )


# ===========================================================================
# PROTECTION DE L'ARRIVÉE + SÉLECTIVITÉ LOGIQUE (SLP)
# ===========================================================================

class ProtectionArrivee:
    """Protection de l'arrivée : I> + Io> de secours + sélectivité logique.

    L'arrivée voit TOUS les défauts, puisque tout le courant passe par elle.
    - Défaut sur un départ : le départ voit aussi le défaut et envoie une
      « attente logique » à l'arrivée. L'arrivée attend sa temporisation
      longue (secours) : c'est le départ qui déclenche, seul.
    - Défaut sur le jeu de barres : aucun départ ne voit le défaut, donc pas
      d'attente logique. Avec la SLP en service, l'arrivée déclenche après
      la temporisation courte TEMPO_SLP_MS au lieu d'attendre la longue.
    L'arrivée n'a pas de réenclencheur : tout déclenchement est définitif.
    """

    def __init__(self):
        self.phase = SeuilTemporise(SEUIL_PHASE_ARRIVEE_A, TEMPO_PHASE_ARRIVEE_MS)
        self.terre = SeuilTemporise(SEUIL_TERRE_ARRIVEE_A, TEMPO_TERRE_ARRIVEE_MS)
        self.tempo_slp = Tempo(TEMPO_SLP_MS)
        self.slp_en_service = True
        self.disjoncteur = CommandeDisjoncteur()
        self.releve = ReleveTemps()

        self.phases_vues = 0
        self.ordre_precedent = False
        self.verrouille = False
        self.declenchement_phase = False
        self.declenchement_terre = False
        self.declenchement_slp = False

    @property
    def demarrage_phase(self):
        return self.phase.demarrage

    @property
    def demarrage_terre(self):
        return self.terre.demarrage

    def regler(self, seuil_phase, tempo_phase, seuil_terre, tempo_terre, tempo_slp):
        self.phase.seuil = borner(seuil_phase, PLAGE_SEUIL_PHASE_A)
        self.phase.tempo.duree_ms = borner(tempo_phase, PLAGE_TEMPO_MS)
        self.terre.seuil = borner(seuil_terre, PLAGE_SEUIL_TERRE_A)
        self.terre.tempo.duree_ms = borner(tempo_terre, PLAGE_TEMPO_MS)
        self.tempo_slp.duree_ms = borner(tempo_slp, PLAGE_TEMPO_MS)

    def cycle(self, courants, courant_residuel, dj_ferme, attente_logique,
              acr_ouverture, acr_fermeture, acquittement, dt_ms):
        """attente_logique : vrai si au moins un départ voit le défaut."""
        # 1. Protections à temps constant (secours des départs)
        ordre_phase = self.phase.cycle(max(courants), dt_ms)
        ordre_terre = self.terre.cycle(courant_residuel, dt_ms)
        demarrage = self.phase.demarrage or self.terre.demarrage
        self.phases_vues = bits_phases(courants, self.phase.seuil)
        if self.terre.demarrage:
            self.phases_vues |= BIT_TERRE

        # 2. SLP : l'arrivée voit le défaut, aucun départ ne le voit
        #    -> défaut sur le jeu de barres -> déclenchement accéléré
        defaut_barre = self.slp_en_service and demarrage and not attente_logique
        ordre_slp = self.tempo_slp.cycle(defaut_barre, dt_ms)

        # 3. Déclenchement (front montant) et indications
        ordre = ordre_phase or ordre_terre or ordre_slp
        declenchement = ordre and not self.ordre_precedent
        self.ordre_precedent = ordre
        origine = 0
        if declenchement:
            self.verrouille = True
            self.declenchement_phase = self.phase.demarrage
            self.declenchement_terre = self.terre.demarrage
            self.declenchement_slp = ordre_slp and not (ordre_phase or ordre_terre)
            origine = ((ORIGINE_PHASE if self.phase.demarrage else 0)
                       | (ORIGINE_TERRE if self.terre.demarrage else 0)
                       | (ORIGINE_SLP if self.declenchement_slp else 0))

        # 4. Relevé des temps
        self.releve.cycle(demarrage, origine, self.phases_vues, dj_ferme, dt_ms)

        # 5. Acquittement : seulement si le défaut n'est plus mesuré
        if acquittement and not demarrage:
            self.verrouille = False
            self.declenchement_phase = False
            self.declenchement_terre = False
            self.declenchement_slp = False

        # 6. Ordres au disjoncteur
        self.disjoncteur.cycle(
            dj_ferme,
            demande_ouverture=ordre or self.verrouille or acr_ouverture,
            demande_fermeture=acr_fermeture and not self.verrouille,
        )
