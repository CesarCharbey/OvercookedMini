import tkinter as tk
from typing import Optional, Iterable, Tuple
from PIL import Image, ImageTk
from recette import Aliment

TILE_SIZE = 32  # chaque frame du sprite fait 32x32 pixels

class Player:
    def __init__(self, x: int, y: int, couleur: str = "green", sprite_path: Optional[str] = None) -> None:
        self.x = int(x)
        self.y = int(y)
        self.couleur = couleur
        self.item: Optional[Aliment] = None

        self.anim_x = float(x)
        self.anim_y = float(y)
        self.anim_speed = 0.1  # vitesse d’animation (plus petit = plus lent)
        self.moving = False
        # Animation
        self.direction = "down"
        self.frame_index = 0

        # Spritesheet optionnelle
        self.has_sprite = sprite_path is not None
        if self.has_sprite:
            self._load_sprite_sheet(sprite_path)
        else:
            self.frames = None

    def _load_sprite_sheet(self, path: str):
        """Découpe une spriteshee 3x4 de 32x32 en frames Tkinter utilisables (agrandies x2)."""
        img = Image.open(path)
        directions = ["down", "left", "right", "up"]
        self.frames = {d: [] for d in directions}

        for row, d in enumerate(directions):
            for col in range(4):
                x0 = col * TILE_SIZE
                y0 = row * TILE_SIZE
                sub = img.crop((x0, y0, x0 + TILE_SIZE, y0 + TILE_SIZE))
                # 🔹 Double la taille
                sub = sub.resize((TILE_SIZE * 3, TILE_SIZE *3), Image.NEAREST)
                self.frames[d].append(ImageTk.PhotoImage(sub))

        self.current_image = self.frames["down"][0]

    def _next_frame(self):
        if not self.has_sprite:
            return
        self.frame_index = (self.frame_index + 1) % 3
        self.current_image = self.frames[self.direction][self.frame_index]

    # ----------------- Déplacement -----------------
    def _try_move(self, dx: int, dy: int, carte) -> None:
        """Déplace le joueur avec animation fluide."""
        nx, ny = self.x + dx, self.y + dy
        if 0 <= nx < carte.cols and 0 <= ny < carte.rows and not carte.est_bloquant(nx, ny):
            self.x, self.y = nx, ny
            self.target_x = nx
            self.target_y = ny
            self.moving = True
            if dx == 1: self.direction = "right"
            elif dx == -1: self.direction = "left"
            elif dy == 1: self.direction = "down"
            elif dy == -1: self.direction = "up"
            self._next_frame()

    def update(self, dt: float):
        """Met à jour la position animée (interpolation vers la case cible)."""
        if self.moving:
            # Lisse le mouvement
            diff_x = self.x - self.anim_x
            diff_y = self.y - self.anim_y

            self.anim_x += diff_x * self.anim_speed * (dt * 60)
            self.anim_y += diff_y * self.anim_speed * (dt * 60)

            # Si très proche de la destination → arrêt
            if abs(diff_x) < 0.05 and abs(diff_y) < 0.05:
                self.anim_x = self.x
                self.anim_y = self.y
                self.moving = False


    def gauche(self, carte): self._try_move(-1, 0, carte)
    def droite(self, carte): self._try_move(1, 0, carte)
    def haut(self, carte): self._try_move(0, -1, carte)
    def bas(self, carte): self._try_move(0, 1, carte)

    # ----------------- Adjacence -----------------
    def est_adjacent_a(self, positions: Iterable[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
        for (px, py) in positions:
            if abs(px - self.x) + abs(py - self.y) == 1:
                return (px, py)
        return None

    # ----------------- Dessin -----------------
    def dessiner(self, canvas: tk.Canvas, carte) -> None:
        carte.dessiner(canvas)
        cw = carte.largeur_px / carte.cols
        ch = carte.hauteur_px / carte.rows
        x1 = self.anim_x * cw
        y1 = self.anim_y * ch


        if self.has_sprite:
            canvas.create_image(x1, y1, image=self.current_image, anchor="nw")
        else:
            # Fallback si pas d’image
            x2 = (self.x + 1) * cw
            y2 = (self.y + 1) * ch
            canvas.create_rectangle(x1, y1, x2, y2, outline="black", fill=self.couleur)

        if self.item:
            if self.item.est_perime:
                self.item = None
            else:
                side = min(cw, ch) * 0.35
                ax1 = x1 + cw - side * 1.2
                ay1 = y1 + (ch - side) / 2
                ax2 = ax1 + side
                ay2 = ay1 + side
                canvas.create_rectangle(ax1, ay1, ax2, ay2, outline="black", fill=self.item.couleur_ui())
