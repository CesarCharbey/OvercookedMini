# carte.py
from typing import List, Sequence, Tuple, Dict
import tkinter as tk
from PIL import Image, ImageTk

# Codes tuiles
SOL, BAC, FOUR, DECOUPE, SERVICE, JOUEUR, MUR, POELE, ASSEMBLAGE = 0, 1, 2, 3, 4, 5, 6, 7, 8
BLOQUANTS = {MUR, BAC, FOUR, DECOUPE, SERVICE, POELE, ASSEMBLAGE}
DIR_N, DIR_E, DIR_S, DIR_W = "N", "E", "S", "W"

class Carte:
    """Carte grille : dessine, expose les positions des stations et gère libellés/assignations de bacs/assemblage."""
    def __init__(self, grille: Sequence[Sequence[int]], largeur: int = 600, hauteur: int = 600) -> None:
        if not grille or not all(isinstance(row, (list, tuple)) for row in grille):
            raise ValueError("grille doit être une liste de listes.")
        w = len(grille[0])
        if any(len(row) != w for row in grille):
            raise ValueError("toutes les lignes doivent avoir la même longueur.")
        self.grille: List[List[int]] = [list(r) for r in grille]
        self.largeur_px = int(largeur)
        self.hauteur_px = int(hauteur)

        # positions
        self.pos_bacs: List[Tuple[int, int]] = []
        self.pos_decoupes: List[Tuple[int, int]] = []
        self.pos_services: List[Tuple[int, int]] = []
        self.pos_poeles: List[Tuple[int, int]] = []
        self.pos_fours: List[Tuple[int, int]] = []
        self.pos_assemblages: List[Tuple[int, int]] = []

        # config bacs: (x,y) -> (nom, vitesse)
        self.bacs_config: Dict[Tuple[int, int], Tuple[str, float]] = {}
        # stock assemblage: (x,y) -> liste d'objets (Aliment ou plat final)
        self.assemblage_stock: Dict[Tuple[int, int], List[object]] = {}

        self._indexer_stations()

        self.couleurs = {
            SOL:      "burlywood",
            BAC:      "blue",
            FOUR:     "red",
            DECOUPE:  "yellow",
            SERVICE:  "gray",
            JOUEUR:   "green",
            MUR:      "black",
            POELE:    "orange",
            ASSEMBLAGE: "#8bd3dd",
        }

        self.labels_base = {
            BAC: "Bac",
            FOUR: "Four",
            DECOUPE: "Découpe",
            SERVICE: "Service",
            POELE: "Poêle",
            ASSEMBLAGE: "Assemblage",
            JOUEUR: "Joueur",
        }

        #textures étendues pour le service
        self.service_tex_h = None  # 2x1, étendu vers la droite
        self.service_tex_v = None  # 1x2, étendu vers le bas

        # fichiers de crates
        self.crate_files_map = {
            "pain":    "texture/Tiles/crate_bread.png",
            "viande":  "texture/Tiles/crate_meat.png",
            "oeuf":    "texture/Tiles/crate_egg.png",
            "pate":    "texture/Tiles/crate_pasta.png",
            "legume":  "texture/Tiles/crate_vegetables.png",
        }

        # fichiers de textures
        self.texture_files = {
            SOL: "texture/Tiles/floor.png",
            DECOUPE: "texture/Tiles/cutting_board.png",
            FOUR: "texture/Tiles/oven.png",
            SERVICE: "texture/Tiles/service.png",
            POELE: "texture/Tiles/pan.png",
            ASSEMBLAGE: "texture/Tiles/plate.png",
            # MUR: "texture/Tiles/wall.png",  # si un jour on ajoute
        }

        # textures (clé = (code_tuile, direction))
        self.textures: Dict[Tuple[int, str], ImageTk.PhotoImage] = {}
        self.crate_textures: Dict[Tuple[str, str], ImageTk.PhotoImage] = {} # (nom_aliment, orientation)

        # calcul des textures en fonction de la taille
        self._charger_textures(self.largeur_px, self.hauteur_px)

        # orientation des stations (four, poêle, etc.)
        self.orientations: Dict[Tuple[int, int], str] = {}
        self._calculer_orientations()


    def _indexer_stations(self) -> None:
        self.pos_bacs.clear(); self.pos_decoupes.clear(); self.pos_services.clear()
        self.pos_poeles.clear(); self.pos_fours.clear(); self.pos_assemblages.clear()
        for y, row in enumerate(self.grille):
            for x, code in enumerate(row):
                if code == BAC: self.pos_bacs.append((x, y))
                elif code == DECOUPE: self.pos_decoupes.append((x, y))
                elif code == SERVICE: self.pos_services.append((x, y))
                elif code == POELE: self.pos_poeles.append((x, y))
                elif code == FOUR: self.pos_fours.append((x, y))
                elif code == ASSEMBLAGE:
                    self.pos_assemblages.append((x, y))
                    self.assemblage_stock.setdefault((x, y), [])

    def _calculer_orientations(self) -> None:
        """Calcule l'orientation 'logique' des stations (four, poêle, etc.)."""
        self.orientations = {}
        for y, row in enumerate(self.grille):
            for x, code in enumerate(row):
                if code in (FOUR, POELE, DECOUPE, SERVICE, ASSEMBLAGE, BAC):
                    self.orientations[(x, y)] = self._orientation_pour_case(x, y)

    def _orientation_pour_case(self, x: int, y: int) -> str:
        """
        Détermine dans quel sens la station doit regarder.
        Règle avec gestion des angles :
          - mur en haut + droite  -> regarde à droite
          - mur en haut + gauche  -> regarde à gauche
          - mur en bas  + droite  -> regarde à droite
          - mur en bas  + gauche  -> regarde à gauche
          - sinon : opposé au mur le plus proche
        """
        n = (y > 0 and self.grille[y - 1][x] == MUR)
        s = (y < self.rows - 1 and self.grille[y + 1][x] == MUR)
        w = (x > 0 and self.grille[y][x - 1] == MUR)
        e = (x < self.cols - 1 and self.grille[y][x + 1] == MUR)
        if n and e: return DIR_E
        if n and w: return DIR_W
        if s and e: return DIR_E
        if s and w: return DIR_W
        if n: return DIR_S
        if s: return DIR_N
        if e: return DIR_E
        if w: return DIR_W
        return DIR_S

    def _charger_textures(self, largeur_px, hauteur_px):
        """Charge les textures de toutes les tuiles + service 2x1."""
        # tuile carrée
        taille = min(largeur_px // self.cols, hauteur_px // self.rows)
        cw = ch = int(taille)

        self.textures = {}
        self.service_tex_h = None
        self.service_tex_v = None

        for code, path in self.texture_files.items():
            try:
                import os
                from PIL import Image, ImageTk
                img_raw = Image.open(path).convert("RGBA")
            except Exception as e:
                print(f"Erreur chargement texture {path} :", e)
                continue

            # SERVICE 2 cases
            if code == SERVICE:
                # 2x1 horizontal (vers la droite)
                img_h = img_raw.resize((cw * 2, ch), Image.LANCZOS)
                # 1x2 vertical (vers le bas) : on tourne le sprite
                img_v = img_raw.rotate(90, expand=True).resize((cw, ch * 2), Image.LANCZOS)

                self.service_tex_h = ImageTk.PhotoImage(img_h)
                self.service_tex_v = ImageTk.PhotoImage(img_v)
                continue

            base = img_raw.resize((cw, ch), Image.LANCZOS)

            if code == SOL:
                tex = ImageTk.PhotoImage(base)
                self.textures[(code, "N")] = tex
                self.textures[(code, "S")] = tex
                self.textures[(code, "E")] = tex
                self.textures[(code, "W")] = tex
                continue

            img_s = base
            img_n = base.rotate(180, expand=True).resize((cw, ch), Image.LANCZOS)
            img_e = base.rotate(-90, expand=True).resize((cw, ch), Image.LANCZOS)
            img_w = base.rotate(90,  expand=True).resize((cw, ch), Image.LANCZOS)

            from PIL import ImageTk
            self.textures[(code, "S")] = ImageTk.PhotoImage(img_s)
            self.textures[(code, "N")] = ImageTk.PhotoImage(img_n)
            self.textures[(code, "E")] = ImageTk.PhotoImage(img_e)
            self.textures[(code, "W")] = ImageTk.PhotoImage(img_w)
        
        # 2. Chargement des textures BACS dynamiques
        for aliment_nom, path in self.crate_files_map.items():
            img_raw = Image.open(path).convert("RGBA")
            base = img_raw.resize((cw, ch), Image.LANCZOS)
            # On génère les 4 orientations pour chaque type de crate
            self.crate_textures[(aliment_nom, "S")] = ImageTk.PhotoImage(base)
            self.crate_textures[(aliment_nom, "N")] = ImageTk.PhotoImage(base.rotate(180))
            self.crate_textures[(aliment_nom, "E")] = ImageTk.PhotoImage(base.rotate(-90))
            self.crate_textures[(aliment_nom, "W")] = ImageTk.PhotoImage(base.rotate(90))

    @property
    def rows(self) -> int: return len(self.grille)
    @property
    def cols(self) -> int: return len(self.grille[0])

    def assigner_bacs(self, items: List[Tuple[str, float]]) -> None:
        """
        Assigne chaque bac à un aliment (nom, vitesse).
        Si moins de bacs que d'aliments, on convertit des cases SOL en BAC (de gauche à droite, haut -> bas)
        jusqu'à en avoir au moins un par aliment.
        """
        # 1) créer des bacs supplémentaires si nécessaire
        manquants = max(0, len(items) - len(self.pos_bacs))
        if manquants > 0:
            for y in range(self.rows):
                for x in range(self.cols):
                    if manquants == 0: break
                    if self.grille[y][x] == SOL:
                        self.grille[y][x] = BAC
                        self.pos_bacs.append((x, y))
                        manquants -= 1
                if manquants == 0: break
            # reindex si on a modifié la grille
            self._indexer_stations()
            self._calculer_orientations()

        # 2) associer au moins un bac par aliment (et boucler si surplus de bacs)
        self.bacs_config.clear()
        for i, pos in enumerate(self.pos_bacs):
            nom, v = items[i % len(items)]
            self.bacs_config[pos] = (nom, v)

    def est_mur(self, x: int, y: int) -> bool:
        if 0 <= y < self.rows and 0 <= x < self.cols:
            return self.grille[y][x] == MUR
        return True

    def est_bloquant(self, x: int, y: int) -> bool:
        """Tout atelier + murs sont bloquants pour le déplacement."""
        if 0 <= y < self.rows and 0 <= x < self.cols:
            return self.grille[y][x] in BLOQUANTS
        return True

    def dessiner(self, canvas: tk.Canvas) -> None:
        canvas.config(width=self.largeur_px, height=self.hauteur_px)
        canvas.delete("all")

        # tuile carrée
        taille = min(self.largeur_px // self.cols, self.hauteur_px // self.rows)
        cw = ch = int(taille)

        floor_tex = self.textures.get((SOL, DIR_S))

        # --------- PASSAGE 1 : SOLS ----------
        for y in range(self.rows):
            for x in range(self.cols):
                code = self.grille[y][x]
                x1, y1 = x * cw, y * ch
                x2, y2 = (x + 1) * cw, (y + 1) * ch

                if code != MUR:
                    if floor_tex is not None:
                        canvas.create_image(x1, y1, image=floor_tex, anchor="nw")
                    else:
                        canvas.create_rectangle(
                            x1, y1, x2, y2,
                            outline="",
                            fill=self.couleurs.get(SOL, "burlywood")
                        )

        # --------- PASSAGE 2 : STATIONS + MURS ----------
        for y in range(self.rows):
            for x in range(self.cols):
                code = self.grille[y][x]
                x1, y1 = x * cw, y * ch
                x2, y2 = (x + 1) * cw, (y + 1) * ch

                # Murs
                if code == MUR:
                    fill = self.couleurs.get(MUR, "black")
                    canvas.create_rectangle(x1, y1, x2, y2, outline="", fill=fill)

                # Service
                elif code == SERVICE:
                    count_above = 0
                    yy = y - 1
                    while yy >= 0 and self.grille[yy][x] == SERVICE:
                        count_above += 1
                        yy -= 1

                    if count_above % 2 == 1:
                        pass
                    else:
                        if y + 1 < self.rows and self.grille[y + 1][x] == SERVICE:
                            if self.service_tex_v:
                                canvas.create_image(
                                    x1, y1,
                                    image=self.service_tex_v,
                                    anchor="nw"
                                )

                # BACS
                elif code == BAC:
                    orient = self.orientations.get((x, y), DIR_S)
                    
                    # Récupérer l'aliment
                    nom = self.bacs_config.get((x, y), ("?", 0))[0]
                    
                    # Mapper le nom vers la bonne clé de texture
                    # Si c'est un légume spécifique (tomate, etc), on utilise la caisse "legume"
                    if nom in ["tomate", "salade", "aubergine", "courgette", "poivron"]:
                        key = "legume"
                    else:
                        key = nom
                    
                    # Chercher dans le dico spécial crate_textures
                    tex = self.crate_textures.get((key, orient))
                    
                    if tex:
                        canvas.create_image(x1, y1, image=tex, anchor="nw")
                    else:
                        # Fallback (ce que tu voyais avant)
                        canvas.create_rectangle(x1, y1, x2, y2, fill="blue", outline="")

                # Autres stations
                elif code != SOL:
                    orient = self.orientations.get((x, y), DIR_S)
                    tex = self.textures.get((code, orient))
                    if tex is not None:
                        canvas.create_image(x1, y1, image=tex, anchor="nw")
                    else:
                        fill = self.couleurs.get(code, "white")
                        canvas.create_rectangle(x1, y1, x2, y2, outline="", fill=fill)

                # 2.e) Labels
                if code == ASSEMBLAGE:
                    stock = self.assemblage_stock.get((x, y), [])
                    if stock:
                        # Affiche seulement les noms des ingrédients
                        label = " +\n".join(getattr(a, "nom", str(a)) for a in stock)
                        canvas.create_text(
                            (x1 + x2) / 2, (y1 + y2) / 2,
                            text=label, fill="black", font=("Arial", 9), justify="center"
                        )