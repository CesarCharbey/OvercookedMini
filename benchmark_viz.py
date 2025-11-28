import time
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np  # <--- C'était l'import manquant

# On s'assure d'importer la grille depuis main
from main import grille_J1
from recette import (
    Aliment, EtatAliment, Recette, ALIMENTS_BAC, 
    nouvelle_recette
)
from carte import Carte
from player import Player
from agent import Agent

# =============================================================================
# MOTEUR DE SIMULATION HEADLESS (SANS INTERFACE GRAPHIQUE)
# =============================================================================

class HeadlessCarte(Carte):
    """Surcharge pour ne pas charger les images (lourdes et inutiles en simulation)."""
    def _charger_textures(self, w, h): pass
    def dessiner(self, canvas): pass

class HeadlessPlayer(Player):
    """Surcharge pour ne pas charger les sprites."""
    def _load_sprite_sheet(self, path): pass
    def dessiner(self, canvas, carte): pass

class HeadlessGame:
    def __init__(self, strategie: str, duration_s: int):
        self.duration_s = duration_s
        self.current_sim_time = 0.0
        
        # Initialisation Carte et Bacs
        self.carte = HeadlessCarte(grille_J1, largeur=600, hauteur=600)
        self.carte.assigner_bacs(ALIMENTS_BAC)
        
        # --- INITIALISATION 2 JOUEURS ---
        # Positionnés comme dans main.py pour éviter le blocage au spawn
        self.players = [
            HeadlessPlayer(2, 2),
            HeadlessPlayer(5, 2)
        ]

        # Données de jeu
        self.score = 0
        self.recettes = [nouvelle_recette() for _ in range(3)]
        self.recettes_livrees = []
        self.cuissons = {} 
        
        self.score_history = [(0.0, 0)]
        
        # Stats pour l'analyse
        self.stats_steps = 0
        self.time_working_total = 0.0
        self.time_walking_total = 0.0
        self.time_idle_total = 0.0

        # Actions en cours : Dict[Agent, (type, pos, aliment, fin_time)]
        self.actions_en_cours = {} 

        # --- CRÉATION ET LIAISON DES AGENTS (CRITIQUE) ---
        self.agents = [
            Agent(self, self.players[0], strategie, agent_id=0),
            Agent(self, self.players[1], strategie, agent_id=1)
        ]
        
        # IMPORTANT : On lie les partenaires pour activer la logique de coopération
        self.agents[0].partner = self.agents[1]
        self.agents[1].partner = self.agents[0]
        
        # Configuration Vitesse pour le benchmark
        # On met 1.0 pour qu'ils soient réactifs, ou vous pouvez mettre 2.0 
        # pour matcher exactement la vitesse visuelle actuelle.
        for a in self.agents:
            a.move_every_ticks = 1.0 

    def get_time(self) -> float:
        """Simule l'horloge du jeu."""
        return self.current_sim_time

    def trigger_action_bloquante(self, agent, type_action, pos, aliment, duree):
        """Enregistre une action qui bloque l'agent."""
        start = self.current_sim_time
        self.actions_en_cours[agent] = (type_action, pos, aliment, start, start + duree)

    def start_cooking(self, pos, aliment, duree):
        self.cuissons[pos] = (aliment, self.current_sim_time, self.current_sim_time + duree)

    def deliver_recipe(self, index, recette):
        self.score += recette.difficulte_reelle
        self.recettes_livrees.append((recette.nom, recette.complexite))
        self.score_history.append((self.current_sim_time, self.score))
        # Remplacement de la recette
        self.recettes.pop(index)
        self.recettes.append(nouvelle_recette())

    def run(self):
        """Boucle principale de simulation."""
        dt = 0.1 # Pas de temps équivalent à TICK_MS (100ms)
        
        while self.current_sim_time < self.duration_s:
            
            # 1. Physique (Cuissons)
            for pos, (alim, t0, tfin) in list(self.cuissons.items()):
                if self.current_sim_time >= tfin and alim.etat != EtatAliment.CUIT:
                    alim.transformer(EtatAliment.CUIT)

            # Snapshot positions pour détecter le mouvement
            prev_positions = [(p.x, p.y) for p in self.players]
            
            # 2. Gestion des Actions Bloquantes
            agents_occupes = set()
            
            # Copie des clés car on modifie le dictionnaire en itérant
            for agent in list(self.actions_en_cours.keys()):
                type_act, _, aliment, _, t_fin = self.actions_en_cours[agent]
                
                if self.current_sim_time >= t_fin:
                    if type_act == "DECOUPE":
                        aliment.transformer(EtatAliment.COUPE)
                    del self.actions_en_cours[agent]
                    agent._mark_progress()
                else:
                    agents_occupes.add(agent)
                    self.time_working_total += dt

            # 3. Update Agents (Logique de décision)
            for i, agent in enumerate(self.agents):
                if agent not in agents_occupes:
                    agent.tick()

            # 4. Collecte de Stats
            for i, p in enumerate(self.players):
                # Si le joueur a changé de coordonnées
                if (p.x, p.y) != prev_positions[i]:
                    self.stats_steps += 1
                    self.time_walking_total += dt
                # S'il ne bouge pas et ne travaille pas -> Idle (Attente/Réflexion/Blocage)
                elif self.agents[i] not in agents_occupes:
                    self.time_idle_total += dt

            self.current_sim_time += dt
        
        # --- CALCUL DES RÉSULTATS FINAUX ---
        
        # Efficacité : combien de pas pour 1 point de score (plus bas = mieux)
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

