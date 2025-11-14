import tkinter as tk
from tkinter import ttk

class EndScreen:
    def __init__(self, root, stats_j1, stats_j2):
        """
        stats_jX = {
            "score" : int,
            "recettes": [(nom, complexité), ...]
        }
        """
        self.root = root
        self.j1 = stats_j1
        self.j2 = stats_j2

        self._build_screen()

    def _build_screen(self):
        self.window = tk.Toplevel(self.root)
        self.window.title("Fin de partie — Résultats 🎉")
        self.window.geometry("900x600")
        self.window.config(bg="#1f1f1f")

        # ---- TITRE ----
        tk.Label(
            self.window, text="🎉 FIN DE LA PARTIE 🎉",
            font=("Arial", 24, "bold"), fg="white", bg="#1f1f1f"
        ).pack(pady=20)

        frame_global = tk.Frame(self.window, bg="#1f1f1f")
        frame_global.pack(fill="both", expand=True)

        # ---- COLONNE JOUEUR 1 ----
        self._build_player_column(frame_global, self.j1, "👩‍🍳 Joueur 1", 0)

        # ---- COLONNE JOUEUR 2 ----
        self._build_player_column(frame_global, self.j2, "🧑‍🍳 Joueur 2", 1)

        # ---- Bouton Rejouer ----
        tk.Button(
            self.window,
            text="🔁 Rejouer",
            font=("Arial", 16, "bold"),
            bg="#44bb44",
            fg="white",
            relief="raised",
            command=self._restart_game,
        ).pack(pady=20)

    def _build_player_column(self, parent, stats, title, col):
        f = tk.Frame(parent, bg="#1f1f1f")
        f.grid(row=0, column=col, padx=20)

        # Titre joueur
        tk.Label(
            f, text=title,
            font=("Arial", 20, "bold"),
            fg="#ffdd55", bg="#1f1f1f"
        ).pack(pady=10)

        score = stats["score"]
        recettes = stats["recettes"]

        nb = len(recettes)
        comp_totale = sum(c for (_, c) in recettes) or 1

        tk.Label(
            f, text=f"⭐ Score : {score}",
            font=("Arial", 16), fg="white", bg="#1f1f1f"
        ).pack(pady=5)

        tk.Label(
            f,
            text=f"Recettes livrées : {nb}\n"
                 f"Complexité totale : {comp_totale}\n"
                 f"Complexité moyenne : {comp_totale/max(1,nb):.2f}",
            font=("Arial", 12), fg="white", bg="#1f1f1f"
        ).pack(pady=10)

        # Tableau des recettes triées par complexité
        tk.Label(
            f, text="🏆 Recettes livrées :",
            font=("Arial", 14, "bold"), fg="#ff8866", bg="#1f1f1f"
        ).pack(pady=5)

        columns = ("Recette", "Complexité")
        table = ttk.Treeview(f, columns=columns, show="headings", height=10)
        table.heading("Recette", text="Recette")
        table.heading("Complexité", text="Complexité")

        for nom, c in sorted(recettes, key=lambda x: -x[1]):
            table.insert("", "end", values=(nom, c))

        table.pack()

    def _restart_game(self):
        """Redémarre la partie entièrement."""
        self.window.destroy()
        self.root.destroy()

        import main
        main.main()
