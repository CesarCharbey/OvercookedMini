# start_menu.py
import tkinter as tk
from tkinter import ttk
from main import main

class StartMenu:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Menu de démarrage — Overcooked IA")
        self.root.geometry("400x280")
        self.root.resizable(False, False)

        title = tk.Label(self.root, text="🍳 Overcooked — Menu de démarrage", 
                         font=("Arial", 16, "bold"))
        title.pack(pady=15)

        # ---- Sélection stratégie J1 ----
        frame1 = tk.Frame(self.root)
        frame1.pack(pady=5)
        tk.Label(frame1, text="Stratégie Joueur 1 :", font=("Arial", 12)).pack(side="left", padx=5)

        self.strat_j1 = ttk.Combobox(frame1, values=["naive", "simple", "complexe"])
        self.strat_j1.current(0)  # valeur par défaut : naive
        self.strat_j1.pack(side="left")

        # ---- Sélection stratégie J2 ----
        frame2 = tk.Frame(self.root)
        frame2.pack(pady=5)
        tk.Label(frame2, text="Stratégie Joueur 2 :", font=("Arial", 12)).pack(side="left", padx=5)

        self.strat_j2 = ttk.Combobox(frame2, values=["naive", "simple", "complexe"])
        self.strat_j2.current(0)  # valeur par défaut : naive
        self.strat_j2.pack(side="left")

        # ---- Boutons ----
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=25)

        play_btn = tk.Button(btn_frame, text="Jouer", font=("Arial", 12, "bold"),
                             width=12, command=self.start_game)
        play_btn.grid(row=0, column=0, padx=10)

        quit_btn = tk.Button(btn_frame, text="Quitter", font=("Arial", 12),
                             width=12, command=self.root.destroy)
        quit_btn.grid(row=0, column=1, padx=10)

        self.root.mainloop()

    def start_game(self):
        strat1 = self.strat_j1.get() or "naive"
        strat2 = self.strat_j2.get() or "naive"

        self.root.destroy()  # fermer le menu
        main(strat1, strat2)  # lancer le jeu

# ---- Lancement direct ----
if __name__ == "__main__":
    StartMenu()
