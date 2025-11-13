# carte.py
from typing import List, Sequence, Tuple, Dict
import tkinter as tk

# Codes tuiles
SOL, BAC, FOUR, DECOUPE, SERVICE, JOUEUR, MUR, POELE, ASSEMBLAGE = 0, 1, 2, 3, 4, 5, 6, 7, 8
BLOQUANTS = {MUR, BAC, FOUR, DECOUPE, SERVICE, POELE, ASSEMBLAGE}

class Carte:
    """Carte grille : dessine, expose les positions des stations et gère libellés/assignations de bacs/assemblage."""
    def __init__(self, grille: Sequence[Sequence[int]], largeur: int = 600, hauteur: int = 600) -> None:
        if not grille or not all(isinstance(row, (list, tuple)) for row in grille):
            raise ValueError("grille doit être une liste de listes.")
        w = len(grille[0])
        if any(len(row) != w for row in grille):
            raise ValueError("toutes les lignes doivent avoir la même longueur.")
        self.grille: List[List[int]] = [list(r) for r in grille]
        self.largeur_px = int(largeur)
        self.hauteur_px = int(hauteur)

        # positions
        self.pos_bacs: List[Tuple[int, int]] = []
        self.pos_decoupes: List[Tuple[int, int]] = []
        self.pos_services: List[Tuple[int, int]] = []
        self.pos_poeles: List[Tuple[int, int]] = []
        self.pos_fours: List[Tuple[int, int]] = []
        self.pos_assemblages: List[Tuple[int, int]] = []

        # config bacs: (x,y) -> (nom, vitesse)
        self.bacs_config: Dict[Tuple[int, int], Tuple[str, float]] = {}
        # stock assemblage: (x,y) -> liste d'objets (Aliment ou plat final)
        self.assemblage_stock: Dict[Tuple[int, int], List[object]] = {}

        self._indexer_stations()

        self.couleurs = {
            SOL:      "burlywood",
            BAC:      "blue",
            FOUR:     "red",
            DECOUPE:  "yellow",
            SERVICE:  "gray",
            JOUEUR:   "green",
            MUR:      "black",
            POELE:    "orange",
            ASSEMBLAGE: "#8bd3dd",
        }

        self.labels_base = {
            BAC: "Bac",
            FOUR: "Four",
            DECOUPE: "Découpe",
            SERVICE: "Service",
            POELE: "Poêle",
            ASSEMBLAGE: "Assemblage",
            JOUEUR: "Joueur",
        }

    def _indexer_stations(self) -> None:
        self.pos_bacs.clear(); self.pos_decoupes.clear(); self.pos_services.clear()
        self.pos_poeles.clear(); self.pos_fours.clear(); self.pos_assemblages.clear()
        for y, row in enumerate(self.grille):
            for x, code in enumerate(row):
                if code == BAC: self.pos_bacs.append((x, y))
                elif code == DECOUPE: self.pos_decoupes.append((x, y))
                elif code == SERVICE: self.pos_services.append((x, y))
                elif code == POELE: self.pos_poeles.append((x, y))
                elif code == FOUR: self.pos_fours.append((x, y))
                elif code == ASSEMBLAGE:
                    self.pos_assemblages.append((x, y))
                    self.assemblage_stock.setdefault((x, y), [])

    @property
    def rows(self) -> int: return len(self.grille)
    @property
    def cols(self) -> int: return len(self.grille[0])

    def assigner_bacs(self, items: List[Tuple[str, float]]) -> None:
        """
        Assigne chaque bac à un aliment (nom, vitesse).
        Si moins de bacs que d'aliments, on convertit des cases SOL en BAC (de gauche à droite, haut -> bas)
        jusqu'à en avoir au moins un par aliment.
        """
        # 1) créer des bacs supplémentaires si nécessaire
        manquants = max(0, len(items) - len(self.pos_bacs))
        if manquants > 0:
            for y in range(self.rows):
                for x in range(self.cols):
                    if manquants == 0: break
                    if self.grille[y][x] == SOL:
                        self.grille[y][x] = BAC
                        self.pos_bacs.append((x, y))
                        manquants -= 1
                if manquants == 0: break
            # reindex si on a modifié la grille
            self._indexer_stations()

        # 2) associer au moins un bac par aliment (et boucler si surplus de bacs)
        self.bacs_config.clear()
        for i, pos in enumerate(self.pos_bacs):
            nom, v = items[i % len(items)]
            self.bacs_config[pos] = (nom, v)

    def est_mur(self, x: int, y: int) -> bool:
        if 0 <= y < self.rows and 0 <= x < self.cols:
            return self.grille[y][x] == MUR
        return True

    def est_bloquant(self, x: int, y: int) -> bool:
        """Tout atelier + murs sont bloquants pour le déplacement."""
        if 0 <= y < self.rows and 0 <= x < self.cols:
            return self.grille[y][x] in BLOQUANTS
        return True

    def dessiner(self, canvas: tk.Canvas) -> None:
        """Dessine la grille et les labels. Pour ASSEMBLAGE, affiche le contenu."""
        canvas.config(width=self.largeur_px, height=self.hauteur_px)
        canvas.delete("all")
        cw = self.largeur_px / self.cols
        ch = self.hauteur_px / self.rows

        for y in range(self.rows):
            for x in range(self.cols):
                code = self.grille[y][x]
                fill = self.couleurs.get(code, "white")
                x1, y1 = x * cw, y * ch
                x2, y2 = (x + 1) * cw, (y + 1) * ch
                canvas.create_rectangle(x1, y1, x2, y2, outline="black", fill=fill)

                # Labels (sauf murs/sol)
                if code in (MUR, SOL):
                    continue

                # label de base
                label = self.labels_base.get(code, "")

                # Bacs : afficher l'aliment assigné
                if code == BAC:
                    nom = self.bacs_config.get((x, y), ("?", 0.0))[0]
                    label = f"Bac\n{nom}"

                # Assemblage : afficher contenu (noms)
                if code == ASSEMBLAGE:
                    stock = self.assemblage_stock.get((x, y), [])
                    if stock:
                        noms = " + ".join(getattr(a, "nom", str(a)) for a in stock)
                        label = f"Assemblage\n{noms}"

                canvas.create_text(
                    (x1 + x2) / 2, (y1 + y2) / 2,
                    text=label, fill="black", font=("Arial", 9), justify="center"
                )
