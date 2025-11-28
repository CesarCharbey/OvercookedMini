from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Tuple
import random

# ---------------------------------------------------
# ÉTATS DES ALIMENTS
# ---------------------------------------------------
class EtatAliment(Enum):
    SORTI_DU_BAC = auto()
    COUPE = auto()
    CUIT = auto()

# ---------------------------------------------------
# MAPPING TEXTURES (Nouveau)
# ---------------------------------------------------
# Associe (nom_aliment, etat) -> nom_fichier_png
# Basé sur ta liste de fichiers fournie.
TEXTURES_ALIMENTS = {
    # Tomate
    ("tomate", EtatAliment.SORTI_DU_BAC): "texture/FoodAssets/Tomato_Fresh.png",
    ("tomate", EtatAliment.COUPE):        "texture/FoodAssets/Tomato_Cut.png", 
    ("tomate", EtatAliment.CUIT):         "texture/FoodAssets/Tomato_Cooked.png",

    # Salade
    ("salade", EtatAliment.SORTI_DU_BAC): "texture/FoodAssets/Lettuce_Fresh.png",
    ("salade", EtatAliment.COUPE):        "texture/FoodAssets/Lettuce_Cut.png",

    # Aubergine
    ("aubergine", EtatAliment.SORTI_DU_BAC): "texture/FoodAssets/Eggplant_Fresh.png",
    ("aubergine", EtatAliment.COUPE):        "texture/FoodAssets/Eggplant_Cut.png",
    ("aubergine", EtatAliment.CUIT):         "texture/FoodAssets/Eggplant_Cooked.png",

    # Courgette
    ("courgette", EtatAliment.SORTI_DU_BAC): "texture/FoodAssets/Zucchini_Fresh.png",
    ("courgette", EtatAliment.COUPE):        "texture/FoodAssets/Zucchini_Cut.png",
    ("courgette", EtatAliment.CUIT):         "texture/FoodAssets/Zucchini_Cooked.png",

    # Poivron
    ("poivron", EtatAliment.SORTI_DU_BAC): "texture/FoodAssets/Pepper_Fresh.png",
    ("poivron", EtatAliment.COUPE):        "texture/FoodAssets/Pepper_Cut.png",
    ("poivron", EtatAliment.CUIT):         "texture/FoodAssets/Pepper_Cooked.png",

    # Viande
    ("viande", EtatAliment.SORTI_DU_BAC): "texture/FoodAssets/Meat_Fresh.png",
    ("viande", EtatAliment.COUPE):        "texture/FoodAssets/Meat_Cut.png",
    ("viande", EtatAliment.CUIT):         "texture/FoodAssets/Meat_Cooked.png",

    # Oeuf
    # Note: Si tu as une texture pour l'oeuf frais, ajoute-la ici. Sinon fallback couleur.
    # Je mappe SORTI_DU_BAC vers Egg_Cut si jamais tu n'as pas Egg_Fresh, sinon laisse vide ou mets le bon nom.
    ("oeuf", EtatAliment.SORTI_DU_BAC):   "texture/FoodAssets/Egg_Fresh.png", # Hypothèse
    ("oeuf", EtatAliment.COUPE):          "texture/FoodAssets/Egg_Cut.png",
    ("oeuf", EtatAliment.CUIT):           "texture/FoodAssets/Egg_Cooked.png",

    # Pain
    ("pain", EtatAliment.SORTI_DU_BAC): "texture/FoodAssets/Bread_Fresh.png",
    ("pain", EtatAliment.COUPE):        "texture/FoodAssets/Bread_Cut.png",

    # Pates
    ("pate", EtatAliment.SORTI_DU_BAC): "texture/FoodAssets/Pasta_Fresh.png",
    ("pate", EtatAliment.CUIT):         "texture/FoodAssets/Pasta_Cooked.png",
}

# ---------------------------------------------------
# DURÉES
# ---------------------------------------------------
TEMPS_COUPE = {
    "tomate": 1.0, "salade": 0.8, "aubergine": 1.5, "courgette": 1.2,
    "poivron": 1.0, "viande": 2.0, "oeuf": 0.8, "pain": 0.0,
}

TEMPS_CUISSON = {
    "tomate": 2.0, "aubergine": 3.0, "courgette": 2.0, "poivron": 2.5,
    "viande": 4.0, "oeuf": 1.5, "pate": 2.5,
}

# ---------------------------------------------------
# ALIMENT
# ---------------------------------------------------
@dataclass
class Aliment:
    nom: str
    etat: EtatAliment
    
    # Cache pour stocker l'image Tkinter chargée et éviter de recharger le fichier PNG à chaque frame
    # field(init=False) signifie qu'on ne le passe pas dans le constructeur
    _image_cache: Dict[EtatAliment, object] = field(default_factory=dict, init=False, repr=False, compare=False)

    def transformer(self, nouvel_etat: EtatAliment) -> None:
        self.etat = nouvel_etat

    def get_texture_path(self) -> Optional[str]:
        return TEXTURES_ALIMENTS.get((self.nom, self.etat))

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

    @property
    def complexite(self) -> int:
        return sum(len(req.etats) for req in self.requis)

    @property
    def interactions(self) -> int:
        total = 0
        for req in self.requis:
            total += 1 + len(req.etats) + 1
        return total

    @property
    def temps_estime(self) -> float:
        total = 0.0
        for req in self.requis:
            if EtatAliment.COUPE in req.etats: total += TEMPS_COUPE.get(req.nom, 1.0)
            if EtatAliment.CUIT in req.etats: total += TEMPS_CUISSON.get(req.nom, 2.0)
        total += len(self.requis) * 0.5
        return total

    @property
    def difficulte_reelle(self) -> float:
        return self.complexite * self.interactions

# ---------------------------------------------------
# INVENTAIRE
# ---------------------------------------------------
LEGUMES_NOMS = ["tomate", "salade", "aubergine", "courgette", "poivron"]

ALIMENTS_BAC = [
    ("viande", 0), ("pate", 0), ("oeuf", 0), ("pain", 0), ("legume", 0),
]

def prendre_au_bac(nom: str) -> Aliment:
    if nom == "legume":
        raise RuntimeError("Utiliser prendre_legume()")
    return Aliment(nom=nom, etat=EtatAliment.SORTI_DU_BAC)

def prendre_legume(nom_legume: str) -> Aliment:
    return Aliment(nom=nom_legume, etat=EtatAliment.SORTI_DU_BAC)


# ---------------------------------------------------
# RECETTES
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

    Recette("Pates aux legumes", [
        IngredientRequis("pate",    [EtatAliment.CUIT]),
        IngredientRequis("tomate",  [EtatAliment.COUPE]),
        IngredientRequis("courgette",  [EtatAliment.COUPE, EtatAliment.CUIT])
    ])
]


def nouvelle_recette() -> Recette:
    return random.choice(RECETTES_POOL)