def process_smoothed_curves(df_history, max_duration):
    """
    Transforme les historiques bruts (événements discrets) en courbes lissées et moyennées.
    1. Ré-échantillonne chaque simulation sur une grille de temps commune (1 point/sec).
    2. Calcule la moyenne par stratégie.
    3. Applique une moyenne glissante (rolling window) pour lisser les paliers.
    """
    # Grille de temps commune (0 à max_duration secondes)
    common_time_index = pd.Index(np.arange(0, max_duration + 1, 1.0), name="Temps")
    
    smoothed_data = []

    # Pour chaque simulation individuelle
    for sim_id in df_history["Sim_ID"].unique():
        subset = df_history[df_history["Sim_ID"] == sim_id]
        if subset.empty: continue
        
        strat = subset["Strategie"].iloc[0]
        dur = subset["Duree"].iloc[0]
        
        # On ne traite que les simulations de la durée maximale pour le graphique temporel
        if dur != max_duration: continue

        # On crée une série temporelle à partir des événements
        s = subset.set_index("Temps")["Score"]
        # On supprime les doublons d'index s'il y en a (plusieurs scores au même timestamp précis)
        s = s[~s.index.duplicated(keep='last')]
        
        # Ré-échantillonnage : on projette sur la grille commune et on 'pad' (forward fill) les valeurs
        # Cela transforme l'escalier irrégulier en escalier régulier
        s_resampled = s.reindex(s.index.union(common_time_index)).sort_index().ffill().reindex(common_time_index).fillna(0)
        
        for t, val in s_resampled.items():
            smoothed_data.append({"Temps": t, "Score": val, "Strategie": strat})

    # DataFrame dense (toutes les secondes pour toutes les sims)
    df_dense = pd.DataFrame(smoothed_data)

    if df_dense.empty:
        return pd.DataFrame()

    # Calcul de la moyenne par Stratégie à chaque seconde
    df_mean = df_dense.groupby(["Strategie", "Temps"])["Score"].mean().reset_index()

    # Lissage : Moyenne glissante sur 10 secondes pour transformer les "marches" en pente
    # Cela donne l'aspect "progression moyenne"
    df_mean["Score_Lisse"] = df_mean.groupby("Strategie")["Score"].transform(
        lambda x: x.rolling(window=15, min_periods=1).mean()
    )

    return df_mean

