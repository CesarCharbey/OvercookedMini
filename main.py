# main.py
import tkinter as tk
from typing import List, Tuple, Optional, Iterable, Deque
from collections import deque
import time

from end_screen import EndScreen
from carte import Carte
from player import Player
from recette import (
    Aliment, EtatAliment, Recette,
    ALIMENTS_BAC, prendre_au_bac, nouvelle_recette, IngredientRequis
)

# ---------- Carte d'exemple ----------
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
MOVE_EVERY = 1.5
BLOCK_TIMEOUT_S = 3.0
PAUSE_AFTER_RESET_S = 1.0

# ---------- Helpers recettes ----------
def recettes_possibles_pour_items(items: List[Aliment], recettes: List[Recette]) -> List[Recette]:
    possibles = []
    for r in recettes:
        non_perimes = [a for a in items if not a.est_perime]
        requis = r.requis
        used = [False] * len(requis)
        ok = True
        for a in non_perimes:
            matched = False
            for i, req in enumerate(requis):
                if used[i]:
                    continue
                if a.nom == req.nom and a.etat == req.etat_final:
                    used[i] = True
                    matched = True
                    break
            if not matched:
                ok = False
                break
        if ok:
            possibles.append(r)
    return possibles

def items_completent_recette(items: List[Aliment], r: Recette) -> bool:
    non_perimes = [a for a in items if not a.est_perime]
    used = [False] * len(r.requis)
    for a in non_perimes:
        for i, req in enumerate(r.requis):
            if used[i]:
                continue
            if a.nom == req.nom and a.etat == req.etat_final:
                used[i] = True
                break
    return all(used)


def matched_flags_for_recipe(items: List[Aliment], r: Recette) -> List[bool]:
    flags = [False] * len(r.requis)
    for a in items:
        if a.est_perime:
            continue
        for i, req in enumerate(r.requis):
            if not flags[i] and a.nom == req.nom and a.etat == req.etat_final:
                flags[i] = True
                break
    return flags


def first_missing_index(flags: List[bool]) -> int:
    for i, ok in enumerate(flags):
        if not ok:
            return i
    return 0

# ---------- Pathfinding (BFS) ----------
Coord = Tuple[int, int]

def voisins_libres(carte: Carte, x: int, y: int) -> Iterable[Coord]:
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx, ny = x+dx, y+dy
        if 0 <= nx < carte.cols and 0 <= ny < carte.rows and not carte.est_bloquant(nx, ny):
            yield (nx, ny)

def bfs_path(carte: Carte, start: Coord, goals: Iterable[Coord]) -> Optional[List[Coord]]:
    goal_set = set(goals)
    q: Deque[Coord] = deque([start])
    parent: dict[Coord, Optional[Coord]] = {start: None}
    while q:
        cur = q.popleft()
        if cur in goal_set:
            path = [cur]
            while parent[cur] is not None:
                cur = parent[cur]
                path.append(cur)
            path.reverse()
            return path
        for nxt in voisins_libres(carte, *cur):
            if nxt not in parent:
                parent[nxt] = cur
                q.append(nxt)
    return None

def cases_adjacentes_a_stations(carte: Carte, stations: List[Coord]) -> List[Coord]:
    adj: set[Coord] = set()
    for (sx, sy) in stations:
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = sx+dx, sy+dy
            if 0 <= nx < carte.cols and 0 <= ny < carte.rows and not carte.est_bloquant(nx, ny):
                adj.add((nx, ny))
    return list(adj)

