import random
from collections import deque

# Codes blocs
SOL, BAC, FOUR, DECOUPE, SERVICE, JOUEUR, MUR, POELE, ASSEMBLAGE = 0, 1, 2, 3, 4, 5, 6, 7, 8


# -------------------------------------------------------------------
# Utils
# -------------------------------------------------------------------
def voisins(x, y, rows, cols):
    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        nx, ny = x + dx, y + dy
        if 0 <= nx < cols and 0 <= ny < rows:
            yield nx, ny


def zone_connexe(grid):
    rows, cols = len(grid), len(grid[0])

    start = None
    for y in range(rows):
        for x in range(cols):
            if grid[y][x] == SOL:
                start = (x, y)
                break
        if start:
            break

    if not start:
        return False

    q = deque([start])
    visited = {start}

    while q:
        x, y = q.popleft()
        for nx, ny in voisins(x, y, rows, cols):
            if grid[ny][nx] == SOL and (nx, ny) not in visited:
                visited.add((nx, ny))
                q.append((nx, ny))

    total_sol = sum(row.count(SOL) for row in grid)
    return len(visited) == total_sol


# -------------------------------------------------------------------
# Vérifier qu’il n’existe pas de couloirs d’épaisseur 1
# -------------------------------------------------------------------
def check_min_width(grid):
    """
    Retourne False s’il existe une case SOL prise en sandwich
    entre 2 blocs/murs horizontalement ou verticalement.
    Donc on impose des couloirs de largeur >= 2 partout.
    """
    rows, cols = len(grid), len(grid[0])

    for y in range(rows):
        for x in range(cols):
            if grid[y][x] != SOL:
                continue

            # bloc à gauche / droite ?
            left_block  = (x - 1 >= 0       and grid[y][x-1] != SOL)
            right_block = (x + 1 < cols     and grid[y][x+1] != SOL)
            up_block    = (y - 1 >= 0       and grid[y-1][x] != SOL)
            down_block  = (y + 1 < rows     and grid[y+1][x] != SOL)

            # couloir vertical de largeur 1
            if left_block and right_block:
                return False

            # couloir horizontal de largeur 1
            if up_block and down_block:
                return False

    return True


# -------------------------------------------------------------------
# Détection motifs en U et en C pour éviter les pièges
# -------------------------------------------------------------------
def has_u_shape(grid):
    rows, cols = len(grid), len(grid[0])
    for y in range(1, rows-1):
        for x in range(1, cols-1):

            if grid[y][x] == SOL:

                # U vertical (bloc au-dessus et en-dessous, ouverture horizontale serrée)
                if (grid[y-1][x] != SOL and
                    grid[y+1][x] != SOL and
                    (grid[y][x-1] != SOL or grid[y][x+1] != SOL)):
                    return True

                # U horizontal (bloc à gauche et à droite, ouverture verticale serrée)
                if (grid[y][x-1] != SOL and
                    grid[y][x+1] != SOL and
                    (grid[y-1][x] != SOL or grid[y+1][x] != SOL)):
                    return True

    return False


# -------------------------------------------------------------------
# Vérification de la forme d’un amas de blocs
#  -> soit une ligne 1×N, soit un carré 2×2, soit un bloc seul
# -------------------------------------------------------------------
def component_shape_ok(grid, start_x, start_y):
    """
    On regarde la composante connexe de blocs (hors murs) contenant (start_x, start_y).
    Valide si :
      - c’est une ligne (1×N) sans trous
      - ou un 2×2 plein
    Sinon -> False.
    """
    rows, cols = len(grid), len(grid[0])

    # On ne considère que les blocs "stations", pas les murs ni le sol
    if grid[start_y][start_x] == SOL or grid[start_y][start_x] == MUR:
        return True  # rien à vérifier

    stack = [(start_x, start_y)]
    visited = {(start_x, start_y)}
    coords = []

    while stack:
        x, y = stack.pop()
        if grid[y][x] == SOL or grid[y][x] == MUR:
            continue

        coords.append((x, y))

        for nx, ny in voisins(x, y, rows, cols):
            if (nx, ny) in visited:
                continue
            if grid[ny][nx] == SOL or grid[ny][nx] == MUR:
                continue
            visited.add((nx, ny))
            stack.append((nx, ny))

    if not coords:
        return True

    xs = [x for x, _ in coords]
    ys = [y for _, y in coords]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    width = max_x - min_x + 1
    height = max_y - min_y + 1
    area = len(coords)

    # Cas ligne (1×N ou N×1)
    if width == 1 or height == 1:
        # La composante doit remplir toute la bounding box
        expected = max(width, height)
        return area == expected

    # Cas carré 2×2 plein
    if width == 2 and height == 2:
        return area == 4

    # Toute autre forme/tailles interdites
    return False


# -------------------------------------------------------------------
# Fonctions de vérification des groupes
# -------------------------------------------------------------------
def can_place_line(grid, x, y, length, horizontal=True):
    rows, cols = len(grid), len(grid[0])

    coords = []
    for i in range(length):
        xx = x + i if horizontal else x
        yy = y if horizontal else y + i
        # on évite les bords (1..cols-2 / 1..rows-2)
        if not (1 <= xx < cols-1 and 1 <= yy < rows-1):
            return None
        if grid[yy][xx] != SOL:
            return None
        coords.append((xx, yy))

    return coords


