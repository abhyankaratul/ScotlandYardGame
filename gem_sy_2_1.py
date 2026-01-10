import pygame
import sys
import random
import math
import pandas as pd
from enum import Enum
from typing import Dict, List, Tuple, Optional, Set

# ======================
# CONSTANTS & CONFIG
# ======================
WIDTH, HEIGHT = 1300, 850
TOP_BAR_HEIGHT = 100
TICKET_BAR_HEIGHT = 120
NODE_RADIUS = 20
FPS = 60
MAX_TURNS = 24  
REVEAL_TURNS = [3, 8, 13, 18, 24] 

TRANSPORT_COLORS = {
    "taxi": (255, 215, 0),       
    "bus": (34, 139, 34),        
    "underground": (178, 34, 34), 
    "black": (50, 50, 50)        
}

class Ticket(Enum):
    TAXI = "taxi"
    BUS = "bus"
    UNDERGROUND = "underground"
    BLACK = "black"

class PlayerType(Enum):
    MRX = 1
    DETECTIVE = 2

# ======================
# MODELS
# ======================
class Player:
    def __init__(self, name: str, ptype: PlayerType, node: int, color: Tuple[int, int, int], tickets: Dict[Ticket, int], avatar_path: str):
        self.name = name
        self.type = ptype
        self.node = node
        self.color = color
        self.tickets = tickets
        self.avatar = self._load_avatar(avatar_path, color)
        self.mini_avatar = pygame.transform.scale(self.avatar, (25, 25))

    def _load_avatar(self, path: str, color: Tuple[int, int, int]):
        try:
            img = pygame.image.load(path).convert_alpha()
            return pygame.transform.scale(img, (60, 60))
        except:
            surf = pygame.Surface((60, 60), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (30, 30), 28)
            pygame.draw.circle(surf, (255, 255, 255), (30, 30), 28, 2)
            return surf

class Board:
    def __init__(self):
        self.nodes: Dict[int, Tuple[int, int]] = {}
        self.edges: Dict[int, List[List]] = {} 

    def add_node(self, i: int, pos: Tuple[int, int]):
        self.nodes[i] = pos
        self.edges[i] = []

    def add_edge(self, a: int, b: int, modes: Set[Ticket]):
        self.edges[a].append([b, modes])
        self.edges[b].append([a, modes])

