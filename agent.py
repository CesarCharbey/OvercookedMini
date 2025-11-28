# agent.py
import time
import random
from typing import List, Tuple, Optional, Iterable, Deque, Set
from collections import deque

from recette import (
    Aliment, EtatAliment, Recette, IngredientRequis,
    prendre_au_bac, prendre_legume, nouvelle_recette
)
from carte import Carte

Coord = Tuple[int, int]

# --- HELPERS LOGIQUE RECETTE ---

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
    """Vérifie si les items présents sont tous valides pour la recette r."""
    used = [False] * len(r.requis)
    for a in items:
        found = False
        for i, req in enumerate(r.requis):
            if used[i]: continue
            if a.nom == req.nom and a.etat == req.etat_final:
                used[i] = True
                found = True
                break
        if not found: return False
    return True

def matched_flags_for_recipe(items: List[Aliment], r: Recette) -> List[bool]:
    flags = [False] * len(r.requis)
    for a in items:
        for i, req in enumerate(r.requis):
            if not flags[i] and a.nom == req.nom and a.etat == req.etat_final:
                flags[i] = True
                break
    return flags

# --- PATHFINDING AMÉLIORÉ ---

def voisins_libres(carte: Carte, x: int, y: int, obstacles_dynamiques: Set[Coord] = None) -> Iterable[Coord]:
    if obstacles_dynamiques is None: obstacles_dynamiques = set()
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx, ny = x+dx, y+dy
        if 0 <= nx < carte.cols and 0 <= ny < carte.rows:
            # On ne traverse pas les murs/stations ET on évite les obstacles dynamiques (l'autre joueur)
            if not carte.est_bloquant(nx, ny) and (nx, ny) not in obstacles_dynamiques:
                yield (nx, ny)

def bfs_path(carte: Carte, start: Coord, goals: Iterable[Coord], obstacles_dynamiques: Set[Coord] = None) -> Optional[List[Coord]]:
    goal_set = set(goals)
    # Si on est déjà sur l'objectif
    if start in goal_set: return []
    
    q: Deque[Coord] = deque([start])
    parent: dict[Coord, Optional[Coord]] = {start: None}
    visited = {start}
    
    # Sécurité : si le start est dans un obstacle (bug de spawn), on autorise le mouvement quand même
    if obstacles_dynamiques and start in obstacles_dynamiques:
        obstacles_dynamiques.remove(start)

    while q:
        cur = q.popleft()
        if cur in goal_set:
            path = [cur]
            while parent[cur] is not None:
                cur = parent[cur]
                path.append(cur)
            path.reverse()
            return path
        
        for nxt in voisins_libres(carte, *cur, obstacles_dynamiques=obstacles_dynamiques):
            if nxt not in visited:
                visited.add(nxt)
                parent[nxt] = cur
                q.append(nxt)
    return None

def cases_adjacentes_a_stations(carte: Carte, stations: List[Coord], obstacles_dynamiques: Set[Coord] = None) -> List[Coord]:
    adj: set[Coord] = set()
    for (sx, sy) in stations:
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = sx+dx, sy+dy
            # Une case est valide si elle est dans la grille, pas un mur, ET pas occupée par l'autre joueur
            if 0 <= nx < carte.cols and 0 <= ny < carte.rows:
                if not carte.est_bloquant(nx, ny):
                    if obstacles_dynamiques is None or (nx, ny) not in obstacles_dynamiques:
                        adj.add((nx, ny))
    return list(adj)


