from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Tuple
import random

class EtatAliment(Enum):
    SORTI_DU_BAC = auto()
    COUPE = auto()
    CUIT = auto()

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
        return self.etats[-1]

    def etape_suivante(self, etat_courant: EtatAliment) -> Optional[EtatAliment]:
        """Retourne la prochaine étape nécessaire pour cet ingrédient."""
        if etat_courant == self.etat_final:
            return None
        try:
            idx = self.etats.index(etat_courant)
            return self.etats[idx + 1]
        except ValueError:
            return self.etats[0]


@dataclass
class Recette:
    nom: str
    requis: List[IngredientRequis]

    @property
    def complexite(self) -> int:
        """Total des étapes de préparation."""
        return sum(len(req.etats) for req in self.requis)


# ------------------------
# Bacs disponibles
# ------------------------

LEGUMES = {
    "tomate":     0.0005,
    "salade":     0.0008,
    "aubergine":  0.0007,
    "courgette":  0.0006,
    "poivron":    0.0007,
}

ALIMENTS_BAC = [
    ("viande", 0.0010),
    ("pate",   0.0003),
    ("oeuf",   0.0009),
    ("pain",   0.0003),

    # bac unique LÉGUMES
    ("legume", 0.0006),
]

def prendre_au_bac(nom: str, vitesse: float) -> Aliment:
    # Bac légumes → donne le légume demandé par le bot
    if nom == "legume":
        # Le main va nous dire quel légume exact il veut
        raise RuntimeError("Appel incorrect : utiliser prendre_legume(nom_reel)")

    return Aliment(nom=nom, etat=EtatAliment.SORTI_DU_BAC, vitesse_peremption=vitesse)


def prendre_legume(nom_legume: str) -> Aliment:
    """Retourne un légume spécifique depuis le bac unique."""
    return Aliment(
        nom=nom_legume,
        etat=EtatAliment.SORTI_DU_BAC,
        vitesse_peremption=LEGUMES[nom_legume]
    )


# ------------------------
# RECETTES AVANCÉES
# ------------------------

RECETTES_POOL: List[Recette] = [
    Recette("Tomate poelee", [
        IngredientRequis("tomate", [EtatAliment.COUPE, EtatAliment.CUIT])
    ]),

    Recette("Viande cuite", [
        IngredientRequis("viande", [EtatAliment.COUPE, EtatAliment.CUIT])
    ]),

    Recette("Pates nature", [
        IngredientRequis("pate", [EtatAliment.CUIT])
    ]),

    Recette("Salade coupee", [
        IngredientRequis("salade", [EtatAliment.COUPE])
    ]),

    Recette("Salade composee", [
        IngredientRequis("salade", [EtatAliment.COUPE]),
        IngredientRequis("tomate", [EtatAliment.COUPE])
    ]),

    Recette("Pates bolognaises", [
        IngredientRequis("pate",   [EtatAliment.CUIT]),
        IngredientRequis("viande", [EtatAliment.COUPE, EtatAliment.CUIT])
    ]),

    Recette("Sandwich", [
        IngredientRequis("pain",   [EtatAliment.SORTI_DU_BAC]),
        IngredientRequis("viande", [EtatAliment.COUPE, EtatAliment.CUIT]),
        IngredientRequis("salade", [EtatAliment.COUPE])
    ]),

    Recette("Soupe de legumes", [
        IngredientRequis("tomate",     [EtatAliment.COUPE]),
        IngredientRequis("courgette",  [EtatAliment.COUPE]),
        IngredientRequis("aubergine",  [EtatAliment.COUPE, EtatAliment.CUIT])
    ]),

    Recette("Burger complet", [
        IngredientRequis("pain",   [EtatAliment.SORTI_DU_BAC]),
        IngredientRequis("viande", [EtatAliment.COUPE, EtatAliment.CUIT]),
        IngredientRequis("tomate", [EtatAliment.COUPE]),
        IngredientRequis("salade", [EtatAliment.COUPE])
    ]),

    Recette("Omelette", [
        IngredientRequis("oeuf", [EtatAliment.COUPE, EtatAliment.CUIT])
    ]),

    Recette("Ratatouille", [
        IngredientRequis("tomate",     [EtatAliment.COUPE]),
        IngredientRequis("aubergine",  [EtatAliment.COUPE]),
        IngredientRequis("courgette",  [EtatAliment.COUPE]),
    ]),

    Recette("Pates carbonara", [
        IngredientRequis("pate",   [EtatAliment.CUIT]),
        IngredientRequis("viande", [EtatAliment.COUPE, EtatAliment.CUIT]),
        IngredientRequis("oeuf",   [EtatAliment.COUPE])
    ]),

    Recette("Brochette mixte", [
        IngredientRequis("viande",   [EtatAliment.COUPE, EtatAliment.CUIT]),
        IngredientRequis("tomate",   [EtatAliment.COUPE]),
        IngredientRequis("poivron",  [EtatAliment.COUPE])
    ]),

    Recette("Pizza maison", [
        IngredientRequis("pate",    [EtatAliment.CUIT]),
        IngredientRequis("tomate",  [EtatAliment.COUPE]),
        IngredientRequis("viande",  [EtatAliment.COUPE, EtatAliment.CUIT])
    ])
]

def nouvelle_recette() -> Recette:
    return random.choice(RECETTES_POOL)
