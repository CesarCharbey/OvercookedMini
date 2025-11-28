import time
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# Imports du jeu
from recette import (
    Aliment, EtatAliment, Recette, ALIMENTS_BAC, 
    nouvelle_recette
)
from carte import Carte
from player import Player
from agent import Agent
from map_generator import generate_map

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
    def __init__(self, grille_data, spawn_positions, strategies: list, duration_s: int):
        self.duration_s = duration_s
        self.current_sim_time = 0.0
        
        # Initialisation Carte
        self.carte = HeadlessCarte(grille_data, largeur=600, hauteur=600)
        self.carte.assigner_bacs(ALIMENTS_BAC)
        
        self.score = 0
        self.recettes = [nouvelle_recette() for _ in range(3)]
        self.recettes_livrees = []
        self.cuissons = {} 
        self.score_history = [(0.0, 0)]
        
        self.stats_steps = 0
        self.time_working_total = 0.0
        self.time_walking_total = 0.0
        self.time_idle_total = 0.0

        self.actions_en_cours = {} 

        self.players = []
        self.agents = []

        # --- CRÉATION AGENTS SELON LA LISTE DE STRATÉGIES ---
        nb_agents = len(strategies)
        # On limite au nombre de spawns disponibles (généralement 2)
        limit_agents = min(nb_agents, len(spawn_positions))

        for i in range(limit_agents):
            sx, sy = spawn_positions[i]
            p = HeadlessPlayer(sx, sy)
            self.players.append(p)
            
            strat = strategies[i]
            a = Agent(self, p, strat, agent_id=i)
            # Pour la simulation, on accélère un peu la prise de décision
            a.move_every_ticks = 1.0 
            self.agents.append(a)

        # Liaison partenaires
        if limit_agents == 2:
            self.agents[0].partner = self.agents[1]
            self.agents[1].partner = self.agents[0]
        elif limit_agents == 1:
            self.agents[0].partner = None

    def get_time(self) -> float:
        return self.current_sim_time

    def trigger_action_bloquante(self, agent, type_action, pos, aliment, duree):
        start = self.current_sim_time
        self.actions_en_cours[agent] = (type_action, pos, aliment, start, start + duree)

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
            
            # Physique
            for pos, (alim, t0, tfin) in list(self.cuissons.items()):
                if self.current_sim_time >= tfin and alim.etat != EtatAliment.CUIT:
                    alim.transformer(EtatAliment.CUIT)

            prev_positions = [(p.x, p.y) for p in self.players]
            agents_occupes = set()
            
            # Actions bloquantes
            for agent in list(self.actions_en_cours.keys()):
                type_act, _, aliment, _, t_fin = self.actions_en_cours[agent]
                if self.current_sim_time >= t_fin:
                    if type_act == "DECOUPE": aliment.transformer(EtatAliment.COUPE)
                    del self.actions_en_cours[agent]
                    agent._mark_progress()
                else:
                    agents_occupes.add(agent)
                    self.time_working_total += dt

            # Tick Agents
            for agent in self.agents:
                if agent not in agents_occupes:
                    agent.tick()

            # Stats Mouvement
            for i, p in enumerate(self.players):
                if (p.x, p.y) != prev_positions[i]:
                    self.stats_steps += 1
                    self.time_walking_total += dt
                elif self.agents[i] not in agents_occupes:
                    self.time_idle_total += dt

            self.current_sim_time += dt
        
        # Résultats
        efficiency = (self.stats_steps / self.score) if self.score > 0 else 0
        avg_comp = 0
        if self.recettes_livrees:
            avg_comp = sum(c for _, c in self.recettes_livrees) / len(self.recettes_livrees)

        nb = len(self.agents)
        total_pool = self.duration_s * nb if nb > 0 else 1

        return {
            "score": self.score,
            "nb_agents": nb,
            "recettes_count": len(self.recettes_livrees),
            "avg_complexity": avg_comp,
            "history": self.score_history,
            "efficiency_cost": efficiency,
            "walking_pct": (self.time_walking_total / total_pool) * 100,
            "working_pct": (self.time_working_total / total_pool) * 100,
            "idle_pct": (self.time_idle_total / total_pool) * 100
        }