def can_place_square2(grid, x, y):
    rows, cols = len(grid), len(grid[0])

    # interdit contre un mur (on laisse au moins 1 case de marge)
    if x <= 1 or x >= cols-3 or y <= 1 or y >= rows-3:
        return None

    coords = [(x, y), (x+1, y), (x, y+1), (x+1, y+1)]

    for (xx, yy) in coords:
        if grid[yy][xx] != SOL:
            return None

    return coords


# -------------------------------------------------------------------
# Placement d’un groupe (lignes + carrés 2×2)
# -------------------------------------------------------------------
def place_group(grid, block_type):
    rows, cols = len(grid), len(grid[0])

    for _ in range(300):

        shape = random.choice(["lineH", "lineV", "square"])
        length = random.choice([1, 2, 3, 4])  # mix équilibré

        x = random.randint(1, cols-2)
        y = random.randint(1, rows-2)

        if shape == "square":
            coords = can_place_square2(grid, x, y)
        elif shape == "lineH":
            coords = can_place_line(grid, x, y, length, True)
        else:
            coords = can_place_line(grid, x, y, length, False)

        if not coords:
            continue

        # placement temporaire
        for xx, yy in coords:
            grid[yy][xx] = block_type

        # vérif forme de l’amas de blocs que l’on vient (éventuellement) d’agrandir
        if not component_shape_ok(grid, coords[0][0], coords[0][1]):
            # revert
            for xx, yy in coords:
                grid[yy][xx] = SOL
            continue

        # vérifications globales
        if zone_connexe(grid) and check_min_width(grid) and not has_u_shape(grid):
            return True

        # sinon revert
        for xx, yy in coords:
            grid[yy][xx] = SOL

    return False

def place_two_adjacent_services(grid):
    """
    Place 2 blocs SERVICE adjacents (horizontal OU vertical)
    et collés à un mur.
    Retourne True si succès, False sinon.
    """
    rows, cols = len(grid), len(grid[0])
    candidates = []

    # On parcourt l'intérieur de la map (1 .. rows-2 / 1 .. cols-2)
    for y in range(1, rows - 1):
        for x in range(1, cols - 1):
            if grid[y][x] != SOL:
                continue

            # --- Bloc horizontal : (x, y) et (x+1, y)
            if x + 1 <= cols - 2 and grid[y][x + 1] == SOL:
                if (is_against_wall(grid, x, y)
                        and is_against_wall(grid, x + 1, y)):
                    candidates.append(((x, y), (x + 1, y)))

            # --- Bloc vertical : (x, y) et (x, y+1)
            if y + 1 <= rows - 2 and grid[y + 1][x] == SOL:
                if (is_against_wall(grid, x, y)
                        and is_against_wall(grid, x, y + 1)):
                    candidates.append(((x, y), (x, y + 1)))

    if not candidates:
        return False

    (x1, y1), (x2, y2) = random.choice(candidates)
    grid[y1][x1] = SERVICE
    grid[y2][x2] = SERVICE
    return True


def is_against_wall(grid, x, y):
    rows, cols = len(grid), len(grid[0])
    for nx, ny in voisins(x, y, rows, cols):
        if grid[ny][nx] == MUR:
            return True
    return False

# -------------------------------------------------------------------
# Générateur principal
# -------------------------------------------------------------------
def generate_map(
        rows=8, cols=12,
        nb_bacs=5,
        nb_fours=2,
        nb_decoupes=2,
        nb_services=2,
        nb_assemblages=2,
        nb_poeles=2):

    # Par sécurité, on impose qu'il y ait au moins 2 services
    if nb_services < 2:
        raise ValueError("nb_services doit être >= 2 pour placer 2 blocs adjacents")

    while True:

        # -----------------------
        # 1) Base + murs
        # -----------------------
        grid = [[SOL for _ in range(cols)] for _ in range(rows)]
        for x in range(cols):
            grid[0][x] = grid[rows-1][x] = MUR
        for y in range(rows):
            grid[y][0] = grid[y][cols-1] = MUR

        # -----------------------
        # 2) Placer les 2 services adjacents
        # -----------------------
        if not place_two_adjacent_services(grid):
            # Si on n'y arrive pas, on recommence une map
            continue

        # Nombre de services restant à placer avec l'algo normal
        remaining_services = nb_services - 2

        # -----------------------
        # 3) Préparer la liste des autres blocs à placer
        # -----------------------
        blocks = (
            [SERVICE]      * remaining_services +
            [ASSEMBLAGE]   * nb_assemblages +
            [BAC]          * nb_bacs +
            [FOUR]         * nb_fours +
            [DECOUPE]      * nb_decoupes +
            [POELE]        * nb_poeles
        )
        random.shuffle(blocks)

        ok = True
        for block in blocks:
            if not place_group(grid, block):
                ok = False
                break

        if not ok:
            # on recommence une génération complète
            continue

        # -----------------------
        # 4) Spawns des joueurs
        # -----------------------
        free = [(x, y) for y in range(rows) for x in range(cols) if grid[y][x] == SOL]
        if len(free) < 2:
            continue

        p1 = random.choice(free)
        free.remove(p1)
        p2 = random.choice(free)

        return grid, p1, p2
