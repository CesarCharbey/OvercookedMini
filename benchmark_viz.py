import time
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from main import grille_J1
from recette import (
    Aliment, EtatAliment, Recette, ALIMENTS_BAC, 
    nouvelle_recette
)
from carte import Carte
from player import Player
from agent import Agent

# =============================================================================
# MOTEUR DE SIMULATION HEADLESS
# =============================================================================
class HeadlessCarte(Carte):
    def _charger_textures(self, w, h): pass
    def dessiner(self, canvas): pass

class HeadlessPlayer(Player):
    def _load_sprite_sheet(self, path): pass
    def dessiner(self, canvas, carte): pass

class HeadlessGame:
    def __init__(self, strategie: str, duration_s: int):
        self.duration_s = duration_s
        self.current_sim_time = 0.0
        
        self.carte = HeadlessCarte(grille_J1, largeur=600, hauteur=600)
        self.carte.assigner_bacs(ALIMENTS_BAC)
        
        # --- MODIF 2vs2 : On crée 2 joueurs et 2 agents ---
        self.players = [
            HeadlessPlayer(2, 2),
            HeadlessPlayer(5, 2)
        ]

        self.score = 0
        self.recettes = [nouvelle_recette() for _ in range(3)]
        self.recettes_livrees = []
        self.cuissons = {} 
        
        self.score_history = [(0.0, 0)]
        
        # Stats globales (cumulées pour les 2 joueurs)
        self.stats_steps = 0
        self.time_working_total = 0.0
        self.time_walking_total = 0.0
        self.time_idle_total = 0.0

        # Actions en cours : Dict[Agent, (type, pos, aliment, fin_time)]
        self.actions_en_cours = {} 

        self.agents = [
            Agent(self, self.players[0], strategie, agent_id=0),
            Agent(self, self.players[1], strategie, agent_id=1)
        ]
        
        # Vitesse max pour simulation
        for a in self.agents:
            a.move_every_ticks = 1 

    def get_time(self) -> float:
        """Retourne le temps simulé (0.0 -> duration_s)"""
        return self.current_sim_time

    def trigger_action_bloquante(self, agent, type_action, pos, aliment, duree):
        """Mise à jour de la signature pour accepter 'agent'"""
        self.actions_en_cours[agent] = (type_action, pos, aliment, self.current_sim_time + duree)

    def start_cooking(self, pos, aliment, duree):
        self.cuissons[pos] = (aliment, self.current_sim_time, self.current_sim_time + duree)

    def deliver_recipe(self, index, recette):
        self.score += recette.difficulte_reelle
        self.recettes_livrees.append((recette.nom, recette.complexite))
        self.score_history.append((self.current_sim_time, self.score))
        self.recettes.pop(index)
        self.recettes.append(nouvelle_recette())

    def run(self):
        dt = 0.1
        while self.current_sim_time < self.duration_s:
            
            # --- 1. Physique (Juste Cuissons) ---
            for pos, (alim, t0, tfin) in list(self.cuissons.items()):
                if self.current_sim_time >= tfin and alim.etat != EtatAliment.CUIT:
                    alim.transformer(EtatAliment.CUIT)

            # On sauvegarde les positions avant update pour compter les pas
            prev_positions = [(p.x, p.y) for p in self.players]
            
            # Ensemble des agents occupés ce tick-ci
            agents_occupes = set()

            # --- 2. Actions Bloquantes (Multi-Agents) ---
            # On itère sur une copie des clés car on peut supprimer pendant la boucle
            for agent in list(self.actions_en_cours.keys()):
                type_act, _, aliment, t_fin = self.actions_en_cours[agent]
                
                if self.current_sim_time >= t_fin:
                    # Action finie
                    if type_act == "DECOUPE":
                        aliment.transformer(EtatAliment.COUPE)
                    del self.actions_en_cours[agent]
                    agent._mark_progress()
                else:
                    # Action en cours
                    agents_occupes.add(agent)
                    self.time_working_total += dt

            # --- 3. Agents Libres ---
            for i, agent in enumerate(self.agents):
                if agent not in agents_occupes:
                    agent.tick()

            # --- 4. Stats ---
            for i, p in enumerate(self.players):
                # Si le joueur a bougé
                if (p.x, p.y) != prev_positions[i]:
                    self.stats_steps += 1
                    self.time_walking_total += dt
                # Sinon, s'il n'était pas en train de travailler (découpe), il était Idle
                elif self.agents[i] not in agents_occupes:
                    self.time_idle_total += dt

            self.current_sim_time += dt
        
        # Calcul des stats finales
        efficiency = (self.stats_steps / self.score) if self.score > 0 else 0
        avg_complexity = 0
        if self.recettes_livrees:
            avg_complexity = sum(c for _, c in self.recettes_livrees) / len(self.recettes_livrees)

        # Temps total cumulé disponible (2 joueurs * durée)
        total_time_pool = self.duration_s * 2

        return {
            "score": self.score,
            "recettes_count": len(self.recettes_livrees),
            "avg_complexity": avg_complexity,
            "history": self.score_history,
            "efficiency_cost": efficiency,
            "time_walking_pct": (self.time_walking_total / total_time_pool) * 100,
            "time_working_pct": (self.time_working_total / total_time_pool) * 100,
            "time_idle_pct": (self.time_idle_total / total_time_pool) * 100
        }