# =============================================================================
# LOGIQUE DE BENCHMARK ET VISUALISATION
# =============================================================================

def process_smoothed_curves(df_history, max_duration):
    """Lisse les courbes de score pour l'affichage."""
    common_time = pd.Index(np.arange(0, max_duration + 1, 1.0), name="Temps")
    smoothed_data = []

    for sim_id in df_history["Sim_ID"].unique():
        subset = df_history[df_history["Sim_ID"] == sim_id]
        if subset.empty: continue
        
        # On récupère les infos pour grouper
        label = subset["Label"].iloc[0]
        category = subset["Category"].iloc[0]
        
        s = subset.set_index("Temps")["Score"]
        s = s[~s.index.duplicated(keep='last')]
        s_resampled = s.reindex(s.index.union(common_time)).sort_index().ffill().reindex(common_time).fillna(0)
        
        for t, val in s_resampled.items():
            smoothed_data.append({"Temps": t, "Score": val, "Label": label, "Category": category})

    df_dense = pd.DataFrame(smoothed_data)
    if df_dense.empty: return pd.DataFrame()

    # Moyenne par Label (Scenario)
    df_mean = df_dense.groupby(["Label", "Temps", "Category"])["Score"].mean().reset_index()
    
    # Moyenne glissante pour faire joli
    df_mean["Score_Lisse"] = df_mean.groupby("Label")["Score"].transform(
        lambda x: x.rolling(window=10, min_periods=1).mean()
    )
    return df_mean

