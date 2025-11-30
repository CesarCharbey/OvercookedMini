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
from map_generator import generate_map

# Constantes globales
W, H = 600, 600
GAME_DURATION_S = 90
TICK_MS = 100
sprites_game1 = [
        "texture/boss.png",  # Agent 1
        "texture/paul.png",  # Agent 2 (si présent)
    ]

sprites_game2 = [
    "texture/Player.png",  # Agent 1
    "texture/robin.png",  # Agent 2 (si présent)
]

class Game:
    def __init__(self, root: tk.Tk, grille_data: List[List[int]], spawn_positions: List[Tuple[int, int]], 
                 strategie_1="naive", strategie_2="naive", nb_agents=2, sprite_paths=None) -> None:
        self.root = root
        self.canvas = tk.Canvas(root, width=W, height=H)
        self.canvas.pack()

        # Initialisation de la carte avec la grille générée
        self.carte = Carte(grille_data, largeur=W, hauteur=H)
        self.carte.assigner_bacs(ALIMENTS_BAC)
        
        self.score = 0
        self.start_time = time.time()
        self.deadline = self.start_time + GAME_DURATION_S
        
        self.recettes: List[Recette] = [nouvelle_recette() for _ in range(3)]
        self.recettes_livrees = []
        
        self.cuissons: dict[Tuple[int, int], Tuple[Aliment, float, float]] = {}
        
        # Stockage des actions par agent
        self.actions_en_cours: Dict[Agent, Tuple[str, Tuple[int,int], Aliment, float, float]] = {}

        # --- CRÉATION DYNAMIQUE DES JOUEURS/AGENTS ---
        self.players = []
        self.agents = []
        
        # On s'assure de ne pas essayer de créer plus d'agents que de points de spawn disponibles
        # (Le générateur de map en fournit généralement 2)
        limit_agents = min(nb_agents, len(spawn_positions))

        for i in range(limit_agents):
            sx, sy = spawn_positions[i]
            
            # Création joueur
            if sprite_paths is not None and i < len(sprite_paths):
                sprite_path = sprite_paths[i]
            else:
                # Sprite par défaut si pas de liste fournie ou pas assez d’entrées
                sprite_path = "texture/Player.png"
            
            # Création joueur avec sprite spécifique
            p = Player(sx, sy, sprite_path=sprite_path, label=f"P{i+1}")
            self.players.append(p)


            # Choix de la stratégie (J1 prend strat1, J2 prend strat2)
            strat = strategie_1 if i == 0 else strategie_2
            
            # Création agent
            a = Agent(self, p, strat, agent_id=i)
            self.agents.append(a)

        # Liaison des partenaires
        if limit_agents == 2:
            self.agents[0].partner = self.agents[1]
            self.agents[1].partner = self.agents[0]
        elif limit_agents == 1:
            self.agents[0].partner = None

        self.last_tick = time.time()
        self._refresh()
        self.root.after(TICK_MS, self._tick)

    def get_time(self) -> float:
        return time.time()

    def trigger_action_bloquante(self, agent: Agent, type_action, pos, aliment, duree):
        """L'agent signale qu'il commence une action (ex: découpe)."""
        now = self.get_time()
        self.actions_en_cours[agent] = (type_action, pos, aliment, now, now + duree)

    def start_cooking(self, pos, aliment, duree):
        start = self.get_time()
        self.cuissons[pos] = (aliment, start, start + duree)

    def deliver_recipe(self, index, recette):
        self.score += recette.difficulte_reelle
        self.recettes_livrees.append((recette.nom, recette.complexite))
        self.recettes.pop(index)
        self.recettes.append(nouvelle_recette())

    def _tick(self):
        try:
            now = self.get_time()
            dt = now - self.last_tick
            self.last_tick = now

            if now >= self.deadline: return

            self._update_physics()

            # 1. GESTION DES ACTIONS BLOQUANTES
            agents_occupes = set()
            
            for agent in list(self.actions_en_cours.keys()):
                type_action, _, aliment, _, t_fin = self.actions_en_cours[agent]
                
                if now >= t_fin:
                    # Action terminée
                    if type_action == "DECOUPE":
                        aliment.transformer(EtatAliment.COUPE)
                    del self.actions_en_cours[agent]
                    agent._mark_progress()
                else:
                    # Action en cours
                    agents_occupes.add(agent)

            # 2. UPDATE DES AGENTS LIBRES
            for agent in self.agents:
                if agent not in agents_occupes:
                    agent.tick()

            # 3. UPDATE DES JOUEURS (Animation)
            for p in self.players:
                p.update(dt)

            self._refresh()

        except Exception as e:
            print(f"ERREUR DANS TICK: {e}")
            import traceback
            traceback.print_exc()

        self.root.after(TICK_MS, self._tick)

    def _update_physics(self):
        now = self.get_time()
        for pos, (alim, _, tfin) in list(self.cuissons.items()):
            if now >= tfin and alim.etat != EtatAliment.CUIT:
                alim.transformer(EtatAliment.CUIT)

    def _refresh(self):
        self.carte.dessiner(self.canvas) 
        
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
            
            bx1, bx2 = x1 + 4, x1 + cw - 4
            by1, by2 = y1 + 4, y1 + 10
            
            self.canvas.create_rectangle(bx1, by1, bx2, by2, fill="#222", outline="black")
            color = "#ffb347" if kind == "DECOUPE" else "#ff6961"
            fx2 = bx1 + ratio * (bx2 - bx1)
            self.canvas.create_rectangle(bx1, by1, fx2, by2, fill=color, outline="")

        for agent, (type_act, pos, _, t_deb, t_fin) in self.actions_en_cours.items():
            if type_act == "DECOUPE" and pos:
                draw_bar(pos[0], pos[1], t_deb, t_fin, "DECOUPE")
        
        for (sx, sy), (_, t0, tfin) in self.cuissons.items():
            draw_bar(sx, sy, t0, tfin, "CUISSON")

    def _dessiner_debug_path(self):
        colors = ["cyan", "magenta"]
        tile = min(self.carte.largeur_px // self.carte.cols, self.carte.hauteur_px // self.carte.rows)
        cw = ch = int(tile)
        
        for i, agent in enumerate(self.agents):
            if not agent.current_path: continue
            nx, ny = agent.current_path[0]
            col = colors[i % len(colors)]
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

        dx = SPLIT_X + 8
        dy = panel_y0 + 4
        for i, agent in enumerate(self.agents):
            status = "Occupé" if agent in self.actions_en_cours else "Libre"
            recette_nom = agent.bot_recette.nom if agent.bot_recette else '...'
            txt = f"J{i+1}: {recette_nom} ({status})"
            self.canvas.create_text(dx, dy, text=txt, fill="white", anchor="nw", font=("Arial", 9))
            dy += 18


def main(nb_agents_1=2, strat_1a="naive", strat_1b="naive",
         nb_agents_2=2, strat_2a="naive", strat_2b="naive"):
    
    root = tk.Tk()
    root.title(f"Overcooked Mini — {nb_agents_1} vs {nb_agents_2}")
    root.resizable(False, False)

    # 1. GÉNÉRATION DE LA MAP (Identique pour les deux équipes pour l'équité)
    # On génère une seule fois la grille et les spawns
    grille_generee, spawn1, spawn2 = generate_map()
    
    # On met les spawns dans une liste pour les passer à la classe Game
    spawns = [spawn1, spawn2]

    

    # --- INTERFACE TKINTER ---
    frame = tk.Frame(root)
    frame.pack()

    # --- ÉQUIPE 1 ---
    f1 = tk.Frame(frame)
    f1.pack(side="left", padx=5)
    
    tk.Label(f1, text=f"Équipe 1 ({nb_agents_1} IA)", font=("Arial", 14, "bold"), fg="#3498db").pack()
    
    # On passe la grille générée et les spawns
    g1 = Game(f1, grille_data=grille_generee, spawn_positions=spawns,
              strategie_1=strat_1a, strategie_2=strat_1b, nb_agents=nb_agents_1, sprite_paths=sprites_game1)


    # --- ÉQUIPE 2 ---
    f2 = tk.Frame(frame)
    f2.pack(side="left", padx=5)
    
    tk.Label(f2, text=f"Équipe 2 ({nb_agents_2} IA)", font=("Arial", 14, "bold"), fg="#e74c3c").pack()
    
    # On passe la MÊME grille et les MÊMES spawns (compétition sur terrain égal)
    g2 = Game(f2, grille_data=grille_generee, spawn_positions=spawns,
              strategie_1=strat_2a, strategie_2=strat_2b, nb_agents=nb_agents_2, sprite_paths=sprites_game2)

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
    # Valeurs par défaut pour test direct
    main()