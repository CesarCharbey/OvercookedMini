import tkinter as tk
from typing import Optional, Iterable, Tuple
from PIL import Image, ImageTk
from recette import Aliment

TILE_SIZE = 32
SPRITE_SCALE = 1.7  # 1.0 = taille de la tuile, 1.3 = un peu plus grand


class Player:
    def __init__(self, x: int, y: int, couleur: str = "green", sprite_path: Optional[str] = None, label: str = "") -> None:
        self.x = int(x)
        self.y = int(y)
        self.couleur = couleur
        self.item: Optional[Aliment] = None
        self.label = label # P1, P2, etc.

        self.anim_x = float(x)
        self.anim_y = float(y)
        self.anim_speed = 0.1
        self.moving = False
        self.direction = "down"
        self.frame_index = 0

        self.has_sprite = sprite_path is not None
        if self.has_sprite:
            self._load_sprite_sheet(sprite_path)
        else:
            self.frames = None

    def _load_sprite_sheet(self, path: str):
        img = Image.open(path)
        directions = ["down", "left", "right", "up"]
        self.frames = {d: [] for d in directions}
        for row, d in enumerate(directions):
            for col in range(4):
                x0 = col * TILE_SIZE
                y0 = row * TILE_SIZE
                sub = img.crop((x0, y0, x0 + TILE_SIZE, y0 + TILE_SIZE))

                target = int(TILE_SIZE * SPRITE_SCALE)   # <<< ici
                sub = sub.resize((target, target), Image.NEAREST)

                self.frames[d].append(ImageTk.PhotoImage(sub))
        self.current_image = self.frames["down"][0]


    def _next_frame(self):
        if not self.has_sprite: return
        self.frame_index = (self.frame_index + 1) % 3
        self.current_image = self.frames[self.direction][self.frame_index]

    def _try_move(self, dx: int, dy: int, carte) -> None:
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
        if self.moving:
            diff_x = self.x - self.anim_x
            diff_y = self.y - self.anim_y
            self.anim_x += diff_x * self.anim_speed * (dt * 60)
            self.anim_y += diff_y * self.anim_speed * (dt * 60)
            if abs(diff_x) < 0.05 and abs(diff_y) < 0.05:
                self.anim_x = self.x
                self.anim_y = self.y
                self.moving = False

    def gauche(self, carte): self._try_move(-1, 0, carte)
    def droite(self, carte): self._try_move(1, 0, carte)
    def haut(self, carte): self._try_move(0, -1, carte)
    def bas(self, carte): self._try_move(0, 1, carte)

    def est_adjacent_a(self, positions: Iterable[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
        for (px, py) in positions:
            if abs(px - self.x) + abs(py - self.y) == 1:
                return (px, py)
        return None

    def dessiner_personnage(self, canvas: tk.Canvas, carte) -> None:
        # Note: on ne dessine plus la carte ici pour ne pas la redessiner 4 fois
        tile = min(carte.largeur_px // carte.cols, carte.hauteur_px // carte.rows)
        cw = ch = int(tile)

        x1 = self.anim_x * cw
        y1 = self.anim_y * ch

        # Sprite
        if self.has_sprite:
            canvas.create_image(x1, y1, image=self.current_image, anchor="nw")
        else:
            x2 = (self.x + 1) * cw
            y2 = (self.y + 1) * ch
            canvas.create_rectangle(x1, y1, x2, y2, outline="black", fill=self.couleur)

        # Indicateur P1/P2
        if self.label:
            canvas.create_text(x1 + cw/2, y1 - 5, text=self.label, fill="white", font=("Arial", 8, "bold"))

        # Aliment dans les mains
        if self.item:
            photo = self.item._image_cache.get(self.item.etat)
            if photo is None:
                path = self.item.get_texture_path()
                if path:
                    try:
                        img = Image.open(path).convert("RGBA")
                        target_size = int(cw * 0.4)
                        img = img.resize((target_size, target_size), Image.NEAREST)
                        photo = ImageTk.PhotoImage(img)
                        self.item._image_cache[self.item.etat] = photo
                    except: pass
            
            item_x = x1 + cw * 0.75
            item_y = y1 + ch * 0.6

            if photo:
                canvas.create_image(item_x, item_y, image=photo, anchor="center")
            else:
                side = min(cw, ch) * 0.35
                ax1 = x1 + cw - side * 1.2
                ay1 = y1 + (ch - side) / 2
                ax2 = ax1 + side
                ay2 = ay1 + side
                canvas.create_rectangle(ax1, ay1, ax2, ay2, outline="black", fill=self.item.couleur_ui())