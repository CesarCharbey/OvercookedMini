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
        """Affiche une petite barre de progression sur la station où une action est en cours."""
        if not self.action_en_cours:
            return

        type_action, pos_action, aliment = self.action_en_cours
        if not pos_action:
            return

        now = time.time()
        total = self.action_fin - self.action_debut
        if total <= 0:
            return

        t = (now - self.action_debut) / total
        t = max(0.0, min(1.0, t))  # clamp 0..1

        sx, sy = pos_action

        # même taille de tuile que pour la carte / joueur
        tile = min(self.carte.largeur_px // self.carte.cols,
                self.carte.hauteur_px // self.carte.rows)
        cw = ch = int(tile)

        x1 = sx * cw
        y1 = sy * ch
        x2 = x1 + cw

        # petite barre en haut de la case
        margin = 4
        bar_h = 6
        bx1 = x1 + margin
        bx2 = x2 - margin
        by1 = y1 + margin
        by2 = by1 + bar_h

        # fond sombre
        self.canvas.create_rectangle(bx1, by1, bx2, by2,
                                    fill="#222", outline="black")

        # couleur selon type d'action
        if type_action == "DECOUPE":
            fill_color = "#ffb347"  # orange
        elif type_action == "CUISSON":
            fill_color = "#ff6961"  # rouge
        else:
            fill_color = "#6af06a"  # vert par défaut

        fx2 = bx1 + t * (bx2 - bx1)
        self.canvas.create_rectangle(bx1, by1, fx2, by2,
                                    fill=fill_color, outline="")

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


        # --- CUISSON : seulement si requis CUIT ---
        adj_four = p.est_adjacent_a(self.carte.pos_fours)
        adj_poele = p.est_adjacent_a(self.carte.pos_poeles)

        if p.item and (adj_four or adj_poele) and self.bot_recette:
            etat_requis = None
            for req in self.bot_recette.requis:
                if req.nom == p.item.nom:
                    etat_requis = req.etape_suivante(p.item.etat)
                    break

            if etat_requis == EtatAliment.CUIT and not p.item.est_perime:
                if p.item.etat in (EtatAliment.SORTI_DU_BAC, EtatAliment.COUPE):
                    from recette import TEMPS_CUISSON
                    duree = TEMPS_CUISSON.get(p.item.nom, 2.0)
                    pos_station = adj_four or adj_poele
                    self.action_en_cours = ("CUISSON", pos_station, p.item)
                    self.action_debut = time.time()
                    self.action_fin = self.action_debut + duree
                    self._refresh()
                    return True


        # --- ASSEMBLAGE ---
        adj_ass = p.est_adjacent_a(self.carte.pos_assemblages)
        if adj_ass:
            stock = self.carte.assemblage_stock.setdefault(adj_ass, [])

            # Si la recette courante est déjà complète ici : finaliser sans déposer
            if self.bot_recette and p.item is None and items_completent_recette(stock, self.bot_recette):
                stock.clear()
                stock.append(Aliment(nom=self.bot_recette.nom, etat=EtatAliment.CUIT, vitesse_peremption=0.0005))
                self._mark_progress()
                self._refresh()
                return True

            # Déposer ?
            if p.item and not p.item.est_perime:
                tentative = stock + [p.item]
                possibles = recettes_possibles_pour_items(tentative, self.recettes)

                if not possibles:
                    # Mauvais ingrédient : si assembleur vide dispo -> y déposer, sinon jeter + pause + restart
                    assembleurs_vides = [pos for pos in self.carte.pos_assemblages
                                         if len(self.carte.assemblage_stock.get(pos, [])) == 0]
                    if assembleurs_vides:
                        # si celui-ci est vide, déposer directement
                        if len(stock) == 0:
                            self.carte.assemblage_stock[adj_ass].append(p.item)
                            p.item = None
                            self._mark_progress()
                            self._refresh()
                            return True
                        # sinon aller vers l'assembleur vide le plus proche
                        adj_targets = cases_adjacentes_a_stations(self.carte, assembleurs_vides)
                        path = bfs_path(self.carte, (p.x, p.y), adj_targets)
                        if path:
                            self.current_path = path
                            self.move_cooldown = 0
                            return True

                    # Tous pleins OU pas d'assembleur vide atteignable -> jeter + purge + pause + restart
                    all_full = all(len(self.carte.assemblage_stock.get(pos, [])) > 0 for pos in self.carte.pos_assemblages)
                    if all_full:
                        # jette l'item en main
                        p.item = None
                        # purge 1 item du plus proche assembleur non vide
                        non_vides = [pos for pos in self.carte.pos_assemblages
                                     if len(self.carte.assemblage_stock.get(pos, [])) > 0]
                        if non_vides:
                            nearest = min(non_vides, key=lambda t: abs(p.x - t[0]) + abs(p.y - t[1]))
                            st = self.carte.assemblage_stock.get(nearest, [])
                            if st:
                                st.pop()
                        self._restart_recipe_flow()
                        return True

                    # Sinon essayer un autre assembleur
                    autres = [pos for pos in self.carte.pos_assemblages if pos != adj_ass]
                    if autres:
                        adj_targets = cases_adjacentes_a_stations(self.carte, autres)
                        path = bfs_path(self.carte, (p.x, p.y), adj_targets)
                        if path:
                            self.current_path = path
                            self.move_cooldown = 0
                            return True
                    return False

                # Compatible -> déposer
                stock.append(p.item)
                p.item = None

                completed_now = False
                for r in possibles:
                    if items_completent_recette(stock, r):
                        stock.clear()
                        stock.append(Aliment(nom=r.nom, etat=EtatAliment.CUIT, vitesse_peremption=0.0005))
                        completed_now = True
                        break
                if not completed_now and self.bot_recette:
                    self.next_req_idx = (self.next_req_idx + 1) % len(self.bot_recette.requis)

                self._mark_progress()
                self._refresh()
                return True

            # Reprendre plat final prêt
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
                        self.recettes.pop(idx)
                        self.recettes.append(nouvelle_recette())
                        self._mark_progress()
                        self._refresh()
                        return True

  
        return False

    # ---------- Planification ----------
    def _planifier(self):
        # Plat final en main -> Service
        if self.player.item and any(r.nom == self.player.item.nom for r in self.recettes):
            self._aller_adjacent("SERVICE")
            return

        # Si un ingrédient est en main -> étape selon l'état requis
        if self.player.item and self.bot_recette:
            a = self.player.item
            etat_requis = None
            for req in self.bot_recette.requis:
                if req.nom == a.nom:
                    etat_requis = req.etape_suivante(a.etat)
                    break

            if etat_requis == EtatAliment.COUPE:
                if a.etat == EtatAliment.SORTI_DU_BAC:
                    self._aller_adjacent("DECOUPE"); return
                else:
                    self._aller_adjacent("ASSEMBLAGE"); return
            elif etat_requis == EtatAliment.CUIT:
                if a.etat != EtatAliment.CUIT:
                    self._aller_adjacent("FOUR_OU_POELE"); return
                else:
                    self._aller_adjacent("ASSEMBLAGE"); return
            else:
                self._aller_adjacent("ASSEMBLAGE"); return

        # Sinon : exploiter un assembleur partiellement prêt pour la 1re recette
        if not self.recettes:
            return
        if self.bot_recette is None:
            self.bot_recette = self.choisir_recette()

        # scan des assembleurs
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
            # sinon, viser le 1er requis manquant
            self.next_req_idx = first_missing_index(flags)
            target_req = self.bot_recette.requis[self.next_req_idx]
            self._aller_adjacent("BAC", cible_aliment=target_req.nom)
            return

        # rien d'utile sur les assembleurs -> prendre 1er ingrédient
        self.current_assembly = None
        self.bot_recette = self.choisir_recette()
        self.next_req_idx = 0
        target_req = self.bot_recette.requis[self.next_req_idx]
        self._aller_adjacent("BAC", cible_aliment=target_req.nom)

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
            stations = self.carte.pos_fours + self.carte.pos_poeles or self.carte.pos_decoupes
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
                self.player.item = None

        for pos, stock in self.carte.assemblage_stock.items():
            for a in list(stock):
                a.tick(dt)
                if a.est_perime:
                    stock.remove(a)

        if now >= self.deadline: #fin de la partie on quitte
            return


        # ---- ACTION EN COURS (découpe, cuisson...) ----
        if self.action_en_cours:
            # Si l'action est terminée
            if time.time() >= self.action_fin:
                type_action, pos_action, aliment = self.action_en_cours

                # Finaliser l’action
                if type_action == "DECOUPE":
                    aliment.transformer(EtatAliment.COUPE)
                elif type_action == "CUISSON":
                    aliment.transformer(EtatAliment.CUIT)

                # Reset action
                self.action_en_cours = None
                self._mark_progress()

            else:
                # Action EN COURS → on stoppe totalement l'IA
                self._refresh()
                self.root.after(TICK_MS, self._tick)
                return

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
