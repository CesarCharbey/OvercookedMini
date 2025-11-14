# recette.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Tuple
import random

# États possibles d’un aliment
class EtatAliment(Enum):
    SORTI_DU_BAC = auto()
    COUPE = auto()
    CUIT = auto()


# Classe Aliment (inchangée)
@dataclass
class Aliment:
    nom: str
    etat: EtatAliment
    vitesse_peremption: float
    fraicheur: float = 1.0

    def tick(self, dt_s: float) -> None:
        self.fraicheur = max(0.0, self.fraicheur - self.vitesse_peremption * dt_s)

    @property
    def est_perime(self) -> bool:
        return self.fraicheur <= 0.0

    def transformer(self, nouvel_etat: EtatAliment) -> None:
        if not self.est_perime:
            self.etat = nouvel_etat

    def couleur_ui(self) -> str:
        if self.etat == EtatAliment.SORTI_DU_BAC: return "#7fbf7f"
        if self.etat == EtatAliment.COUPE:        return "#ffeb7a"
        if self.etat == EtatAliment.CUIT:         return "#ff9966"
        return "white"


@dataclass(frozen=True)
class IngredientRequis:
    nom: str
    etats: List[EtatAliment]

    @property
    def etat_final(self) -> EtatAliment:
        """L’état final attendu pour compléter la recette."""
        return self.etats[-1]

    def etape_suivante(self, etat_actuel: EtatAliment) -> EtatAliment | None:
        """
        Retourne l’étape suivante de transformation :
          - SORTI_DU_BAC -> COUPE
          - COUPE -> CUIT
          - CUIT -> None (terminé)
        """
        # si déjà dans la chaîne
        if etat_actuel in self.etats:
            idx = self.etats.index(etat_actuel)
            if idx + 1 < len(self.etats):
                return self.etats[idx + 1]
            return None  # déjà terminé

        # sinon : SORTI_DU_BAC, on retourne la première étape
        return self.etats[0]


# Recette = liste d’ingrédients
@dataclass
class Recette:
    nom: str
    requis: List[IngredientRequis]

    def est_complete_avec(self, items: List[Aliment]) -> bool:
        """Vrai si tous les ingrédients nécessaires (état final) sont présents."""
        needed = self.requis.copy()
        used = [False] * len(items)

        for req in needed:
            found = False
            for i, a in enumerate(items):
                if used[i]:
                    continue
                if (not a.est_perime) and a.nom == req.nom and a.etat == req.etat_final:
                    used[i] = True
                    found = True
                    break
            if not found:
                return False
        return True


# Aliments disponibles en bac
ALIMENTS_BAC: List[Tuple[str, float]] = [
    ("tomate", 0.0005),
    ("viande", 0.0010),
    ("pate",   0.0003),
    ("salade", 0.0008),
]


def prendre_au_bac(nom: str, vitesse: float) -> Aliment:
    return Aliment(nom=nom, etat=EtatAliment.SORTI_DU_BAC, vitesse_peremption=vitesse)


# Liste des recettes
RECETTES_POOL: List[Recette] = [
    Recette("Tomate poelee", [
        IngredientRequis("tomate", [EtatAliment.CUIT]),
    ]),

    Recette("Viande cuite", [
        IngredientRequis("viande", [EtatAliment.COUPE, EtatAliment.CUIT]),
    ]),

    Recette("Pates nature", [
        IngredientRequis("pate", [EtatAliment.CUIT]),
    ]),

    Recette("Salade coupee", [
        IngredientRequis("salade", [EtatAliment.COUPE]),
    ]),

    Recette("Salade composee", [
        IngredientRequis("salade", [EtatAliment.COUPE]),
        IngredientRequis("tomate", [EtatAliment.COUPE]),
    ]),

    Recette("Pates bolognaises", [
        IngredientRequis("pate",   [EtatAliment.CUIT]),
        IngredientRequis("viande", [EtatAliment.COUPE, EtatAliment.CUIT]),
    ]),

    Recette("Sandwich", [
        IngredientRequis("viande", [EtatAliment.COUPE, EtatAliment.CUIT]),
        IngredientRequis("salade", [EtatAliment.COUPE]),
    ]),
]

# Nouvelle recette aléatoire
def nouvelle_recette() -> Recette:
    return random.choice(RECETTES_POOL)