def run_viz_benchmark():
    print("Démarrage du Benchmark Comparatif...")
    print("Analyse des stratégies : Naif (Naïf), Simple (Simple), Complexe (Complexe)")

    # --- DÉFINITION DES SCÉNARIOS ---
    # Ici, on mappe les noms techniques (naive, simple...) vers des noms d'affichage propres.
    # On teste les SOLOS (1 agent) et les DUOS (2 agents) pour chaque niveau.
    
    scenarios = [
        # --- MODE 1 JOUEUR (SOLO) ---
        {"id": "solo_naif", "label": "Solo - Naif",    "strats": ["naive"],    "cat": "1 Agent"},
        {"id": "solo_simp", "label": "Solo - Simple",     "strats": ["simple"],   "cat": "1 Agent"},
        {"id": "solo_comp", "label": "Solo - Complexe",      "strats": ["complexe"], "cat": "1 Agent"},

        # --- MODE 2 JOUEURS (DUO) ---
        {"id": "duo_naif",  "label": "Duo - Naifs",    "strats": ["naive", "naive"],       "cat": "2 Agents"},
        {"id": "duo_simp",  "label": "Duo - Simple",      "strats": ["simple", "simple"],     "cat": "2 Agents"},
        {"id": "duo_comp",  "label": "Duo - Complexes",      "strats": ["complexe", "complexe"], "cat": "2 Agents"},
    ]

    duration = 90
    iterations = 100 
    
    results = []
    histories = []
    sim_counter = 0

    start_global = time.time()

    for i in range(iterations):
        # Générer une carte UNIQUE pour cette itération
        # Tous les scénarios vont jouer sur cette même carte pour être comparables
        grille, s1, s2 = generate_map()
        spawns = [s1, s2]
        
        print(f"\r[Carte {i+1}/{iterations}] Simulation des 6 scénarios...", end="")

        for scen in scenarios:
            sim_counter += 1
            
            # Lancer la simulation
            game = HeadlessGame(grille, spawns, scen["strats"], duration)
            res = game.run()

            # Stocker les résultats
            results.append({
                "Label": scen["label"],      # Nom affiché (ex: Solo - Complexe)
                "Category": scen["cat"],     # Pour les couleurs (1 Agent vs 2 Agents)
                "Nb_Agents": res["nb_agents"],
                "Score": res["score"],
                "Recettes": res["recettes_count"],
                "Efficacite": res["efficiency_cost"],
                "Idle": res["idle_pct"],
                "Score_Par_Agent": res["score"] / max(1, res["nb_agents"]) # Rentabilité
            })

            # Historique pour la courbe
            df_hist = pd.DataFrame(res["history"], columns=["Temps", "Score"])
            df_hist["Label"] = scen["label"]
            df_hist["Category"] = scen["cat"]
            df_hist["Sim_ID"] = sim_counter
            histories.append(df_hist)

    print(f"\nBenchmark terminé en {time.time() - start_global:.2f} s.")

    # --- GÉNÉRATION DES GRAPHIQUES ---
    df = pd.DataFrame(results)
    df_hist_raw = pd.concat(histories, ignore_index=True)
    df_curves = process_smoothed_curves(df_hist_raw, duration)

    # Configuration du style
    sns.set_theme(style="whitegrid", font_scale=1.1)
    
    # Création de la grille de graphiques
    fig = plt.figure(figsize=(18, 12))
    fig.suptitle(f'Performance IA : Impact du Nombre d\'Agents et de la Stratégie', fontsize=20, weight='bold')

    # Palette de couleurs : Bleu pour Solo, Orange pour Duo
    custom_palette = {"1 Agent": "#3498db", "2 Agents": "#e67e22"}

    # 1. SCORE FINAL (Barplot)
    ax1 = fig.add_subplot(2, 2, 1)
    sns.barplot(data=df, x="Label", y="Score", hue="Category", ax=ax1, palette=custom_palette, dodge=False)
    ax1.set_title("Score Moyen par Configuration", fontsize=14, weight='bold')
    ax1.set_xlabel("")
    ax1.set_ylabel("Score Moyen")
    ax1.tick_params(axis='x', rotation=15)
    ax1.legend(title="Taille Équipe")

    # 2. COURBES D'ÉVOLUTION (Lineplot)
    ax2 = fig.add_subplot(2, 2, 2)
    sns.lineplot(data=df_curves, x="Temps", y="Score_Lisse", hue="Category", style="Label", ax=ax2, palette=custom_palette, linewidth=2.5)
    ax2.set_title("Progression du Score au cours du temps", fontsize=14, weight='bold')
    ax2.set_xlabel("Temps (secondes)")
    ax2.set_ylabel("Score cumulé")

    # 3. RENTABILITÉ INDIVIDUELLE (Boxplot)
    # Permet de voir si 2 agents sont vraiment 2x plus efficaces que 1
    ax3 = fig.add_subplot(2, 2, 3)
    sns.boxplot(data=df, x="Label", y="Score_Par_Agent", hue="Category", ax=ax3, palette=custom_palette, dodge=False)
    ax3.set_title("Rentabilité Individuelle (Score généré par agent)", fontsize=14, weight='bold')
    ax3.set_xlabel("")
    ax3.set_ylabel("Points / Agent")
    ax3.tick_params(axis='x', rotation=15)

    # 4. TEMPS PERDU / ATTENTE (Barplot)
    # Révèle les problèmes de coordination (collisions)
    ax4 = fig.add_subplot(2, 2, 4)
    sns.barplot(data=df, x="Label", y="Idle", hue="Category", ax=ax4, palette="rocket")
    ax4.set_title("Taux d'Inactivité (Attente, Blocages)", fontsize=14, weight='bold')
    ax4.set_xlabel("")
    ax4.set_ylabel("% du temps inactif")
    ax4.tick_params(axis='x', rotation=15)
    ax4.legend(title="Taille Équipe")

    plt.tight_layout()
    filename = "benchmark_resultats.png"
    plt.savefig(filename)
    plt.show()

if __name__ == "__main__":
    run_viz_benchmark()