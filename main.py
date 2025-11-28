# main.py
import tkinter as tk
from typing import List, Tuple
import time

from end_screen import EndScreen
from carte import Carte
from player import Player
from recette import (
    Aliment, EtatAliment, Recette,
    ALIMENTS_BAC, nouvelle_recette
)
from agent import Agent

grille_J1= [
    [6,6,6,6,6,6,6,6,6,6],
    [6,0,0,3,2,2,0,0,8,6],
    [6,1,0,0,0,0,0,0,8,6],
    [6,1,0,0,0,0,0,0,4,6],
    [6,1,0,0,0,0,0,0,4,6],
    [6,1,0,0,0,0,0,0,4,6],
    [6,0,0,7,7,3,0,0,4,6],
    [6,6,6,6,6,6,6,6,6,6],
]

grille_J2= [
    [6,6,6,6,6,6,6,6,6,6],
    [6,0,0,3,2,2,0,0,8,6],
    [6,1,0,0,0,0,0,0,8,6],
    [6,1,0,0,0,0,0,0,4,6],
    [6,1,0,0,0,0,0,0,4,6],
    [6,1,0,0,0,0,0,0,4,6],
    [6,0,0,7,7,3,0,0,4,6],
    [6,6,6,6,6,6,6,6,6,6],
]

W, H = 600, 600
GAME_DURATION_S = 90
TICK_MS = 100

