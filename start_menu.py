import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os
from main import main

# Couleurs du thème
BG_COLOR = "#2c3e50"
ACCENT_COLOR = "#e67e22"
TEXT_COLOR = "#ecf0f1"
BTN_HOVER = "#d35400"
FRAME_BG = "#34495e" # Couleur de fond pour les blocs d'équipe

class StartMenu:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Overcooked Mini - Configuration Match")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_COLOR)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TCombobox", fieldbackground=TEXT_COLOR, background=ACCENT_COLOR)

        # --- TITRE ---
        tk.Label(self.root, text="👨‍🍳 CONFIGURATION DU MATCH 👩‍🍳", 
                 font=("Segoe UI", 20, "bold"), bg=BG_COLOR, fg=ACCENT_COLOR).pack(pady=15)

        # --- CONTENEUR DES ÉQUIPES (GRID) ---
        teams_frame = tk.Frame(self.root, bg=BG_COLOR)
        teams_frame.pack(pady=10, padx=10, fill="x")

        # ====== COLONNE ÉQUIPE 1 ======
        self.frame_j1 = tk.Frame(teams_frame, bg=FRAME_BG, bd=2, relief="groove")
        self.frame_j1.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        
        tk.Label(self.frame_j1, text="ÉQUIPE 1 (Gauche)", font=("Arial", 14, "bold"), bg=FRAME_BG, fg="#3498db").pack(pady=10)
        
        # Choix Nombre Agents J1
        tk.Label(self.frame_j1, text="Nombre d'agents :", bg=FRAME_BG, fg=TEXT_COLOR).pack()
        self.nb_j1_var = tk.IntVar(value=2)
        f_radio_j1 = tk.Frame(self.frame_j1, bg=FRAME_BG)
        f_radio_j1.pack(pady=5)
        tk.Radiobutton(f_radio_j1, text="1", variable=self.nb_j1_var, value=1, command=self.update_ui, bg=FRAME_BG, fg=TEXT_COLOR, selectcolor=FRAME_BG).pack(side="left", padx=10)
        tk.Radiobutton(f_radio_j1, text="2", variable=self.nb_j1_var, value=2, command=self.update_ui, bg=FRAME_BG, fg=TEXT_COLOR, selectcolor=FRAME_BG).pack(side="left", padx=10)

        # Stratégies J1
        tk.Label(self.frame_j1, text="Stratégie Agent A :", bg=FRAME_BG, fg=TEXT_COLOR).pack(pady=(10,0))
        self.strat_j1_a = ttk.Combobox(self.frame_j1, values=["naive", "simple", "complexe"], state="readonly")
        self.strat_j1_a.current(0)
        self.strat_j1_a.pack(pady=5)

        self.lbl_j1_b = tk.Label(self.frame_j1, text="Stratégie Agent B :", bg=FRAME_BG, fg=TEXT_COLOR)
        self.lbl_j1_b.pack(pady=(5,0))
        self.strat_j1_b = ttk.Combobox(self.frame_j1, values=["naive", "simple", "complexe"], state="readonly")
        self.strat_j1_b.current(0)
        self.strat_j1_b.pack(pady=5)

        # ====== COLONNE ÉQUIPE 2 ======
        self.frame_j2 = tk.Frame(teams_frame, bg=FRAME_BG, bd=2, relief="groove")
        self.frame_j2.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        
        tk.Label(self.frame_j2, text="ÉQUIPE 2 (Droite)", font=("Arial", 14, "bold"), bg=FRAME_BG, fg="#e74c3c").pack(pady=10)

        # Choix Nombre Agents J2
        tk.Label(self.frame_j2, text="Nombre d'agents :", bg=FRAME_BG, fg=TEXT_COLOR).pack()
        self.nb_j2_var = tk.IntVar(value=2)
        f_radio_j2 = tk.Frame(self.frame_j2, bg=FRAME_BG)
        f_radio_j2.pack(pady=5)
        tk.Radiobutton(f_radio_j2, text="1", variable=self.nb_j2_var, value=1, command=self.update_ui, bg=FRAME_BG, fg=TEXT_COLOR, selectcolor=FRAME_BG).pack(side="left", padx=10)
        tk.Radiobutton(f_radio_j2, text="2", variable=self.nb_j2_var, value=2, command=self.update_ui, bg=FRAME_BG, fg=TEXT_COLOR, selectcolor=FRAME_BG).pack(side="left", padx=10)

        # Stratégies J2
        tk.Label(self.frame_j2, text="Stratégie Agent A :", bg=FRAME_BG, fg=TEXT_COLOR).pack(pady=(10,0))
        self.strat_j2_a = ttk.Combobox(self.frame_j2, values=["naive", "simple", "complexe"], state="readonly")
        self.strat_j2_a.current(0)
        self.strat_j2_a.pack(pady=5)

        self.lbl_j2_b = tk.Label(self.frame_j2, text="Stratégie Agent B :", bg=FRAME_BG, fg=TEXT_COLOR)
        self.lbl_j2_b.pack(pady=(5,0))
        self.strat_j2_b = ttk.Combobox(self.frame_j2, values=["naive", "simple", "complexe"], state="readonly")
        self.strat_j2_b.current(0)
        self.strat_j2_b.pack(pady=5)

        # --- BOUTONS ---
        btn_frame = tk.Frame(self.root, bg=BG_COLOR)
        btn_frame.pack(side="bottom", pady=30)

        self.btn_play = tk.Button(btn_frame, text="LANCER LE MATCH 🍳", font=("Arial", 14, "bold"),
                             bg=ACCENT_COLOR, fg="white", activebackground=BTN_HOVER, activeforeground="white",
                             width=25, relief="flat", cursor="hand2", command=self.start_game)
        self.btn_play.pack(pady=5)

        self.btn_quit = tk.Button(btn_frame, text="Quitter", font=("Arial", 10),
                             bg="#7f8c8d", fg="white", activebackground="#95a5a6",
                             width=10, relief="flat", cursor="hand2", command=self.root.destroy)
        self.btn_quit.pack(pady=5)

        self.update_ui()
        self.root.mainloop()

    def update_ui(self):
        """Active/Désactive les sélecteurs selon le nombre d'agents choisi pour chaque équipe."""
        # Gestion J1
        if self.nb_j1_var.get() == 1:
            self.strat_j1_b.config(state="disabled")
            self.lbl_j1_b.config(fg="gray")
        else:
            self.strat_j1_b.config(state="readonly")
            self.lbl_j1_b.config(fg=TEXT_COLOR)

        # Gestion J2
        if self.nb_j2_var.get() == 1:
            self.strat_j2_b.config(state="disabled")
            self.lbl_j2_b.config(fg="gray")
        else:
            self.strat_j2_b.config(state="readonly")
            self.lbl_j2_b.config(fg=TEXT_COLOR)

    def start_game(self):
        # Récupération Team 1
        nb1 = self.nb_j1_var.get()
        s1a = self.strat_j1_a.get()
        s1b = self.strat_j1_b.get()

        # Récupération Team 2
        nb2 = self.nb_j2_var.get()
        s2a = self.strat_j2_a.get()
        s2b = self.strat_j2_b.get()

        self.root.destroy()
        
        # On passe tous les arguments à main
        main(nb_agents_1=nb1, strat_1a=s1a, strat_1b=s1b,
             nb_agents_2=nb2, strat_2a=s2a, strat_2b=s2b)

if __name__ == "__main__":
    StartMenu()