# ---------- Game + Bot ----------
class Game:
    def __init__(self, root: tk.Tk, grille_data=None, strategie = None) -> None:
        self.root = root
        self.canvas = tk.Canvas(root, width=W, height=H)
        self.canvas.pack()

        self.carte = Carte(grille_data, largeur=W, hauteur=H)
        self.carte.assigner_bacs(ALIMENTS_BAC)

        self.player = Player(2, 2, sprite_path="texture/Player.png")

        self.score = 0
        self.deadline = time.time() + GAME_DURATION_S
        self.last_tick = time.time()

        self.recettes: List[Recette] = [nouvelle_recette(), nouvelle_recette(), nouvelle_recette()]
        self.recettes_livrees = [] # utile pour garder des stats

        self.current_path: List[Coord] = []
        self.move_cooldown = 0
        self.bot_recette: Optional[Recette] = None
        self.bot_ingredient_en_cours: Optional[IngredientRequis] = None
        self.next_req_idx: int = 0

        # anti-blocage
        self.last_progress_time = time.time()
        self.last_pos: Coord = (self.player.x, self.player.y)
        self.pause_until = 0.0

        # assembleur “verrouillé” (si on exploite un partiel)
        self.current_assembly: Optional[Coord] = None

        # temps des actions
        self.action_en_cours = None
        self.action_debut = 0.0
        self.action_fin = 0.0

        # cuissons asynchrones : (x,y) -> (aliment, t_debut, t_fin)
        self.cuissons: dict[Tuple[int, int], Tuple[Aliment, float, float]] = {}

        self._refresh()
        self.root.after(TICK_MS, self._tick)

        #ajout de strategie
        self.strategie = strategie

    # ---------- HUD ----------
    def _dessiner_hud(self):
        now = time.time()
        remaining = max(0, int(self.deadline - now))
        mm = remaining // 60
        ss = remaining % 60
        info = f"⏱ {mm:02d}:{ss:02d}    ★ Score: {self.score}"

        TOP_H = 28

        # --- Bandeau du haut : timer + score ---
        self.canvas.create_rectangle(0, 0, W, TOP_H, fill="#222", outline="")
        self.canvas.create_text(
            8, TOP_H // 2,
            text=info, fill="white",
            anchor="w", font=("Arial", 12, "bold")
        )

        # --- Calcul de la hauteur réelle de la carte ---
        tile = min(self.carte.largeur_px // self.carte.cols,
                   self.carte.hauteur_px // self.carte.rows)
        map_height = self.carte.rows * tile

        # Le panneau du bas commence juste sous la carte
        panel_y0 = map_height
        if panel_y0 < TOP_H + 2:
            panel_y0 = TOP_H + 2

        # Rect fond
        self.canvas.create_rectangle(0, panel_y0, W, H, fill="#333", outline="")

        # Découpage en 2 colonnes
        LEFT_MARGIN = 8
        SPLIT_X = int(W * 0.55)     # tout ce qui est à gauche = recettes
        RIGHT_MARGIN = 8

        # petite ligne verticale de séparation
        self.canvas.create_line(SPLIT_X, panel_y0, SPLIT_X, H, fill="#555")

        # ---------- 1) Recettes à gauche (avec retour à la ligne) ----------
        y = panel_y0 + 4
        recettes_width = SPLIT_X - 2 * LEFT_MARGIN  # largeur max pour que ça ne déborde pas sur la colonne debug

        for i, r in enumerate(self.recettes):
            need = " + ".join(
                f"{req.nom}({'→'.join(et.name for et in req.etats if et != EtatAliment.SORTI_DU_BAC)})"
                for req in r.requis
            )
            txt = f"{i+1}. {r.nom}  [{need}]"
            self.canvas.create_text(
                LEFT_MARGIN, y,
                text=txt,
                fill="white",
                anchor="nw",
                font=("Arial", 10),
                width=recettes_width,   # <--- WRAP ICI
                justify="left",
            )
            # on laisse plus d'espace car la ligne peut être wrap sur 2–3 lignes
            y += 34

        # ---------- 2) Debug IA à droite ----------
        debug_x = SPLIT_X + RIGHT_MARGIN
        debug_width = W - debug_x - RIGHT_MARGIN

        lignes_debug = []

        # Recette cible
        if getattr(self, "bot_recette", None):
            lignes_debug.append(f"Recette cible : {self.bot_recette.nom}")
        else:
            lignes_debug.append("Recette cible : (aucune)")

        # Action en cours
        if getattr(self, "action_en_cours", None):
            type_action, pos_action, aliment = self.action_en_cours
            remaining_act = max(0.0, self.action_fin - now)
            lignes_debug.append(
                f"Action : {type_action} {getattr(aliment, 'nom', '?')} ({remaining_act:0.1f}s)"
            )
        elif getattr(self, "current_path", None):
            lignes_debug.append(
                f"Action : déplacement (chemin {len(self.current_path)} cases)"
            )
        else:
            lignes_debug.append("Action : choix / attente")

        # Prochaine case
        if getattr(self, "current_path", None):
            nx, ny = self.current_path[0]
            lignes_debug.append(f"Prochaine case : ({nx},{ny})")

        # éventuel cooldown anti-blocage
        if now < getattr(self, "pause_until", 0.0):
            lignes_debug.append(
                f"Cooldown IA : {self.pause_until - now:0.1f}s"
            )

        dy = panel_y0 + 4
        for line in lignes_debug:
            self.canvas.create_text(
                debug_x, dy,
                text=line,
                fill="white",
                anchor="nw",
                font=("Arial", 10),
                width=debug_width,   # <--- WRAP pour le texte debug aussi
                justify="left",
            )
            dy += 18

    def _dessiner_progress_stations(self):
        """Affiche des barres de progression + icônes sur découpe et cuissons."""
        # helper interne
        def draw_bar(sx, sy, t0, tfin, kind: str):
            now = time.time()
            total = tfin - t0
            if total <= 0:
                return
            ratio = max(0.0, min(1.0, (now - t0) / total))

            tile = min(self.carte.largeur_px // self.carte.cols,
                       self.carte.hauteur_px // self.carte.rows)
            cw = ch = int(tile)

            x1 = sx * cw
            y1 = sy * ch
            x2 = x1 + cw

            margin = 4
            bar_h = 6
            bx1 = x1 + margin
            bx2 = x2 - margin
            by1 = y1 + margin
            by2 = by1 + bar_h

            # fond
            self.canvas.create_rectangle(bx1, by1, bx2, by2,
                                         fill="#222", outline="black")

            if kind == "DECOUPE":
                color = "#ffb347"
                icon = "🔪"
            elif kind == "CUISSON":
                color = "#ff6961"
                icon = "🔥"
            else:
                color = "#6af06a"
                icon = "⚙️"

            fx2 = bx1 + ratio * (bx2 - bx1)
            self.canvas.create_rectangle(bx1, by1, fx2, by2,
                                         fill=color, outline="")

            # icône à gauche
            icon_x = bx1 - 2
            icon_y = (by1 + by2) / 2
            self.canvas.create_text(
                icon_x, icon_y,
                text=icon,
                anchor="e",
                font=("Arial", 10)
            )

        # 1) Découpe (bloquante)
        if self.action_en_cours:
            type_action, pos_action, aliment = self.action_en_cours
            if type_action == "DECOUPE" and pos_action:
                sx, sy = pos_action
                draw_bar(sx, sy, self.action_debut, self.action_fin, "DECOUPE")

        # 2) Cuissons asynchrones
        for (sx, sy), (alim, t0, tfin) in self.cuissons.items():
            draw_bar(sx, sy, t0, tfin, "CUISSON")


    def _refresh(self):
        self.player.dessiner(self.canvas, self.carte)
        self._dessiner_progress_stations()
        self._dessiner_debug_path()
        self._dessiner_hud()

    def _dessiner_debug_path(self):
        """Dessine un carré autour de la prochaine case de déplacement."""
        if not self.current_path:
            return

        # même taille de tuile que dans Carte.dessiner
        tile = min(self.carte.largeur_px // self.carte.cols,
                self.carte.hauteur_px // self.carte.rows)
        cw = ch = int(tile)

        nx, ny = self.current_path[0]
        x1 = nx * cw
        y1 = ny * ch
        x2 = x1 + cw
        y2 = y1 + ch

        # petit cadre cyan autour de la prochaine case
        self.canvas.create_rectangle(
            x1 + 2, y1 + 2, x2 - 2, y2 - 2,
            outline="cyan", width=3
        )

    # ---------- anti-blocage ----------
    def _mark_progress(self):
        self.last_progress_time = time.time()
        self.last_pos = (self.player.x, self.player.y)

    def _enter_cooldown(self, seconds: float = PAUSE_AFTER_RESET_S) -> None:
        self.pause_until = time.time() + seconds
        self.current_path = []
        self.move_cooldown = 0

    def _restart_recipe_flow(self) -> None:
        self.player.item = None
        self.current_assembly = None
        if self.recettes:
            self.bot_recette = self.choisir_recette()
            self.next_req_idx = 0
        self.current_path = []
        self._refresh()
        self._enter_cooldown(PAUSE_AFTER_RESET_S)
        self._mark_progress()

    def _check_blockage(self):
        now = time.time()
        pos_now = (self.player.x, self.player.y)
        stagnant = (pos_now == self.last_pos)
        if stagnant and (now - self.last_progress_time) > BLOCK_TIMEOUT_S:
            self._restart_recipe_flow()

    def choisir_recette(self):
        if self.strategie == "naive":
            return self.recettes[0]

        elif self.strategie == "simple":
            # prendre la recette avec la complexité la plus faible
            return min(self.recettes, key=lambda r: r.temps_estime)

        elif self.strategie == "complexe":
            #prendre la recette avec la complexité la plus haute
            return max(self.recettes, key=lambda r: r.difficulte_reelle) # utilisation de la vraie difficulté de la recettes (comme un mode expert)

        # fallback
        return self.recettes[0]
    
    def _ensure_bot_recette_valide(self):
        """S'assure que bot_recette pointe vers une recette encore demandée."""
        if not self.recettes:
            self.bot_recette = None
            return
        if self.bot_recette not in self.recettes:
            self.bot_recette = self.choisir_recette()
            self.next_req_idx = 0
            self.current_assembly = None

    
    # ---------- Actions “joueur” ----------
    def try_action_e(self):
        p = self.player
        # --- BAC : ne prendre que l’ingrédient requis courant ---
        adj_bac = p.est_adjacent_a(self.carte.pos_bacs)
        if p.item is None and adj_bac and self.bot_recette:
            target_req = self.bot_recette.requis[self.next_req_idx % len(self.bot_recette.requis)]
            wanted = target_req.nom

            nom_bac, v = self.carte.bacs_config.get(adj_bac, ("?", 0.0005))

            # Bac légumes → fournit le légume exact demandé
            if nom_bac == "legume":
                from recette import prendre_legume
                if wanted in ["tomate", "salade", "aubergine", "courgette", "poivron"]:
                    p.item = prendre_legume(wanted)
                    self._mark_progress()
                    self._refresh()
                    return True
                else:
                    return False  # Le bac légumes ne fournit pas viande/pate/etc.

            # Sinon : bac normal
            if nom_bac != wanted:
                return False

            p.item = prendre_au_bac(nom_bac, v)
            self._mark_progress()
            self._refresh()
            return True

        # --- DÉCOUPE : seulement si requis COUPE ---
        if p.item and p.est_adjacent_a(self.carte.pos_decoupes) and self.bot_recette:
            etat_requis = None
            for req in self.bot_recette.requis:
                if req.nom == p.item.nom:
                    etat_requis = req.etape_suivante(p.item.etat)
                    break

            if etat_requis == EtatAliment.COUPE and p.item.etat == EtatAliment.SORTI_DU_BAC and not p.item.est_perime:
                from recette import TEMPS_COUPE
                duree = TEMPS_COUPE.get(p.item.nom, 1.0)
                pos_dec = p.est_adjacent_a(self.carte.pos_decoupes)
                self.action_en_cours = ("DECOUPE", pos_dec, p.item)
                self.action_debut = time.time()
                self.action_fin = self.action_debut + duree
                self._refresh()
                return True


        # --- CUISSON : seulement si requis CUIT (asynchrone) ---
        adj_four = p.est_adjacent_a(self.carte.pos_fours)
        adj_poele = p.est_adjacent_a(self.carte.pos_poeles)
        pos_station = adj_four or adj_poele

        # 1) Récupérer un aliment déjà cuit sur la station si on a les mains vides
        if pos_station and p.item is None:
            slot = self.cuissons.get(pos_station)
            if slot:
                alim, t0, tfin = slot
                # si la cuisson est terminée et que ce n'est pas périmé -> on prend l'aliment
                if time.time() >= tfin and not alim.est_perime:
                    p.item = alim
                    del self.cuissons[pos_station]
                    self._mark_progress()
                    self._refresh()
                    return True

        # 2) Lancer une cuisson asynchrone
        if p.item and pos_station and self.bot_recette:
            etat_requis = None
            for req in self.bot_recette.requis:
                if req.nom == p.item.nom:
                    etat_requis = req.etape_suivante(p.item.etat)
                    break

            if etat_requis == EtatAliment.CUIT and not p.item.est_perime:
                if p.item.etat in (EtatAliment.SORTI_DU_BAC, EtatAliment.COUPE):
                    # four/poêle déjà occupé -> on ne fait rien
                    if pos_station in self.cuissons:
                        return False

                    from recette import TEMPS_CUISSON
                    duree = TEMPS_CUISSON.get(p.item.nom, 2.0)

                    # on dépose l'aliment sur la station et on le fait cuire en fond
                    alim = p.item
                    p.item = None
                    start = time.time()
                    self.cuissons[pos_station] = (alim, start, start + duree)

                    self._mark_progress()
                    self._refresh()
                    return True

        # --- ASSEMBLAGE ---
        adj_ass = p.est_adjacent_a(self.carte.pos_assemblages)
        if adj_ass:
            stock = self.carte.assemblage_stock.setdefault(adj_ass, [])

            # 0) Ne jamais considérer comme "impossible" une assiette qui contient déjà un plat final demandé
            plats_demandes = {r.nom for r in self.recettes}
            if stock:
                est_plat_final = (
                    len(stock) == 1
                    and stock[0].nom in plats_demandes
                    and stock[0].etat == EtatAliment.CUIT
                )
                if (not est_plat_final) and not recettes_possibles_pour_items(stock, self.recettes):
                    print("[ASSEMBLAGE] reset assiette impossible ->", adj_ass)
                    stock.clear()

            # 1) Si la recette courante est déjà complète ici : finaliser sans déposer
            if self.bot_recette and p.item is None and items_completent_recette(stock, self.bot_recette):
                stock.clear()
                stock.append(
                    Aliment(
                        nom=self.bot_recette.nom,
                        etat=EtatAliment.CUIT,
                        vitesse_peremption=0.0005,
                    )
                )
                self._mark_progress()
                self._refresh()
                return True

            # 2) Déposer un ingrédient ?
            if p.item and not p.item.est_perime:
                # On ne regarde QUE la recette courante pour cette assiette
                recettes_cible = [self.bot_recette] if self.bot_recette else []
                tentative = stock + [p.item]
                possibles = recettes_possibles_pour_items(tentative, recettes_cible)

                if not possibles:
                    # Si l'assiette est vide, on accepte quand même l'ingrédient
                    # comme base d'une tentative pour bot_recette
                    if len(stock) == 0 and self.bot_recette:
                        stock.append(p.item)
                        p.item = None
                        self._mark_progress()
                        self._refresh()
                        return True

                    # Sinon : on "jette" simplement l'item en main (poubelle logique)
                    # mais on ne touche PAS aux assiettes existantes
                    print("[ASSEMBLAGE] poubelle main ->", p.item.nom)
                    p.item = None
                    self._mark_progress()
                    self._refresh()
                    return True

                # Compatible avec la recette courante -> déposer
                stock.append(p.item)
                p.item = None

                # Est-ce que cette assiette complète la recette courante ?
                completed_now = False
                if self.bot_recette and items_completent_recette(stock, self.bot_recette):
                    stock.clear()
                    stock.append(
                        Aliment(
                            nom=self.bot_recette.nom,
                            etat=EtatAliment.CUIT,
                            vitesse_peremption=0.0005,
                        )
                    )
                    completed_now = True

                if not completed_now and self.bot_recette:
                    self.next_req_idx = (self.next_req_idx + 1) % len(self.bot_recette.requis)

                self._mark_progress()
                self._refresh()
                return True

            # 3) Reprendre plat final prêt
            if p.item is None and stock:
                if len(stock) == 1 and stock[0].nom in [r.nom for r in self.recettes]:
                    p.item = stock.pop(0)
                    self._mark_progress()
                    self._refresh()
                    # aller au Service
                    self._aller_adjacent("SERVICE")
                    return True


        # --- SERVICE : livrer si adjacent (géométrique) ---
        if p.item:
            est_adj_service = any(abs(p.x - sx) + abs(p.y - sy) == 1 for (sx, sy) in self.carte.pos_services)
            if est_adj_service:
                for idx, r in enumerate(self.recettes):
                    if p.item.nom == r.nom:

                        # --- SCORE INTELLIGENT ---
                        points = r.difficulte_reelle
                        self.score += points
                        self.recettes_livrees.append((r.nom, r.complexite))
                        p.item = None

                        # on retire la recette servie et on en ajoute une nouvelle
                        old = self.recettes.pop(idx)
                        self.recettes.append(nouvelle_recette())

                        # ne plus suivre une recette qui n'existe plus
                        if self.bot_recette is old or self.bot_recette not in self.recettes:
                            self.bot_recette = self.choisir_recette()
                            self.next_req_idx = 0
                            self.current_assembly = None

                        self._mark_progress()
                        self._refresh()
                        return True
  
        return False

    def _next_req_index_disponible(self, recette: Recette) -> Optional[int]:
        """
        Renvoie l'index d'un ingrédient de la recette qu'il est encore UTILE de préparer.

        - on évite ceux qui sont déjà en cuisson (même nom)
        - on évite ceux qui sont déjà présents en état final
          (dans la main, sur un assembleur, ou dans un four/poêle)
        """

        # noms d'aliments actuellement en cuisson (toutes recettes confondues)
        cuisson_noms = {alim.nom for (alim, _, _) in self.cuissons.values()}

        # pour chaque requi de la recette, on marque s'il est déjà couvert
        couverts = [False] * len(recette.requis)

        def mark_couvert(nom: str, etat):
            """Marque un requis comme déjà satisfait si on trouve (nom, état_final)."""
            for i, req in enumerate(recette.requis):
                if couverts[i]:
                    continue
                if nom == req.nom and etat == req.etat_final:
                    couverts[i] = True
                    return

        # 1) Ce qu'on a en main
        if self.player.item and not self.player.item.est_perime:
            mark_couvert(self.player.item.nom, self.player.item.etat)

        # 2) Ce qu'il y a sur les assiettes d'assemblage
        for stock in self.carte.assemblage_stock.values():
            for a in stock:
                if a.est_perime:
                    continue
                mark_couvert(a.nom, a.etat)

        # 3) Ce qui est dans les fours / poêles
        for alim, t0, tfin in self.cuissons.values():
            if alim.est_perime:
                continue
            mark_couvert(alim.nom, alim.etat)

        # 4) Choisir le premier requis qui n'est pas déjà couvert
        #    et qui n'est pas déjà en cuisson
        for i, req in enumerate(recette.requis):
            if couverts[i]:
                continue
            if req.nom in cuisson_noms:
                continue
            return i

        # tout ce qu'il faut pour cette recette est soit prêt, soit en cours de cuisson
        return None

    
    def _stations_cuisson_pretes(self) -> List[Tuple[int, int]]:
        """
        Renvoie la liste des fours/poêles où la cuisson est terminée
        et l'aliment n'est pas périmé.
        """
        now = time.time()
        res: List[Tuple[int, int]] = []
        for pos, (alim, t0, tfin) in self.cuissons.items():
            if now >= tfin and not alim.est_perime:
                res.append(pos)
        return res

    def _planifier_autre_recette(self):
        """
        Cherche une autre recette pour laquelle on peut préparer au moins un ingrédient
        (qui n'est pas déjà en cuisson). Si trouvée, met à jour bot_recette / next_req_idx
        et planifie un déplacement vers le bac correspondant.
        """
        """for r in self.recettes:
            if r is self.bot_recette:
                continue
            idx = self._next_req_index_disponible(r)
            if idx is not None:
                self.bot_recette = r
                self.current_assembly = None
                self.next_req_idx = idx
                target_req = r.requis[idx]
                self._aller_adjacent("BAC", cible_aliment=target_req.nom)
                return
        # aucune autre recette pour avancer -> on ne fait rien (on attend)"""
        return


    # ---------- Planification ----------
    def _planifier(self):
        # Plat final en main -> Service
        if self.player.item and any(r.nom == self.player.item.nom for r in self.recettes):
            self._aller_adjacent("SERVICE")
            return

        # Si un ingrédient est en main -> étape selon l'état requis de la recette courante
        if self.player.item and self.bot_recette:
            a = self.player.item
            etat_requis = None
            for req in self.bot_recette.requis:
                if req.nom == a.nom:
                    etat_requis = req.etape_suivante(a.etat)
                    break

            if etat_requis == EtatAliment.COUPE:
                if a.etat == EtatAliment.SORTI_DU_BAC:
                    self._aller_adjacent("DECOUPE")
                    return
                else:
                    self._aller_adjacent("ASSEMBLAGE")
                    return
            elif etat_requis == EtatAliment.CUIT:
                if a.etat != EtatAliment.CUIT:
                    self._aller_adjacent("FOUR_OU_POELE")
                    return
                else:
                    self._aller_adjacent("ASSEMBLAGE")
                    return
            else:
                self._aller_adjacent("ASSEMBLAGE")
                return

        # À partir d'ici : pas d'objet en main
        if not self.recettes:
            return
        self._ensure_bot_recette_valide()
        if self.bot_recette is None:
            self.bot_recette = self.choisir_recette()

        stations_pretes = self._stations_cuisson_pretes()
        if stations_pretes:
            adj = cases_adjacentes_a_stations(self.carte, stations_pretes)
            path = bfs_path(self.carte, (self.player.x, self.player.y), adj)
            if path:
                self.current_path = path
                return
        # ---------- 1) Essayer d'exploiter un assembleur partiellement prêt ----------
        best = None  # (pos, flags, matches, dist)
        for pos, stock in self.carte.assemblage_stock.items():
            flags = matched_flags_for_recipe(stock, self.bot_recette)
            matches = sum(flags)
            if matches > 0:
                dist = abs(self.player.x - pos[0]) + abs(self.player.y - pos[1])
                cand = (pos, flags, matches, dist)
                if best is None or cand[2] > best[2] or (cand[2] == best[2] and cand[3] < best[3]):
                    best = cand

        if best:
            pos, flags, _, _ = best
            self.current_assembly = pos
            # si déjà complet -> aller dessus, on finalisera sur place
            if all(flags):
                self._aller_adjacent("ASSEMBLAGE")
                return

            # besoin d'un nouvel ingrédient pour cette recette
            idx = self._next_req_index_disponible(self.bot_recette)
            if idx is not None:
                self.next_req_idx = idx
                target_req = self.bot_recette.requis[idx]
                self._aller_adjacent("BAC", cible_aliment=target_req.nom)
                return

            # aucun ingrédient dispo pour cette recette (probablement tous en cuisson) -> essayer une autre
            #self._planifier_autre_recette()
            return

        # ---------- 2) Aucun assembleur utile -> prendre un ingrédient pour la recette courante ----------
        idx = self._next_req_index_disponible(self.bot_recette)
        if idx is not None:
            self.current_assembly = None
            self.next_req_idx = idx
            target_req = self.bot_recette.requis[idx]
            self._aller_adjacent("BAC", cible_aliment=target_req.nom)
            return

        # ---------- 3) Recette courante bloquée (ingrédients déjà en cuisson) -> passer à une autre ----------
        #self._planifier_autre_recette()


    def _aller_adjacent(self, type_cible: str, cible_aliment: Optional[str] = None):
        px, py = self.player.x, self.player.y

        # Recherche des stations
        if type_cible == "BAC":
            stations = []
            for pos, (nom_bac, _) in self.carte.bacs_config.items():

                # Bac normal : correspondance exacte
                if nom_bac == (cible_aliment or ""):
                    stations.append(pos)

                # Bac légumes : accepte TOUT légume
                if nom_bac == "legume" and cible_aliment in ["tomate", "salade", "aubergine", "courgette", "poivron"]:
                    stations.append(pos)

        elif type_cible == "DECOUPE":
            stations = self.carte.pos_decoupes
        elif type_cible == "FOUR_OU_POELE":
            # On préfère les fours/poêles LIBRES si possible
            toutes = self.carte.pos_fours + self.carte.pos_poeles
            libres = [pos for pos in toutes if pos not in self.cuissons]
            stations = libres or toutes

        elif type_cible == "ASSEMBLAGE":
            stations = [self.current_assembly] if self.current_assembly else self.carte.pos_assemblages
        elif type_cible == "SERVICE":
            stations = self.carte.pos_services
        else:
            stations = []

        adj = cases_adjacentes_a_stations(self.carte, stations)
        path = bfs_path(self.carte, (px, py), adj)
        self.current_path = path or []

    def _suivre_chemin(self):
        if not self.current_path:
            return
        if self.current_path and self.current_path[0] == (self.player.x, self.player.y):
            self.current_path.pop(0)
        if not self.current_path:
            return
        nx, ny = self.current_path.pop(0)
        dx = nx - self.player.x
        dy = ny - self.player.y
        if abs(dx) + abs(dy) != 1:
            return
        if   dx == -1: self.player.gauche(self.carte)
        elif dx ==  1: self.player.droite(self.carte)
        elif dy == -1: self.player.haut(self.carte)
        elif dy ==  1: self.player.bas(self.carte)
        self._mark_progress()

    # ---------- Boucle ----------
    def _tick(self):
        now = time.time()
        dt = now - self.last_tick
        self.last_tick = now

        # pause active ?
        if time.time() < self.pause_until:
            self._refresh()
            self.root.after(TICK_MS, self._tick)
            return

        if self.player.item:
            self.player.item.tick(dt)
            if self.player.item and self.player.item.est_perime:
                print("[PERIME] main ->", self.player.item.nom, self.player.item.etat)
                self.player.item = None

        for pos, stock in self.carte.assemblage_stock.items():
            for a in list(stock):
                a.tick(dt)
                if a.est_perime:
                    print("[PERIME] assiette", pos, "->", a.nom, a.etat)
                    stock.remove(a)

        if now >= self.deadline:  # fin de la partie on quitte
            return

        # ---- CUISSONS ASYNCHRONES ----
        for pos, (alim, t0, tfin) in list(self.cuissons.items()):
            alim.tick(dt)
            # si ça pourrit dans le four -> on vide la station
            if alim.est_perime:
                del self.cuissons[pos]
                continue
            # quand le temps est écoulé, on le met en état CUIT (idempotent)
            if now >= tfin and alim.etat != EtatAliment.CUIT:
                alim.transformer(EtatAliment.CUIT)

        # ---- ACTION EN COURS (découpe BLOQUANTE uniquement) ----
        if self.action_en_cours:
            type_action, pos_action, aliment = self.action_en_cours

            if type_action == "DECOUPE":
                if now >= self.action_fin:
                    aliment.transformer(EtatAliment.COUPE)
                    self.action_en_cours = None
                    self._mark_progress()
                else:
                    # découpe en cours -> on bloque l'IA
                    self._refresh()
                    self.root.after(TICK_MS, self._tick)
                    return
            else:
                # au cas où d'autres actions bloquantes apparaissent un jour
                pass

        # anti-blocage avant décision
        self._check_blockage()

        if not self.current_path:
            acted = self.try_action_e()
            if not acted:
                self._planifier()
        else:
            self.move_cooldown += 1
            if self.move_cooldown >= MOVE_EVERY:
                self._suivre_chemin()
                self.move_cooldown = 0
                if not self.current_path:
                    if self.try_action_e():
                        self._mark_progress()

        self.player.update(dt)                
        self._refresh()
        self.root.after(TICK_MS, self._tick)

def main(strategie_J1="naive", strategie_J2="naive"):
    root = tk.Tk()
    root.title("Cuisine — Deux joueurs 🧑‍🍳🧑‍🍳")
    root.resizable(False, False)

    frame = tk.Frame(root)
    frame.pack()

    # ---- Carte / joueur 1 ----
    frame1 = tk.Frame(frame)
    frame1.pack(side="left")
    label1 = tk.Label(frame1, text="👩‍🍳 Joueur 1", font=("Arial", 14, "bold"))
    label1.pack()
    game1 = Game(frame1, grille_J1, strategie=strategie_J1)

    # ---- Carte / joueur 2 ----
    frame2 = tk.Frame(frame)
    frame2.pack(side="left")
    label2 = tk.Label(frame2, text="🧑‍🍳 Joueur 2", font=("Arial", 14, "bold"))
    label2.pack()
    game2 = Game(frame2, grille_J2, strategie=strategie_J2)

    # ---------- CHECK FIN DE PARTIE ----------
    def check_end():
        now = time.time()
        if now >= game1.deadline:   # Les deux partagent le même timer
            EndScreen(
                root,
                {"score": game1.score, "recettes": game1.recettes_livrees},
                {"score": game2.score, "recettes": game2.recettes_livrees},
            )
        else:
            root.after(200, check_end)

    check_end()   # lancement de la surveillance

    root.mainloop()


if __name__ == "__main__":
    main()
