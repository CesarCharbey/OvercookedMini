# player.py
import tkinter as tk
from typing import Optional, Iterable, Tuple
from recette import Aliment
from carte import *

class Player:
    def __init__(self, x: int, y: int, couleur: str = "green") -> None:
        self.x = int(x)
        self.y = int(y)
        self.couleur = couleur
        self.item: Optional[Aliment] = None

    def _try_move(self, dx: int, dy: int, carte) -> None:
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < carte.cols and 0 <= ny < carte.rows and not carte.est_bloquant(nx, ny):
            self.x, self.y = nx, ny

    def gauche(self, carte): self._try_move(-1, 0, carte)
    def droite(self, carte): self._try_move( 1, 0, carte)
    def haut(self,   carte): self._try_move( 0,-1, carte)
    def bas(self,    carte): self._try_move( 0, 1, carte)


    def est_adjacent_a(self, positions: Iterable[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
        for (px, py) in positions:
            if abs(px - self.x) + abs(py - self.y) == 1:
                return (px, py)
        return None

    def dessiner(self, canvas: tk.Canvas, carte) -> None:
        carte.dessiner(canvas)
        cw = carte.largeur_px / carte.cols
        ch = carte.hauteur_px / carte.rows
        x1 = self.x * cw; y1 = self.y * ch
        x2 = (self.x + 1) * cw; y2 = (self.y + 1) * ch
        canvas.create_rectangle(x1, y1, x2, y2, outline="black", fill=self.couleur)

        if self.item:
            if self.item.est_perime:
                self.item = None
            else:
                side = min(cw, ch) * 0.35
                ax1 = x2 - side * 0.2
                ay1 = y1 + (ch - side) / 2
                ax2 = ax1 + side
                ay2 = ay1 + side
                canvas.create_rectangle(ax1, ay1, ax2, ay2, outline="black", fill=self.item.couleur_ui())