class Agent:
    def __init__(self, game_instance, player_instance, strategie: str, agent_id: int = 0):
        self.game = game_instance
        self.player = player_instance
        self.strategie = strategie
        self.agent_id = agent_id 
        self.partner: Optional['Agent'] = None # Référence vers l'autre agent

        self.current_path: List[Coord] = []
        self.target_station: Optional[Coord] = None # La station précise que l'on vise
        
        self.move_cooldown = 0
        self.move_every_ticks = 2.0

        self.bot_recette: Optional[Recette] = None
        self.next_req_idx: int = 0
        self.current_assembly: Optional[Coord] = None

        self.last_pos: Coord = (self.player.x, self.player.y)
        self.last_progress_time = self.game.get_time()
        self.pause_until = 0.0
        self.retreat_threshold_s = 2.0  # Au bout de 2s, on tente de reculer
        self.block_timeout_s = 5.0      # Au bout de 5s, on reset tout (hard reset)

    @property
    def carte(self):
        return self.game.carte

    def tick(self):
        now = self.game.get_time()
        if now < self.pause_until: return

        self._check_blockage(now)

        # Si on n'a pas de chemin, on réfléchit
        if not self.current_path:
            acted = self.try_action()
            if not acted:
                self._planifier()
        else:
            self.move_cooldown += 1
            if self.move_cooldown >= self.move_every_ticks:
                if self._chemin_est_libre_prochaine_etape():
                    self._suivre_chemin()
                    self.move_cooldown = 0
                else:
                    # --- CORRECTION 1 : GESTION DU BLOCAGE (PATIENCE) ---
                    # Au lieu de replanifier tout de suite, on attend un peu de façon aléatoire
                    # pour laisser l'autre passer.
                    self.current_path = [] 
                    # Pause aléatoire entre 0.2 et 0.8 secondes
                    self.pause_until = now + random.uniform(0.2, 0.8)
                    # On ne replanifie pas ici, le prochain tick le fera après la pause

                if not self.current_path:
                    if self.try_action():
                        self._mark_progress()

    def _chemin_est_libre_prochaine_etape(self) -> bool:
        """Vérifie si la prochaine case est libre (pas occupée par le partenaire)."""
        if not self.current_path: return True
        next_pos = self.current_path[0]
        if self.partner:
            partner_pos = (self.partner.player.x, self.partner.player.y)
            if next_pos == partner_pos:
                return False
        return True

    def _mark_progress(self):
        self.last_progress_time = self.game.get_time()
        self.last_pos = (self.player.x, self.player.y)

    def _tenter_degagement(self):
        """Essaie de trouver une case adjacente libre pour laisser passer le partenaire."""
        px, py = self.player.x, self.player.y
        partner_pos = (self.partner.player.x, self.partner.player.y) if self.partner else (-999, -999)
        
        candidates = []
        # On regarde les 4 voisins
        for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
            nx, ny = px + dx, py + dy
            
            # Vérifications de base (limites carte)
            if not (0 <= nx < self.carte.cols and 0 <= ny < self.carte.rows):
                continue
            
            # On ne va pas dans un mur ni une station
            if self.carte.est_bloquant(nx, ny):
                continue
                
            # CRITIQUE : On ne va pas SUR le partenaire (puisqu'on veut lui laisser la place)
            if (nx, ny) == partner_pos:
                continue
            
            # Si on a un chemin actuel, on essaie d'éviter la prochaine case prévue (pour ne pas insister)
            if self.current_path and (nx, ny) == self.current_path[0]:
                continue
                
            candidates.append((nx, ny))
        
        if candidates:
            # On choisit une case de fuite au hasard
            retreat_target = random.choice(candidates)
            
            # On force le mouvement : chemin d'un seul pas
            self.current_path = [retreat_target]
            
            # On met une pause après le mouvement pour laisser le temps à l'autre de passer
            self.pause_until = self.game.get_time() + 1.5 
            
            # On considère qu'on a bougé pour reset le timer de blocage
            self._mark_progress()
            # print(f"Agent {self.agent_id} recule vers {retreat_target} pour débloquer !")

    def _check_blockage(self, now: float):
        pos_now = (self.player.x, self.player.y)
        
        # Est-ce qu'on a bougé depuis la dernière fois ?
        if pos_now != self.last_pos:
            self.last_pos = pos_now
            self.last_progress_time = now
            return

        # Temps écoulé sans bouger
        stagnation_time = now - self.last_progress_time
        
        # ÉTAPE 1 : Tentative de dégagement (Marche arrière)
        if stagnation_time > self.retreat_threshold_s and stagnation_time < self.block_timeout_s:
            # On ne le fait qu'une fois toutes les X secondes pour ne pas spammer
            # Astuce : on utilise modulo ou un flag, mais ici le mark_progress dans _tenter_degagement fera le reset
            self._tenter_degagement()
            return

        # ÉTAPE 2 : Hard Reset (Si la marche arrière n'a pas suffi ou impossible)
        if stagnation_time > self.block_timeout_s:
            # On lâche l'item s'il ne sert à rien, ou on change de recette
            self.current_path = []
            self.target_station = None
            
            # Si on a un item en main, on le pose par terre (optionnel) ou on le garde
            # Reset complet de la logique
            self.bot_recette = None 
            
            # Petit temps de pause
            self.pause_until = now + 1.0 
            self._mark_progress()
            # print(f"Agent {self.agent_id} HARD RESET (Bloqué trop longtemps)")

    def choisir_recette(self):
        recettes = self.game.recettes
        if not recettes: return None
        
        # 1. On copie et on trie selon la stratégie
        sorted_recettes = list(recettes)
        if self.strategie == "simple":
            # Les plus rapides d'abord
            sorted_recettes.sort(key=lambda r: r.temps_estime)
        elif self.strategie == "complexe":
            # Les plus difficiles d'abord (rapporter plus de points)
            sorted_recettes.sort(key=lambda r: r.difficulte_reelle, reverse=True)
        # Si "naive", on garde l'ordre d'arrivée
        
        # 2. Identification de la recette du partenaire
        recette_partenaire = None
        if self.partner and self.partner.bot_recette:
            recette_partenaire = self.partner.bot_recette

        # 3. Sélection intelligente
        # On parcourt la liste triée. On prend la première qui n'est PAS celle du partenaire.
        for r in sorted_recettes:
            # On vérifie l'identité de l'objet (is) ou le nom
            if r is not recette_partenaire:
                #print(f"Agent {self.agent_id} choisit : {r.nom} (Évite {recette_partenaire.nom if recette_partenaire else 'rien'})")
                return r
        
        # 4. Fallback (Cas rare)
        # Si on arrive ici, c'est qu'il n'y a qu'une seule recette disponible 
        # et que le partenaire est déjà dessus. On aide le partenaire !
        #print(f"Agent {self.agent_id} aide son partenaire sur : {sorted_recettes[0].nom}")
        return sorted_recettes[0]

    def _ensure_bot_recette_valide(self):
        if not self.game.recettes:
            self.bot_recette = None; return
        if self.bot_recette not in self.game.recettes:
            self.bot_recette = self.choisir_recette()
            self.next_req_idx = 0
            self.current_assembly = None

    def _next_req_index_disponible(self, recette: Recette) -> Optional[int]:
        """Cherche le prochain ingrédient nécessaire qui n'est pas déjà en cours."""
        cuisson_noms = {alim.nom for (alim, _, _) in self.game.cuissons.values()}
        couverts = [False] * len(recette.requis)

        def mark_couvert(nom: str, etat):
            for i, req in enumerate(recette.requis):
                if couverts[i]: continue
                if nom == req.nom and etat == req.etat_final:
                    couverts[i] = True
                    return

        # Ce que j'ai en main
        if self.player.item: mark_couvert(self.player.item.nom, self.player.item.etat)
        
        # Ce qui est sur les tables
        for stock in self.carte.assemblage_stock.values():
            for a in stock: mark_couvert(a.nom, a.etat)
            
        # Ce qui cuit
        for alim, _, _ in self.game.cuissons.values():
            mark_couvert(alim.nom, alim.etat)

        for i, req in enumerate(recette.requis):
            if couverts[i]: continue
            if req.nom in cuisson_noms: continue
            return i
        return None

    def _stations_cuisson_pretes(self) -> List[Tuple[int, int]]:
        now = self.game.get_time()
        res = []
        for pos, (alim, t0, tfin) in self.game.cuissons.items():
            if now >= tfin: res.append(pos)
        return res

    # --- PLANIFICATION ---
    def _planifier(self):
        self._ensure_bot_recette_valide()
        if self.bot_recette is None: self.bot_recette = self.choisir_recette()
        
        # 0. Réflexe : J'ai un item fini pour une recette ? -> Service
        if self.player.item and any(r.nom == self.player.item.nom for r in self.game.recettes):
            self._aller_adjacent("SERVICE"); return

        # 1. J'ai un item en main : Que faire avec ?
        if self.player.item and self.bot_recette:
            a = self.player.item
            etat_requis = None
            
            # Vérifier si cet item sert dans MA recette
            needed_here = False
            for req in self.bot_recette.requis:
                if req.nom == a.nom:
                    etat_requis = req.etape_suivante(a.etat)
                    needed_here = True
                    break
            
            # Si l'item ne sert pas à ma recette courante, est-ce qu'il sert à une autre ?
            # Si oui, on le pose sur une table d'assemblage (stockage temporaire)
            if not needed_here:
                self._aller_adjacent("ASSEMBLAGE"); return

            # Logique de transformation
            if etat_requis == EtatAliment.COUPE:
                target = "DECOUPE" if a.etat == EtatAliment.SORTI_DU_BAC else "ASSEMBLAGE"
                self._aller_adjacent(target); return
            elif etat_requis == EtatAliment.CUIT:
                target = "FOUR_OU_POELE" if a.etat != EtatAliment.CUIT else "ASSEMBLAGE"
                self._aller_adjacent(target); return
            else:
                # Plus de transformation nécessaire -> Assemblage
                self._aller_adjacent("ASSEMBLAGE"); return

        # 2. Rien en main : Je cherche du travail
        if not self.game.recettes: return

        # A. Une cuisson est finie ? Je vais la chercher
        stations_pretes = self._stations_cuisson_pretes()
        if stations_pretes:
            # On filtre les stations que le partenaire vise déjà ? 
            # Pour simplifier, BFS gérera la proximité, mais on pourrait filtrer ici.
            adj = cases_adjacentes_a_stations(self.carte, stations_pretes, self._get_dynamic_obstacles())
            path = bfs_path(self.carte, (self.player.x, self.player.y), adj, self._get_dynamic_obstacles())
            if path: 
                self.current_path = path
                self.target_station = stations_pretes[0] # Approx
                return

        # B. Assemblage incomplet optimal ?
        best = None
        for pos, stock in self.carte.assemblage_stock.items():
            if not stock: continue
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
                # Recette complète sur la table -> Je vais la chercher pour servir
                self._aller_adjacent("ASSEMBLAGE"); return
            
            # Sinon, quel est le prochain ingrédient manquant ?
            idx = self._next_req_index_disponible(self.bot_recette)
            if idx is not None:
                self.next_req_idx = idx
                target_req = self.bot_recette.requis[idx]
                self._aller_adjacent("BAC", cible_aliment=target_req.nom); return
            return

        # C. Démarrer une nouvelle étape
        idx = self._next_req_index_disponible(self.bot_recette)
        if idx is not None:
            self.current_assembly = None
            self.next_req_idx = idx
            target_req = self.bot_recette.requis[idx]
            self._aller_adjacent("BAC", cible_aliment=target_req.nom); return

    def _get_dynamic_obstacles(self) -> Set[Coord]:
        obs = set()
        if self.partner:
            obs.add((self.partner.player.x, self.partner.player.y))
            if self.partner.current_path:
                 # On considère ses 2 prochaines étapes comme bloquées pour fluidifier
                 for step in self.partner.current_path[:2]:
                     obs.add(step)
        return obs

    def _aller_adjacent(self, type_cible: str, cible_aliment: Optional[str] = None):
        px, py = self.player.x, self.player.y
        stations = []
        
        # --- (Le début de la fonction reste identique pour récupérer les stations) ---
        if type_cible == "BAC":
            for pos, (nom_bac, _) in self.carte.bacs_config.items():
                if nom_bac == (cible_aliment or ""): stations.append(pos)
                if nom_bac == "legume" and cible_aliment in ["tomate", "salade", "aubergine", "courgette", "poivron"]:
                    stations.append(pos)
        elif type_cible == "DECOUPE": 
            stations = self.carte.pos_decoupes
        elif type_cible == "FOUR_OU_POELE":
            toutes = self.carte.pos_fours + self.carte.pos_poeles
            libres = [p for p in toutes if p not in self.game.cuissons]
            stations = libres or toutes 
        elif type_cible == "ASSEMBLAGE":
            stations = [self.current_assembly] if self.current_assembly else self.carte.pos_assemblages
        elif type_cible == "SERVICE": 
            stations = self.carte.pos_services

        # --- CORRECTION 2 : FILTRAGE INTELLIGENT AVEC DISTANCE ---
        stations_candidates = []
        partner_target = self.partner.target_station if self.partner else None
        partner_pos = (self.partner.player.x, self.partner.player.y) if self.partner else (999,999)

        for s in stations:
            # Si le partenaire vise cette station PRÉCISEMMENT
            if s == partner_target:
                # On calcule les distances
                dist_me = abs(px - s[0]) + abs(py - s[1])
                dist_partner = abs(partner_pos[0] - s[0]) + abs(partner_pos[1] - s[1])
                
                # Si je suis plus loin (ou égal mais j'ai un ID plus grand), je lui laisse
                if dist_me > dist_partner or (dist_me == dist_partner and self.agent_id > self.partner.agent_id):
                    continue # Je saute cette station, elle est "réservée"
            
            stations_candidates.append(s)

        # Si on a tout filtré (plus rien de dispo), on remet tout (on essaie quand même)
        if not stations_candidates:
            stations_candidates = stations

        obstacles = self._get_dynamic_obstacles()
        adj = cases_adjacentes_a_stations(self.carte, stations_candidates, obstacles)
        
        path = bfs_path(self.carte, (px, py), adj, obstacles)
        
        if path:
            self.current_path = path
            end_x, end_y = path[-1]
            # On assigne la target_station pour que l'autre agent puisse la voir
            closest_s = min(stations_candidates, key=lambda s: abs(s[0]-end_x) + abs(s[1]-end_y))
            self.target_station = closest_s
        else:
            self.current_path = []
            self.target_station = None

    def _suivre_chemin(self):
        if not self.current_path: return
        # On ignore la position actuelle si elle est encore en tête de liste
        if self.current_path[0] == (self.player.x, self.player.y): self.current_path.pop(0)
        if not self.current_path: return
        
        nx, ny = self.current_path.pop(0)
        dx, dy = nx - self.player.x, ny - self.player.y
        
        # Mouvement physique
        if abs(dx) + abs(dy) != 1: return # Mouvement invalide (diagonale ou saut)
        
        if dx == -1: self.player.gauche(self.carte)
        elif dx == 1: self.player.droite(self.carte)
        elif dy == -1: self.player.haut(self.carte)
        elif dy == 1: self.player.bas(self.carte)
        
        self._mark_progress()

    # --- ACTIONS ---
    def try_action(self) -> bool:
        self._ensure_bot_recette_valide() # être sûr que la recette est bonne avant de faire l'action
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
                # Si on est devant le mauvais bac, ne rien faire (évite de spammer)
                return False
            
            if nom_bac != wanted: return False
            p.item = prendre_au_bac(nom_bac)
            self._mark_progress(); return True

        # 2. DECOUPE
        # Vérification qu'on ne "vole" pas la découpe si quelqu'un d'autre l'utilise (géré par actions_en_cours dans main)
        # Mais ici on vérifie juste si c'est possible
        if p.item and p.est_adjacent_a(self.carte.pos_decoupes) and self.bot_recette:
            etat_requis = None
            for req in self.bot_recette.requis:
                if req.nom == p.item.nom:
                    etat_requis = req.etape_suivante(p.item.etat); break
            
            if etat_requis == EtatAliment.COUPE and p.item.etat == EtatAliment.SORTI_DU_BAC:
                from recette import TEMPS_COUPE
                duree = TEMPS_COUPE.get(p.item.nom, 1.0)
                pos_dec = p.est_adjacent_a(self.carte.pos_decoupes)
                
                # Vérifier si la station est occupée par l'autre agent (via main)
                occupied = False
                for agent, (act, apos, _, _, _) in self.game.actions_en_cours.items():
                    if act == "DECOUPE" and apos == pos_dec:
                        occupied = True; break
                
                if not occupied:
                    self.game.trigger_action_bloquante(self, "DECOUPE", pos_dec, p.item, duree)
                    return True

        # 3. CUISSON
        adj_four = p.est_adjacent_a(self.carte.pos_fours)
        adj_poele = p.est_adjacent_a(self.carte.pos_poeles)
        pos_station = adj_four or adj_poele

        # Récupérer item cuit
        if pos_station and p.item is None:
            slot = self.game.cuissons.get(pos_station)
            if slot:
                alim, t0, tfin = slot
                if self.game.get_time() >= tfin:
                    p.item = alim
                    del self.game.cuissons[pos_station]
                    self._mark_progress(); return True

        # Poser item à cuire
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

        # 4. ASSEMBLAGE (SECTION CORRIGÉE)
        adj_ass = p.est_adjacent_a(self.carte.pos_assemblages)
        if adj_ass:
            stock = self.carte.assemblage_stock.setdefault(adj_ass, [])
            
            # --- CORRECTION 2 : NETTOYAGE FORCÉ ---
            # Si le stock actuel sur la table ne correspond à AUCUNE recette active,
            # il faut le jeter AVANT d'essayer de poser quoi que ce soit.
            if stock:
                # Est-ce un plat final fini ?
                est_plat_final = (len(stock) == 1 and any(r.nom == stock[0].nom for r in self.game.recettes) and stock[0].etat == EtatAliment.CUIT)
                
                if not est_plat_final:
                    compatible_any = False
                    for r in self.game.recettes:
                        if items_completent_recette(stock, r): 
                            compatible_any = True 
                            break
                        flags = matched_flags_for_recipe(stock, r)
                        # Si tous les items présents sont utiles pour R
                        if sum(flags) == len(stock): 
                            compatible_any = True
                            break
                    
                    if not compatible_any:
                        stock.clear() # C'est une poubelle (recette annulée), on vide
                        self._mark_progress()
                        # On ne retourne pas True ici, car on veut peut-être poser notre item juste après

            # --- DÉPÔT / RÉCUPÉRATION ---
            
            # Cas A : C'est prêt pour MOI ?
            if self.bot_recette and p.item is None and items_completent_recette(stock, self.bot_recette):
                stock.clear()
                stock.append(Aliment(nom=self.bot_recette.nom, etat=EtatAliment.CUIT))
                self._mark_progress(); return True
            
            # Cas B : C'est prêt pour n'importe qui ?
            if p.item is None and stock:
                for r in self.game.recettes:
                    if items_completent_recette(stock, r):
                        stock.clear()
                        stock.append(Aliment(nom=r.nom, etat=EtatAliment.CUIT))
                        self._mark_progress(); return True

            # Cas C : Je pose mon ingrédient
            if p.item:
                tentative = stock + [p.item]
                recettes_possibles = recettes_possibles_pour_items(tentative, self.game.recettes)

                if recettes_possibles:
                    stock.append(p.item); p.item = None
                    for r in recettes_possibles:
                        if items_completent_recette(stock, r):
                            stock.clear()
                            stock.append(Aliment(nom=r.nom, etat=EtatAliment.CUIT))
                            break
                    self._mark_progress(); return True
                
                # --- CORRECTION 3 : STOCKAGE TAMPON ROBUSTE ---
                # Si la table est vide, je pose mon item (même si ma recette vient de changer)
                # Cela évite de garder un item inutile en main.
                if not stock:
                     stock.append(p.item); p.item = None
                     self._mark_progress(); return True
                     
                return False 

            # Cas D : Je récupère un plat fini
            if p.item is None and stock:
                if len(stock) == 1 and any(r.nom == stock[0].nom for r in self.game.recettes):
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