def run_viz_benchmark():
    print("Démarrage du benchmark IA (Mode 2vs2 Coopératif)...")
    
    # Paramètres du benchmark
    strategies = ["naive", "simple", "complexe"]
    durations = [90, 180] # Durées de test en secondes
    iterations = 100        # Nombre de parties par configuration (Moyenne)
    
    results = []
    histories = []

    total_sims = len(strategies) * len(durations) * iterations
    curr_sim = 0

    start_global = time.time()

    for strat in strategies:
        for dur in durations:
            for i in range(iterations):
                curr_sim += 1
                print(f"\r[{curr_sim}/{total_sims}] Simulation : Strat={strat}, Durée={dur}s...", end="")
                
                game = HeadlessGame(strategie=strat, duration_s=dur)
                res = game.run()
                
                results.append({
                    "Strategie": strat, 
                    "Duree": dur, 
                    "Score": res["score"],
                    "Nb_Recettes": res["recettes_count"], 
                    "Complexite_Moy": res["avg_complexity"],
                    "Cout_Deplacement": res["efficiency_cost"],
                    "Walking_Pct": res["time_walking_pct"], 
                    "Working_Pct": res["time_working_pct"],
                    "Idle_Pct": res["time_idle_pct"]
                })
                
                # Sauvegarde historique pour courbe temporelle
                df_hist = pd.DataFrame(res["history"], columns=["Temps", "Score"])
                df_hist["Strategie"] = strat
                df_hist["Duree"] = dur
                df_hist["Sim_ID"] = curr_sim
                histories.append(df_hist)

    print(f"\nTerminé en {time.time() - start_global:.2f} secondes.")
    
    # --- TRAITEMENT DES DONNÉES ---
    df = pd.DataFrame(results)
    df_hist_raw = pd.concat(histories, ignore_index=True)
    
    # Préparation des données lissées pour le graphique 2
    max_dur = max(durations)
    df_smoothed = process_smoothed_curves(df_hist_raw, max_dur)

    # --- VISUALISATION ---
    sns.set_theme(style="whitegrid")
    fig = plt.figure(figsize=(18, 12))
    fig.suptitle('Benchmark IA Overcooked (2vs2 Coopératif)', fontsize=16, fontweight='bold')

    # 1. Score Moyen
    ax1 = fig.add_subplot(2, 3, 1)
    sns.barplot(data=df, x="Duree", y="Score", hue="Strategie", ax=ax1, palette="viridis")
    ax1.set_title("Score Moyen (Plus haut = Mieux)")

    # 2. Progression du Score (Moyenne Lissée)
    ax2 = fig.add_subplot(2, 3, 2)
    if not df_smoothed.empty:
        # On trace la courbe lissée
        sns.lineplot(data=df_smoothed, x="Temps", y="Score_Lisse", hue="Strategie", ax=ax2, palette="viridis", linewidth=2.5)
        # On peut ajouter les zones d'ombre (écart-type) si on veut, mais ici on reste sur la moyenne lissée propre
    ax2.set_title(f"Progression Moyenne Lissée ({max_dur}s)")
    ax2.set_ylabel("Score Moyen")

    # 3. Répartition du Temps
    ax3 = fig.add_subplot(2, 3, 3)
    df_budget = df.groupby("Strategie")[["Walking_Pct", "Working_Pct", "Idle_Pct"]].mean()
    df_budget.plot(kind='bar', stacked=True, ax=ax3, color=["#3498db", "#e67e22", "#95a5a6"])
    ax3.set_title("Budget Temps (% du temps total)")
    ax3.legend(["Marche", "Travail", "Attente"], loc='lower right')

    # 4. Quantité vs Qualité
    ax4 = fig.add_subplot(2, 3, 4)
    sns.scatterplot(data=df, x="Nb_Recettes", y="Complexite_Moy", hue="Strategie", style="Duree", s=100, alpha=0.7, ax=ax4, palette="deep")
    ax4.set_title("Quantité vs Complexité")

    # 5. Efficacité
    ax5 = fig.add_subplot(2, 3, 5)
    sns.barplot(data=df, x="Strategie", y="Cout_Deplacement", hue="Duree", ax=ax5, palette="rocket_r")
    ax5.set_title("Coût Mouvement (Pas / Score)")

    # 6. Stabilité
    ax6 = fig.add_subplot(2, 3, 6)
    sns.boxplot(data=df, x="Strategie", y="Score", hue="Duree", ax=ax6, palette="viridis")
    ax6.set_title("Stabilité des Performances")

    plt.tight_layout()
    plt.savefig("resultats_benchmark_final.png")
    print("Graphiques sauvegardés sous 'resultats_benchmark_final.png'")
    plt.show()

if __name__ == "__main__":
    run_viz_benchmark()