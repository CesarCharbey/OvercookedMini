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
        self.player = HeadlessPlayer(2, 2) 

        self.score = 0
        self.recettes = [nouvelle_recette() for _ in range(3)]
        self.recettes_livrees = []
        self.cuissons = {} 
        
        self.score_history = [(0.0, 0)]
        self.stats_steps = 0
        self.time_working = 0.0
        self.time_walking = 0.0
        self.time_idle = 0.0

        self.action_en_cours = None 
        self.action_fin_time = 0.0

        self.agent = Agent(self, self.player, strategie)
        self.agent.move_every_ticks = 1 

    # --- MÉTHODE CORRIGÉE POUR LE BENCHMARK ---
    def get_time(self) -> float:
        """Retourne le temps simulé (0.0 -> duration_s)"""
        return self.current_sim_time

    def trigger_action_bloquante(self, type_action, pos, aliment, duree):
        self.action_en_cours = (type_action, pos, aliment)
        self.action_fin_time = self.current_sim_time + duree

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
            prev_pos = (self.player.x, self.player.y)
            
            # --- 1. Physique (Juste Cuissons) ---
            for pos, (alim, t0, tfin) in list(self.cuissons.items()):
                if self.current_sim_time >= tfin and alim.etat != EtatAliment.CUIT:
                    alim.transformer(EtatAliment.CUIT)

            # --- 2. Actions Bloquantes ---
            if self.action_en_cours:
                self.time_working += dt
                type_act, _, aliment = self.action_en_cours
                if self.current_sim_time >= self.action_fin_time:
                    if type_act == "DECOUPE":
                        aliment.transformer(EtatAliment.COUPE)
                    self.action_en_cours = None
                    self.agent._mark_progress()
            else:
                # --- 3. Agent ---
                self.agent.tick()

                if (self.player.x, self.player.y) != prev_pos:
                    self.stats_steps += 1
                    self.time_walking += dt
                else:
                    self.time_idle += dt

            self.current_sim_time += dt
        
        efficiency = (self.stats_steps / self.score) if self.score > 0 else 0
        avg_complexity = 0
        if self.recettes_livrees:
            avg_complexity = sum(c for _, c in self.recettes_livrees) / len(self.recettes_livrees)

        return {
            "score": self.score,
            "recettes_count": len(self.recettes_livrees),
            "avg_complexity": avg_complexity,
            "history": self.score_history,
            "efficiency_cost": efficiency,
            "time_walking_pct": (self.time_walking / self.duration_s) * 100,
            "time_working_pct": (self.time_working / self.duration_s) * 100,
            "time_idle_pct": (self.time_idle / self.duration_s) * 100
        }

def run_viz_benchmark():
    print("Démarrage du benchmark corrigé...")
    strategies = ["naive", "simple", "complexe"]
    durations = [90, 180] 
    iterations = 100 # Nombre réduit pour test rapide
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
    fig.suptitle('Benchmark Avancé (Temps simulé synchronisé)', fontsize=16)

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