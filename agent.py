import time
import random
from typing import List, Tuple, Optional, Iterable, Deque
from collections import deque

from recette import (
    Aliment, EtatAliment, Recette, IngredientRequis,
    prendre_au_bac, prendre_legume, nouvelle_recette
)
from carte import Carte

# -----------------------------------------------------------
# HELPERS
# -----------------------------------------------------------
Coord = Tuple[int, int]

def recettes_possibles_pour_items(items: List[Aliment], recettes: List[Recette]) -> List[Recette]:
    possibles = []
    for r in recettes:
        requis = r.requis
        used = [False] * len(requis)
        ok = True
        for a in items:
            matched = False
            for i, req in enumerate(requis):
                if used[i]: continue
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
    used = [False] * len(r.requis)
    for a in items:
        for i, req in enumerate(r.requis):
            if used[i]: continue
            if a.nom == req.nom and a.etat == req.etat_final:
                used[i] = True
                break
    return all(used)

def matched_flags_for_recipe(items: List[Aliment], r: Recette) -> List[bool]:
    flags = [False] * len(r.requis)
    for a in items:
        for i, req in enumerate(r.requis):
            if not flags[i] and a.nom == req.nom and a.etat == req.etat_final:
                flags[i] = True
                break
    return flags

def voisins_libres(carte: Carte, x: int, y: int) -> Iterable[Coord]:
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx, ny = x+dx, y+dy
        if 0 <= nx < carte.cols and 0 <= ny < carte.rows and not carte.est_bloquant(nx, ny):
            yield (nx, ny)

def bfs_path(carte: Carte, start: Coord, goals: Iterable[Coord]) -> Optional[List[Coord]]:
    goal_set = set(goals)
    if start in goal_set: return []
    q: Deque[Coord] = deque([start])
    parent: dict[Coord, Optional[Coord]] = {start: None}
    visited = {start}
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
            if nxt not in visited:
                visited.add(nxt)
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