# ======================
# GAME ENGINE
# ======================
class ScotlandYardGUI:
    def __init__(self, stations_csv: str, edges_csv: str):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Scotland Yard - Reveal and Hide Logic")
        self.clock = pygame.time.Clock()
        self.font_small = pygame.font.SysFont("Verdana", 12, bold=True)
        self.font_main = pygame.font.SysFont("Verdana", 18, bold=True)
        
        self.board = self._setup_board(stations_csv, edges_csv)
        self.restart_rect = pygame.Rect(WIDTH//2 - 100, HEIGHT - 80, 200, 50)
        self.reset_game()

    def _setup_board(self, stations_file: str, edges_file: str) -> Board:
        board_obj = Board()
        y_off_base = TOP_BAR_HEIGHT + TICKET_BAR_HEIGHT + 40
        st_df = pd.read_csv(stations_file)
        st_df.columns = st_df.columns.str.strip()
        for _, row in st_df.iterrows():
            board_obj.add_node(int(row['stn_id']), (int(row['x']), y_off_base + int(row['y_offset'])))
        
        ed_df = pd.read_csv(edges_file)
        ed_df.columns = ed_df.columns.str.strip()
        for _, row in ed_df.iterrows():
            s1, s2 = int(row['stn_1']), int(row['stn_2'])
            if s1 not in board_obj.nodes or s2 not in board_obj.nodes: continue
            modes = set()
            if int(row.get('taxi', 0)) == 1: modes.add(Ticket.TAXI)
            if int(row.get('bus', 0)) == 1: modes.add(Ticket.BUS)
            if int(row.get('underground', 0)) == 1: modes.add(Ticket.UNDERGROUND)
            
            if modes:
                found = False
                for edge in board_obj.edges[s1]:
                    if edge[0] == s2:
                        edge[1].update(modes)
                        found = True
                if not found: board_obj.add_edge(s1, s2, modes)
        return board_obj

    def reset_game(self):
        all_nodes = list(self.board.nodes.keys())
        starts = random.sample(all_nodes, 3)
        self.players = [
            Player("Mr. X", PlayerType.MRX, starts[0], (40, 40, 40), {Ticket.TAXI:12, Ticket.BUS:8, Ticket.UNDERGROUND:4}, "mr_x.png"),
            Player("Sherlock", PlayerType.DETECTIVE, starts[1], (40, 80, 200), {Ticket.TAXI:10, Ticket.BUS:8, Ticket.UNDERGROUND:4}, "detective_a.png"),
            Player("Katrina", PlayerType.DETECTIVE, starts[2], (200, 40, 200), {Ticket.TAXI:10, Ticket.BUS:8, Ticket.UNDERGROUND:4}, "detective_b.png"),
        ]
        self.player_map = {p.name: p for p in self.players} 
        self.current_idx = 0
        self.turn_count = 1
        self.game_over = False
        self.game_over_msg = ""
        self.move_history = []
        self.scroll_y = 0

    def draw_curve(self, color, start, end, strength):
        mid_x, mid_y = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
        dx, dy = end[0] - start[0], end[1] - start[1]
        dist = math.sqrt(dx**2 + dy**2)
        if dist == 0: return
        nx, ny = -dy / dist, dx / dist
        control = (mid_x + nx * strength, mid_y + ny * strength)
        pts = [((1-t/20)**2 * start[0] + 2*(1-t/20)*(t/20) * control[0] + (t/20)**2 * end[0],
                (1-t/20)**2 * start[1] + 2*(1-t/20)*(t/20) * control[1] + (t/20)**2 * end[1]) for t in range(21)]
        pygame.draw.lines(self.screen, color, False, pts, 5)

    def draw_board_elements(self):
        processed = set()
        for s1_id, connections in self.board.edges.items():
            for s2_id, modes in connections:
                pair = tuple(sorted((s1_id, s2_id)))
                if pair in processed: continue
                processed.add(pair)
                p1, p2 = self.board.nodes[s1_id], self.board.nodes[s2_id]
                m_list = sorted(list(modes), key=lambda x: x.value)
                for i, m in enumerate(m_list):
                    if m == Ticket.TAXI:
                        pygame.draw.line(self.screen, TRANSPORT_COLORS[m.value], p1, p2, 5)
                    else:
                        strength = (i - (len(m_list)-1)/2) * 60
                        self.draw_curve(TRANSPORT_COLORS[m.value], p1, p2, strength if strength != 0 else 45)

        for nid, pos in self.board.nodes.items():
            all_m = set()
            for _, m_set in self.board.edges[nid]: all_m.update(m_set)
            f_clr = (255,100,100) if Ticket.UNDERGROUND in all_m else (144,238,144) if Ticket.BUS in all_m else (255,255,150)
            pygame.draw.circle(self.screen, f_clr, pos, NODE_RADIUS)
            pygame.draw.circle(self.screen, (50,50,50), pos, NODE_RADIUS, 2)
            lbl = self.font_small.render(str(nid), True, (0,0,0))
            self.screen.blit(lbl, (pos[0]-lbl.get_width()//2, pos[1]-lbl.get_height()//2))

    def draw_ui(self):
        pygame.draw.rect(self.screen, (220, 220, 220), (0, 0, WIDTH, TOP_BAR_HEIGHT))
        for i, p in enumerate(self.players):
            x = 30 + (i * 300)
            if i == self.current_idx:
                pygame.draw.rect(self.screen, (255, 215, 0), (x-5, 5, 280, 90), 4, border_radius=10)
            self.screen.blit(p.avatar, (x, 20))
            self.screen.blit(self.font_main.render(p.name, True, (30, 30, 30)), (x+70, 35))
        
        pygame.draw.rect(self.screen, (255, 255, 255), (0, TOP_BAR_HEIGHT, WIDTH, TICKET_BAR_HEIGHT))
        y = TOP_BAR_HEIGHT + 15
        for p in self.players:
            t_str = " | ".join([f"{t.value.upper()}: {p.tickets[t]}" for t in p.tickets if t != Ticket.BLACK])
            self.screen.blit(self.font_small.render(f"{p.name}: {t_str}", True, (70, 70, 70)), (30, y))
            y += 35

    def handle_click(self, pos):
        if self.game_over:
            if self.restart_rect.collidepoint(pos): self.reset_game()
            return
            
        p = self.players[self.current_idx]
        det_positions = [d.node for d in self.players if d.type == PlayerType.DETECTIVE]

        if p.type == PlayerType.MRX:
            valid_moves = []
            for d, modes in self.board.edges[p.node]:
                if d not in det_positions: 
                    for m in modes:
                        if p.tickets[m] > 0:
                            valid_moves.append((d, m))
            
            if not valid_moves:
                self.game_over, self.game_over_msg = True, "Detectives Win! Mr. X is trapped."
            else:
                dest, ticket = random.choice(valid_moves)
                p.tickets[ticket] -= 1
                self.move_history.append({"turn": self.turn_count, "player": p.name, "from": p.node, "to": dest})
                p.node = dest
                self.next_turn()
        else:
            for nid, npos in self.board.nodes.items():
                if math.hypot(pos[0]-npos[0], pos[1]-npos[1]) < NODE_RADIUS:
                    for d, modes in self.board.edges[p.node]:
                        if d == nid:
                            usable = [m for m in modes if p.tickets[m] > 0]
                            if usable:
                                p.tickets[usable[0]] -= 1
                                self.move_history.append({"turn": self.turn_count, "player": p.name, "from": p.node, "to": nid})
                                p.node = nid
                                self.next_turn()
                                return

    def next_turn(self):
        mrx = self.players[0]
        detectives = [p for p in self.players if p.type == PlayerType.DETECTIVE]

        if any(d.node == mrx.node for d in detectives):
            self.game_over, self.game_over_msg = True, "Detectives Win! Mr. X Caught."
            return

        # Win Condition: Immobilized Detective
        for d in detectives:
            station_modes = set()
            for _, modes in self.board.edges[d.node]:
                station_modes.update(modes)
            if not any(d.tickets[m] > 0 for m in station_modes):
                self.game_over, self.game_over_msg = True, f"Mr. X Wins! {d.name} is stranded."
                return

        self.current_idx = (self.current_idx + 1) % len(self.players)
        if self.current_idx == 0:
            self.turn_count += 1
            if self.turn_count > MAX_TURNS: 
                self.game_over, self.game_over_msg = True, "Mr. X Escaped!"

    def draw_history_screen(self):
        self.screen.fill((30, 30, 35))
        title = self.font_main.render(f"GAME OVER: {self.game_over_msg}", True, (255, 255, 255))
        self.screen.blit(title, (WIDTH//2 - title.get_width()//2, 30))
        
        headers = ["Turn", "Player", "From", "To"]
        x_pos = [150, 350, 600, 850]
        for i, h in enumerate(headers):
            self.screen.blit(self.font_main.render(h, True, (255, 215, 0)), (x_pos[i], 80))
        
        view_h = HEIGHT - 220
        for i, m in enumerate(self.move_history):
            y_off = (i * 35) - self.scroll_y
            if 0 <= y_off <= view_h:
                y = 120 + y_off
                p_obj = self.player_map.get(m["player"])
                self.screen.blit(self.font_small.render(str(m["turn"]), True, (200, 200, 200)), (150, y))
                if p_obj:
                    self.screen.blit(p_obj.mini_avatar, (315, y - 5))
                self.screen.blit(self.font_small.render(m["player"], True, (200, 200, 200)), (350, y))
                self.screen.blit(self.font_small.render(str(m["from"]), True, (200, 200, 200)), (600, y))
                self.screen.blit(self.font_small.render(str(m["to"]), True, (200, 200, 200)), (850, y))

        pygame.draw.rect(self.screen, (34, 139, 34), self.restart_rect, border_radius=10)
        btn = self.font_main.render("RESTART", True, (255, 255, 255))
        self.screen.blit(btn, (self.restart_rect.centerx-btn.get_width()//2, self.restart_rect.centery-btn.get_height()//2))

    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT: pygame.quit(); sys.exit()
                if e.type == pygame.MOUSEWHEEL and self.game_over: self.scroll_y = max(0, self.scroll_y - e.y * 30)
                if e.type == pygame.MOUSEBUTTONDOWN: self.handle_click(e.pos)
            
            if not self.game_over:
                self.screen.fill((240, 240, 240))
                self.draw_ui()
                self.draw_board_elements()
                for i, p in enumerate(self.players):
                    # REVEAL LOGIC UPDATE:
                    # Mr. X is visible ONLY if it is a reveal turn AND it is currently HIS turn (current_idx == 0).
                    # The moment he moves, current_idx becomes 1, and he will vanish.
                    is_visible = p.type != PlayerType.MRX or (self.turn_count in REVEAL_TURNS and self.current_idx == 0)
                    
                    if is_visible:
                        pygame.draw.circle(self.screen, p.color, self.board.nodes[p.node], 16)
                        pygame.draw.circle(self.screen, (255,255,255), self.board.nodes[p.node], 16, 2)
            else: self.draw_history_screen()
            pygame.display.flip(); self.clock.tick(FPS)

if __name__ == "__main__":
    game = ScotlandYardGUI("stations2.csv", "edges2.csv")
    game.run()