def run_viz_benchmark():
    print("Démarrage du benchmark (Mode 2vs2)...")
    strategies = ["naive", "simple", "complexe"]
    durations = [90, 180] 
    iterations = 5 # Nombre d'itérations
    results = []
    histories = []

    total_sims = len(strategies) * len(durations) * iterations
    curr_sim = 0

    for strat in strategies:
        for dur in durations:
            for i in range(iterations):
                curr_sim += 1
                print(f"\rSimulation {curr_sim}/{total_sims} : {strat} ({dur}s)", end="")
                game = HeadlessGame(strategie=strat, duration_s=dur)
                res = game.run()
                results.append({
                    "Strategie": strat, "Duree": dur, "Score": res["score"],
                    "Nb_Recettes": res["recettes_count"], "Complexite_Moy": res["avg_complexity"],
                    "Cout_Deplacement": res["efficiency_cost"],
                    "Walking_Pct": res["time_walking_pct"], "Working_Pct": res["time_working_pct"],
                    "Idle_Pct": res["time_idle_pct"]
                })
                df_hist = pd.DataFrame(res["history"], columns=["Temps", "Score"])
                df_hist["Strategie"] = strat; df_hist["Duree"] = dur; df_hist["Sim_ID"] = curr_sim
                histories.append(df_hist)

    print("\n Simulation terminée.")
    df = pd.DataFrame(results)
    df_time = pd.concat(histories, ignore_index=True)

    sns.set_theme(style="whitegrid")
    fig = plt.figure(figsize=(18, 14))
    fig.suptitle('Benchmark Avancé (2vs2 - Tag Team)', fontsize=16)

    ax1 = fig.add_subplot(3, 2, 1)
    sns.barplot(data=df, x="Duree", y="Score", hue="Strategie", ax=ax1, palette="viridis")
    ax1.set_title("1. Score Moyen")

    ax2 = fig.add_subplot(3, 2, 2)
    max_dur = max(durations)
    sns.lineplot(data=df_time[df_time["Duree"] == max_dur], x="Temps", y="Score", hue="Strategie", ax=ax2, palette="viridis")
    ax2.set_title(f"2. Évolution du Score ({max_dur}s)")

    ax3 = fig.add_subplot(3, 2, 3)
    sns.scatterplot(data=df, x="Nb_Recettes", y="Complexite_Moy", hue="Strategie", style="Duree", s=100, alpha=0.7, ax=ax3, palette="viridis")
    ax3.set_title("3. Quantité vs Complexité")

    ax4 = fig.add_subplot(3, 2, 4)
    sns.barplot(data=df, x="Strategie", y="Cout_Deplacement", hue="Duree", ax=ax4, palette="rocket_r")
    ax4.set_title("4. Coût de Déplacement (Pas/Point)")

    ax5 = fig.add_subplot(3, 2, 5)
    df_budget = df.groupby("Strategie")[["Walking_Pct", "Working_Pct", "Idle_Pct"]].mean()
    df_budget.plot(kind='bar', stacked=True, ax=ax5, color=["#3498db", "#e67e22", "#95a5a6"])
    ax5.set_title("5. Budget Temps (Moyenne)")

    ax6 = fig.add_subplot(3, 2, 6)
    sns.boxplot(data=df, x="Strategie", y="Score", hue="Duree", ax=ax6, palette="viridis")
    ax6.set_title("6. Stabilité des Scores")

    plt.tight_layout()
    plt.savefig("resultats_benchmark_final.png")
    plt.show()

if __name__ == "__main__":
    run_viz_benchmark()