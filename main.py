import tkinter as tk
from typing import List, Tuple, Dict
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
        
        # --- GESTION MULTI-JOUEURS ---
        # Au lieu d'un seul tuple, on stocke les actions par agent : { agent_instance: (type, pos, alim, deb, fin) }
        self.actions_en_cours: Dict[Agent, Tuple[str, Tuple[int,int], Aliment, float, float]] = {}

        # On crée 2 joueurs à des positions différentes pour ne pas qu'ils se bloquent au spawn
        # P1 à (2,2), P2 à (5,2)
        self.players = [
            Player(2, 2, sprite_path="texture/Player.png", label="P1"),
            Player(5, 2, sprite_path="texture/Player.png", label="P2")
        ]
        
        # On crée 2 agents, chacun assigné à un joueur et avec un ID différent
        self.agents = [
            Agent(self, self.players[0], strategie, agent_id=0),
            Agent(self, self.players[1], strategie, agent_id=1)
        ]

        self.last_tick = time.time()
        self._refresh()
        self.root.after(TICK_MS, self._tick)

    def get_time(self) -> float:
        return time.time()

    def trigger_action_bloquante(self, agent: Agent, type_action, pos, aliment, duree):
        """L'agent signale qu'il commence une action (ex: découpe)."""
        now = self.get_time()
        # On stocke l'action liée spécifiquement à CET agent
        self.actions_en_cours[agent] = (type_action, pos, aliment, now, now + duree)

    def start_cooking(self, pos, aliment, duree):
        start = self.get_time()
        self.cuissons[pos] = (aliment, start, start + duree)

    def deliver_recipe(self, index, recette):
        self.score += recette.difficulte_reelle
        self.recettes_livrees.append((recette.nom, recette.complexite))
        # On remplace la recette livrée par une nouvelle
        self.recettes.pop(index)
        self.recettes.append(nouvelle_recette())

    def _tick(self):
        now = self.get_time()
        dt = now - self.last_tick
        self.last_tick = now

        if now >= self.deadline: return

        self._update_physics()

        # 1. GESTION DES ACTIONS BLOQUANTES (PAR AGENT)
        agents_occupes = set()
        
        # On itère sur une copie des clés car on peut supprimer des éléments pendant la boucle
        for agent in list(self.actions_en_cours.keys()):
            type_action, _, aliment, _, t_fin = self.actions_en_cours[agent]
            
            if now >= t_fin:
                # Action terminée
                if type_action == "DECOUPE":
                    aliment.transformer(EtatAliment.COUPE)
                del self.actions_en_cours[agent]
                agent._mark_progress() # Réveille l'agent
            else:
                # Action en cours -> l'agent est occupé
                agents_occupes.add(agent)

        # 2. UPDATE DES AGENTS (Ceux qui ne travaillent pas)
        for agent in self.agents:
            if agent not in agents_occupes:
                agent.tick()

        # 3. UPDATE DES JOUEURS (Animation)
        for p in self.players:
            p.update(dt)

        self._refresh()
        self.root.after(TICK_MS, self._tick)

    def _update_physics(self):
        now = self.get_time()
        for pos, (alim, _, tfin) in list(self.cuissons.items()):
            if now >= tfin and alim.etat != EtatAliment.CUIT:
                alim.transformer(EtatAliment.CUIT)

    def _refresh(self):
        # On redessine tout
        self.carte.dessiner(self.canvas) # Dessine le sol et les stations
        
        # Dessine TOUS les joueurs
        for p in self.players:
            p.dessiner_personnage(self.canvas, self.carte)
            
        self._dessiner_progress_stations()
        self._dessiner_debug_path()
        self._dessiner_hud()

    def _dessiner_progress_stations(self):
        now = self.get_time()
        def draw_bar(sx, sy, t0, tfin, kind: str):
            total = tfin - t0
            if total <= 0: return
            ratio = max(0.0, min(1.0, (now - t0) / total))
            tile = min(self.carte.largeur_px // self.carte.cols, self.carte.hauteur_px // self.carte.rows)
            cw = ch = int(tile)
            x1, y1 = sx * cw, sy * ch
            
            # Barre de progression
            bx1, bx2 = x1 + 4, x1 + cw - 4
            by1, by2 = y1 + 4, y1 + 10
            
            self.canvas.create_rectangle(bx1, by1, bx2, by2, fill="#222", outline="black")
            color = "#ffb347" if kind == "DECOUPE" else "#ff6961"
            fx2 = bx1 + ratio * (bx2 - bx1)
            self.canvas.create_rectangle(bx1, by1, fx2, by2, fill=color, outline="")

        # Barres pour les actions de découpe de CHAQUE agent
        for agent, (type_act, pos, _, t_deb, t_fin) in self.actions_en_cours.items():
            if type_act == "DECOUPE" and pos:
                draw_bar(pos[0], pos[1], t_deb, t_fin, "DECOUPE")
        
        # Barres pour les cuissons (fours/poêles)
        for (sx, sy), (_, t0, tfin) in self.cuissons.items():
            draw_bar(sx, sy, t0, tfin, "CUISSON")

    def _dessiner_debug_path(self):
        # Dessine le chemin de chaque agent avec une couleur différente
        colors = ["cyan", "magenta"]
        tile = min(self.carte.largeur_px // self.carte.cols, self.carte.hauteur_px // self.carte.rows)
        cw = ch = int(tile)
        
        for i, agent in enumerate(self.agents):
            if not agent.current_path: continue
            nx, ny = agent.current_path[0]
            col = colors[i % len(colors)]
            # Petit décalage pour voir si les chemins se superposent
            margin = 2 + (i * 2)
            self.canvas.create_rectangle(
                nx*cw+margin, ny*ch+margin, 
                (nx+1)*cw-margin, (ny+1)*ch-margin, 
                outline=col, width=2
            )

    def _dessiner_hud(self):
        now = self.get_time()
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

        # Debug IA
        dx = SPLIT_X + 8
        dy = panel_y0 + 4
        for i, agent in enumerate(self.agents):
            status = "Occupé" if agent in self.actions_en_cours else "Libre"
            recette_nom = agent.bot_recette.nom if agent.bot_recette else '...'
            txt = f"J{i+1}: {recette_nom} ({status})"
            self.canvas.create_text(dx, dy, text=txt, fill="white", anchor="nw", font=("Arial", 9))
            dy += 18


def main(strategie_J1="naive", strategie_J2="naive"):
    root = tk.Tk()
    root.title("OverCooked Mini 2vs2 (Tag Team) 🧑‍🍳🧑‍🍳")
    root.resizable(False, False)

    frame = tk.Frame(root)
    frame.pack()

    # Équipe 1
    f1 = tk.Frame(frame); f1.pack(side="left")
    tk.Label(f1, text="Équipe 1 (2 Joueurs)", font=("Arial", 14)).pack()
    g1 = Game(f1, grille_J1, strategie=strategie_J1)

    # Équipe 2
    f2 = tk.Frame(frame); f2.pack(side="left")
    tk.Label(f2, text="Équipe 2 (2 Joueurs)", font=("Arial", 14)).pack()
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