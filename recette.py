from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Tuple
import random


# ---------------------------------------------------
# ÉTATS DES ALIMENTS
# ---------------------------------------------------
class EtatAliment(Enum):
    SORTI_DU_BAC = auto()
    COUPE = auto()
    CUIT = auto()


# ---------------------------------------------------
# DURÉES DE PRÉPARATION PAR ALIMENT
# (nouveau : temps de coupe & cuisson)
# ---------------------------------------------------
TEMPS_COUPE = {
    "tomate": 1.0,
    "salade": 0.8,
    "aubergine": 1.5,
    "courgette": 1.2,
    "poivron": 1.0,
    "viande": 2.0,
    "oeuf": 0.8,
    "pain": 0.0,   # se coupe pas
}

TEMPS_CUISSON = {
    "tomate": 2.0,
    "aubergine": 3.0,
    "courgette": 2.0,
    "poivron": 2.5,
    "viande": 4.0,
    "oeuf": 1.5,
    "pate": 2.5,
}


# ---------------------------------------------------
# ALIMENT
# ---------------------------------------------------
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


# ---------------------------------------------------
# INGREDIENT REQUIS
# ---------------------------------------------------
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


# ---------------------------------------------------
# RECETTE
# ---------------------------------------------------
@dataclass
class Recette:
    nom: str
    requis: List[IngredientRequis]

    # === Complexité STRUCTURELLE : nombre d’étapes ===
    @property
    def complexite(self) -> int:
        return sum(len(req.etats) for req in self.requis)

    # === Interactions réelles : prise + étapes + assemblage ===
    @property
    def interactions(self) -> int:
        total = 0
        for req in self.requis:
            total += 1                  # prise au bac
            total += len(req.etats)     # étapes
            total += 1                  # assemblage
        return total

    # === Temps total estimé (nouveau) ===
    @property
    def temps_estime(self) -> float:
        total = 0.0
        for req in self.requis:
            # coupe
            if EtatAliment.COUPE in req.etats:
                total += TEMPS_COUPE.get(req.nom, 1.0)
            # cuisson
            if EtatAliment.CUIT in req.etats:
                total += TEMPS_CUISSON.get(req.nom, 2.0)

        # petit bonus pour assemblage
        total += len(self.requis) * 0.5
        return total

    # === Difficulté réelle (pour scoring) ===
    @property
    def difficulte_reelle(self) -> float:
        return self.complexite * self.interactions


# ---------------------------------------------------
# INVENTAIRE DES ALIMENTS / BACS
# ---------------------------------------------------

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

    # Bac unique légumes
    ("legume", 0.0006),
]


def prendre_au_bac(nom: str, vitesse: float) -> Aliment:
    if nom == "legume":
        raise RuntimeError("Appel incorrect : utiliser prendre_legume()")
    return Aliment(nom=nom, etat=EtatAliment.SORTI_DU_BAC, vitesse_peremption=vitesse)


def prendre_legume(nom_legume: str) -> Aliment:
    return Aliment(
        nom=nom_legume,
        etat=EtatAliment.SORTI_DU_BAC,
        vitesse_peremption=LEGUMES[nom_legume]
    )


# ---------------------------------------------------
# RECETTES
# (inchangées sauf que la difficulté/temps s'adaptent automatiquement)
# ---------------------------------------------------

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

    Recette("Caviar d'aubergine", [
        IngredientRequis("aubergine", [EtatAliment.COUPE, EtatAliment.CUIT])
    ]),

    Recette("Poivron rôti", [
        IngredientRequis("poivron", [EtatAliment.COUPE, EtatAliment.CUIT])
    ]),

    Recette("Salade composee", [
        IngredientRequis("salade", [EtatAliment.COUPE]),
        IngredientRequis("tomate", [EtatAliment.COUPE])
    ]),

    Recette("Pates bolognaises", [
        IngredientRequis("pate",   [EtatAliment.CUIT]),
        IngredientRequis("viande", [EtatAliment.COUPE, EtatAliment.CUIT])
    ]),

    Recette("Tomate farcie", [
        IngredientRequis("tomate", [EtatAliment.COUPE, EtatAliment.CUIT]),
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