# -----------------------------------------------------------
# CLASS AGENT
# -----------------------------------------------------------
class Agent:
    def __init__(self, game_instance, player_instance, strategie: str):
        self.game = game_instance
        self.player = player_instance
        self.strategie = strategie
        
        self.current_path: List[Coord] = []
        self.move_cooldown = 0
        self.move_every_ticks = 1.5

        self.bot_recette: Optional[Recette] = None
        self.next_req_idx: int = 0
        self.current_assembly: Optional[Coord] = None

        self.last_pos: Coord = (self.player.x, self.player.y)
        self.last_progress_time = time.time()
        self.pause_until = 0.0
        self.block_timeout_s = 3.0

    @property
    def carte(self):
        return self.game.carte

    def tick(self):
        now = time.time()
        if now < self.pause_until: return

        self._check_blockage(now)

        if not self.current_path:
            acted = self.try_action()
            if not acted:
                self._planifier()
        else:
            self.move_cooldown += 1
            if self.move_cooldown >= self.move_every_ticks:
                self._suivre_chemin()
                self.move_cooldown = 0
                if not self.current_path:
                    if self.try_action():
                        self._mark_progress()

    def _mark_progress(self):
        self.last_progress_time = time.time()
        self.last_pos = (self.player.x, self.player.y)

    def _check_blockage(self, now: float):
        pos_now = (self.player.x, self.player.y)
        stagnant = (pos_now == self.last_pos)
        if stagnant and (now - self.last_progress_time) > self.block_timeout_s:
            self.player.item = None
            self.current_assembly = None
            if self.game.recettes:
                self.bot_recette = self.choisir_recette()
                self.next_req_idx = 0
            self.current_path = []
            self.pause_until = now + 1.0
            self._mark_progress()

    def choisir_recette(self):
        recettes = self.game.recettes
        if not recettes: return None
        if self.strategie == "naive": return recettes[0]
        elif self.strategie == "simple": return min(recettes, key=lambda r: r.temps_estime)
        elif self.strategie == "complexe": return max(recettes, key=lambda r: r.difficulte_reelle)
        return recettes[0]

    def _ensure_bot_recette_valide(self):
        if not self.game.recettes:
            self.bot_recette = None; return
        if self.bot_recette not in self.game.recettes:
            self.bot_recette = self.choisir_recette()
            self.next_req_idx = 0
            self.current_assembly = None

    def _next_req_index_disponible(self, recette: Recette) -> Optional[int]:
        cuisson_noms = {alim.nom for (alim, _, _) in self.game.cuissons.values()}
        couverts = [False] * len(recette.requis)

        def mark_couvert(nom: str, etat):
            for i, req in enumerate(recette.requis):
                if couverts[i]: continue
                if nom == req.nom and etat == req.etat_final:
                    couverts[i] = True
                    return

        if self.player.item: mark_couvert(self.player.item.nom, self.player.item.etat)
        for stock in self.carte.assemblage_stock.values():
            for a in stock: mark_couvert(a.nom, a.etat)
        for alim, _, _ in self.game.cuissons.values():
            mark_couvert(alim.nom, alim.etat)

        for i, req in enumerate(recette.requis):
            if couverts[i]: continue
            if req.nom in cuisson_noms: continue
            return i
        return None

    def _stations_cuisson_pretes(self) -> List[Tuple[int, int]]:
        now = time.time()
        res = []
        for pos, (alim, t0, tfin) in self.game.cuissons.items():
            if now >= tfin: res.append(pos)
        return res

    # --- PLANIFICATION ---
    def _planifier(self):
        if self.player.item and any(r.nom == self.player.item.nom for r in self.game.recettes):
            self._aller_adjacent("SERVICE"); return

        if self.player.item and self.bot_recette:
            a = self.player.item
            etat_requis = None
            for req in self.bot_recette.requis:
                if req.nom == a.nom:
                    etat_requis = req.etape_suivante(a.etat); break
            
            if etat_requis == EtatAliment.COUPE:
                target = "DECOUPE" if a.etat == EtatAliment.SORTI_DU_BAC else "ASSEMBLAGE"
                self._aller_adjacent(target); return
            elif etat_requis == EtatAliment.CUIT:
                target = "FOUR_OU_POELE" if a.etat != EtatAliment.CUIT else "ASSEMBLAGE"
                self._aller_adjacent(target); return
            else:
                self._aller_adjacent("ASSEMBLAGE"); return

        if not self.game.recettes: return
        self._ensure_bot_recette_valide()
        if self.bot_recette is None: self.bot_recette = self.choisir_recette()

        stations_pretes = self._stations_cuisson_pretes()
        if stations_pretes:
            adj = cases_adjacentes_a_stations(self.carte, stations_pretes)
            path = bfs_path(self.carte, (self.player.x, self.player.y), adj)
            if path: self.current_path = path; return

        best = None
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
            if all(flags):
                self._aller_adjacent("ASSEMBLAGE"); return
            idx = self._next_req_index_disponible(self.bot_recette)
            if idx is not None:
                self.next_req_idx = idx
                target_req = self.bot_recette.requis[idx]
                self._aller_adjacent("BAC", cible_aliment=target_req.nom); return
            return

        idx = self._next_req_index_disponible(self.bot_recette)
        if idx is not None:
            self.current_assembly = None
            self.next_req_idx = idx
            target_req = self.bot_recette.requis[idx]
            self._aller_adjacent("BAC", cible_aliment=target_req.nom); return

    def _aller_adjacent(self, type_cible: str, cible_aliment: Optional[str] = None):
        px, py = self.player.x, self.player.y
        stations = []
        if type_cible == "BAC":
            for pos, (nom_bac, _) in self.carte.bacs_config.items():
                if nom_bac == (cible_aliment or ""): stations.append(pos)
                if nom_bac == "legume" and cible_aliment in ["tomate", "salade", "aubergine", "courgette", "poivron"]:
                    stations.append(pos)
        elif type_cible == "DECOUPE": stations = self.carte.pos_decoupes
        elif type_cible == "FOUR_OU_POELE":
            toutes = self.carte.pos_fours + self.carte.pos_poeles
            libres = [p for p in toutes if p not in self.game.cuissons]
            stations = libres or toutes
        elif type_cible == "ASSEMBLAGE":
            stations = [self.current_assembly] if self.current_assembly else self.carte.pos_assemblages
        elif type_cible == "SERVICE": stations = self.carte.pos_services

        adj = cases_adjacentes_a_stations(self.carte, stations)
        path = bfs_path(self.carte, (px, py), adj)
        self.current_path = path or []

    def _suivre_chemin(self):
        if not self.current_path: return
        if self.current_path[0] == (self.player.x, self.player.y): self.current_path.pop(0)
        if not self.current_path: return
        nx, ny = self.current_path.pop(0)
        dx, dy = nx - self.player.x, ny - self.player.y
        if abs(dx) + abs(dy) != 1: return
        if dx == -1: self.player.gauche(self.carte)
        elif dx == 1: self.player.droite(self.carte)
        elif dy == -1: self.player.haut(self.carte)
        elif dy == 1: self.player.bas(self.carte)
        self._mark_progress()

    # --- ACTIONS ---
    def try_action(self) -> bool:
        p = self.player
        # 1. BAC
        adj_bac = p.est_adjacent_a(self.carte.pos_bacs)
        if p.item is None and adj_bac and self.bot_recette:
            target_req = self.bot_recette.requis[self.next_req_idx % len(self.bot_recette.requis)]
            wanted = target_req.nom
            nom_bac, _ = self.carte.bacs_config.get(adj_bac, ("?", 0))

            if nom_bac == "legume":
                if wanted in ["tomate", "salade", "aubergine", "courgette", "poivron"]:
                    p.item = prendre_legume(wanted)
                    self._mark_progress(); return True
                return False
            
            if nom_bac != wanted: return False
            p.item = prendre_au_bac(nom_bac)
            self._mark_progress(); return True

        # 2. DECOUPE
        if p.item and p.est_adjacent_a(self.carte.pos_decoupes) and self.bot_recette:
            etat_requis = None
            for req in self.bot_recette.requis:
                if req.nom == p.item.nom:
                    etat_requis = req.etape_suivante(p.item.etat); break
            
            if etat_requis == EtatAliment.COUPE and p.item.etat == EtatAliment.SORTI_DU_BAC:
                from recette import TEMPS_COUPE
                duree = TEMPS_COUPE.get(p.item.nom, 1.0)
                pos_dec = p.est_adjacent_a(self.carte.pos_decoupes)
                self.game.trigger_action_bloquante("DECOUPE", pos_dec, p.item, duree)
                return True

        # 3. CUISSON
        adj_four = p.est_adjacent_a(self.carte.pos_fours)
        adj_poele = p.est_adjacent_a(self.carte.pos_poeles)
        pos_station = adj_four or adj_poele

        if pos_station and p.item is None:
            slot = self.game.cuissons.get(pos_station)
            if slot:
                alim, t0, tfin = slot
                if time.time() >= tfin:
                    p.item = alim
                    del self.game.cuissons[pos_station]
                    self._mark_progress(); return True

        if p.item and pos_station and self.bot_recette:
            etat_requis = None
            for req in self.bot_recette.requis:
                if req.nom == p.item.nom:
                    etat_requis = req.etape_suivante(p.item.etat); break
            if etat_requis == EtatAliment.CUIT:
                if p.item.etat in (EtatAliment.SORTI_DU_BAC, EtatAliment.COUPE):
                    if pos_station in self.game.cuissons: return False
                    from recette import TEMPS_CUISSON
                    duree = TEMPS_CUISSON.get(p.item.nom, 2.0)
                    self.game.start_cooking(pos_station, p.item, duree)
                    p.item = None
                    self._mark_progress(); return True

        # 4. ASSEMBLAGE
        adj_ass = p.est_adjacent_a(self.carte.pos_assemblages)
        if adj_ass:
            stock = self.carte.assemblage_stock.setdefault(adj_ass, [])
            plats_demandes = {r.nom for r in self.game.recettes}
            if stock:
                est_plat_final = (len(stock) == 1 and stock[0].nom in plats_demandes and stock[0].etat == EtatAliment.CUIT)
                if (not est_plat_final) and not recettes_possibles_pour_items(stock, self.game.recettes):
                    stock.clear()

            if self.bot_recette and p.item is None and items_completent_recette(stock, self.bot_recette):
                stock.clear()
                stock.append(Aliment(nom=self.bot_recette.nom, etat=EtatAliment.CUIT))
                self._mark_progress(); return True

            if p.item:
                recettes_cible = [self.bot_recette] if self.bot_recette else []
                tentative = stock + [p.item]
                possibles = recettes_possibles_pour_items(tentative, recettes_cible)

                if not possibles:
                    if len(stock) == 0 and self.bot_recette:
                        stock.append(p.item); p.item = None
                        self._mark_progress(); return True
                    p.item = None # Poubelle si incompatible
                    self._mark_progress(); return True
                
                stock.append(p.item); p.item = None
                if self.bot_recette and items_completent_recette(stock, self.bot_recette):
                    stock.clear()
                    stock.append(Aliment(nom=self.bot_recette.nom, etat=EtatAliment.CUIT))
                else:
                    if self.bot_recette:
                        self.next_req_idx = (self.next_req_idx + 1) % len(self.bot_recette.requis)
                self._mark_progress(); return True

            if p.item is None and stock:
                if len(stock) == 1 and stock[0].nom in [r.nom for r in self.game.recettes]:
                    p.item = stock.pop(0)
                    self._mark_progress(); self._aller_adjacent("SERVICE")
                    return True

        # 5. SERVICE
        if p.item:
            est_adj_service = any(abs(p.x - sx) + abs(p.y - sy) == 1 for (sx, sy) in self.carte.pos_services)
            if est_adj_service:
                for idx, r in enumerate(self.game.recettes):
                    if p.item.nom == r.nom:
                        self.game.deliver_recipe(idx, r)
                        p.item = None
                        if self.bot_recette is r or self.bot_recette not in self.game.recettes:
                            self.bot_recette = self.choisir_recette()
                            self.next_req_idx = 0
                            self.current_assembly = None
                        self._mark_progress(); return True
        return False