class Game:
    def __init__(self, root: tk.Tk, grille_data=None, strategie="naive") -> None:
        self.root = root
        self.canvas = tk.Canvas(root, width=W, height=H)
        self.canvas.pack()

        self.carte = Carte(grille_data, largeur=W, hauteur=H)
        self.carte.assigner_bacs(ALIMENTS_BAC)
        self.score = 0
        self.start_time = time.time()
        self.deadline = self.start_time + GAME_DURATION_S
        self.recettes: List[Recette] = [nouvelle_recette() for _ in range(3)]
        self.recettes_livrees = []
        
        self.cuissons: dict[Tuple[int, int], Tuple[Aliment, float, float]] = {}
        self.action_en_cours = None
        self.action_debut = 0.0
        self.action_fin = 0.0

        self.player = Player(2, 2, sprite_path="texture/Player.png")
        self.agent = Agent(self, self.player, strategie)

        self.last_tick = time.time()
        self._refresh()
        self.root.after(TICK_MS, self._tick)

    def get_time(self) -> float:
        """Retourne le temps actuel du jeu (temps réel)."""
        return time.time()

    def trigger_action_bloquante(self, type_action, pos, aliment, duree):
        self.action_en_cours = (type_action, pos, aliment)
        self.action_debut = time.time()
        self.action_fin = self.action_debut + duree

    def start_cooking(self, pos, aliment, duree):
        start = time.time()
        self.cuissons[pos] = (aliment, start, start + duree)

    def deliver_recipe(self, index, recette):
        self.score += recette.difficulte_reelle
        self.recettes_livrees.append((recette.nom, recette.complexite))
        self.recettes.pop(index)
        self.recettes.append(nouvelle_recette())

    def _tick(self):
        now = time.time()
        dt = now - self.last_tick
        self.last_tick = now

        if now >= self.deadline: return

        self._update_physics()

        if self.action_en_cours:
            type_action, _, aliment = self.action_en_cours
            if now >= self.action_fin:
                if type_action == "DECOUPE":
                    aliment.transformer(EtatAliment.COUPE)
                self.action_en_cours = None
                self.agent._mark_progress()
            else:
                self._refresh()
                self.root.after(TICK_MS, self._tick)
                return

        self.agent.tick()
        self.player.update(dt)

        self._refresh()
        self.root.after(TICK_MS, self._tick)

    def _update_physics(self):
        """Mise à jour (seulement fin de cuisson)"""
        now = time.time()
        for pos, (alim, _, tfin) in list(self.cuissons.items()):
            # Plus de gestion péremption, juste transformation si fini
            if now >= tfin and alim.etat != EtatAliment.CUIT:
                alim.transformer(EtatAliment.CUIT)

    def _refresh(self):
        self.player.dessiner(self.canvas, self.carte)
        self._dessiner_progress_stations()
        self._dessiner_debug_path()
        self._dessiner_hud()

    def _dessiner_progress_stations(self):
        def draw_bar(sx, sy, t0, tfin, kind: str):
            now = time.time()
            total = tfin - t0
            if total <= 0: return
            ratio = max(0.0, min(1.0, (now - t0) / total))
            tile = min(self.carte.largeur_px // self.carte.cols, self.carte.hauteur_px // self.carte.rows)
            cw = ch = int(tile)
            x1, y1 = sx * cw, sy * ch
            bx1, bx2 = x1 + 4, x1 + cw - 4
            by1, by2 = y1 + 4, y1 + 10
            
            self.canvas.create_rectangle(bx1, by1, bx2, by2, fill="#222", outline="black")
            color = "#ffb347" if kind == "DECOUPE" else "#ff6961"
            
            fx2 = bx1 + ratio * (bx2 - bx1)
            self.canvas.create_rectangle(bx1, by1, fx2, by2, fill=color, outline="")

        if self.action_en_cours:
            type_act, pos, _ = self.action_en_cours
            if type_act == "DECOUPE" and pos:
                draw_bar(pos[0], pos[1], self.action_debut, self.action_fin, "DECOUPE")
        
        for (sx, sy), (_, t0, tfin) in self.cuissons.items():
            draw_bar(sx, sy, t0, tfin, "CUISSON")

    def _dessiner_debug_path(self):
        if not self.agent.current_path: return
        tile = min(self.carte.largeur_px // self.carte.cols, self.carte.hauteur_px // self.carte.rows)
        cw = ch = int(tile)
        nx, ny = self.agent.current_path[0]
        self.canvas.create_rectangle(nx*cw+2, ny*ch+2, (nx+1)*cw-2, (ny+1)*ch-2, outline="cyan", width=3)

    def _dessiner_hud(self):
        now = time.time()
        remaining = max(0, int(self.deadline - now))
        info = f"⏱ {remaining//60:02d}:{remaining%60:02d}    ★ Score: {self.score}"
        
        self.canvas.delete("hud") 
        
        TOP_H = 28
        self.canvas.create_rectangle(0, 0, W, TOP_H, fill="#222", outline="")
        self.canvas.create_text(8, TOP_H // 2, text=info, fill="white", anchor="w", font=("Arial", 12, "bold"))

        tile = min(self.carte.largeur_px // self.carte.cols, self.carte.hauteur_px // self.carte.rows)
        panel_y0 = max(TOP_H + 2, self.carte.rows * tile)
        self.canvas.create_rectangle(0, panel_y0, W, H, fill="#333", outline="")
        SPLIT_X = int(W * 0.55)
        self.canvas.create_line(SPLIT_X, panel_y0, SPLIT_X, H, fill="#555")

        y = panel_y0 + 4
        for i, r in enumerate(self.recettes):
            need = " + ".join(f"{req.nom}" for req in r.requis)
            self.canvas.create_text(8, y, text=f"{i+1}. {r.nom} [{need}]", fill="white", anchor="nw", font=("Arial", 10), width=SPLIT_X-16)
            y += 34

        dx = SPLIT_X + 8
        dy = panel_y0 + 4
        lines = [
            f"Cible : {self.agent.bot_recette.nom if self.agent.bot_recette else 'Aucune'}",
            f"Action : {'Occupé' if self.action_en_cours else 'Libre'}",
            f"Chemin : {len(self.agent.current_path)} pas"
        ]
        for l in lines:
            self.canvas.create_text(dx, dy, text=l, fill="white", anchor="nw", font=("Arial", 10))
            dy += 18


def main(strategie_J1="naive", strategie_J2="naive"):
    root = tk.Tk()
    root.title("OverCooked Mini 1vs1 🧑‍🍳")
    root.resizable(False, False)

    frame = tk.Frame(root)
    frame.pack()

    f1 = tk.Frame(frame); f1.pack(side="left")
    tk.Label(f1, text="Joueur 1", font=("Arial", 14)).pack()
    g1 = Game(f1, grille_J1, strategie=strategie_J1)

    f2 = tk.Frame(frame); f2.pack(side="left")
    tk.Label(f2, text="Joueur 2", font=("Arial", 14)).pack()
    g2 = Game(f2, grille_J2, strategie=strategie_J2)

    def check_end():
        now = time.time()
        if now >= g1.deadline:
            EndScreen(root, {"score": g1.score, "recettes": g1.recettes_livrees},
                            {"score": g2.score, "recettes": g2.recettes_livrees})
        else:
            root.after(200, check_end)
    check_end()
    root.mainloop()

if __name__ == "__main__":
    main()