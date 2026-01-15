import pygame
import sys
import random
import math
import pandas as pd
import heapq
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

# Distinct High-Contrast Colors
TRANSPORT_COLORS = {
    "taxi": (255, 215, 0),       
    "bus": (34, 139, 34),        
    "underground": (178, 34, 34), 
    "black": (50, 50, 50)        
}

HIGHLIGHT_COLOR = (0, 255, 255) # Electric Cyan
HIGHLIGHT_SECONDARY = (255, 0, 255) # Neon Magenta

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
        pygame.display.set_caption("Scotland Yard")
        self.clock = pygame.time.Clock()
        self.font_small = pygame.font.SysFont("Verdana", 12, bold=True)
        self.font_main = pygame.font.SysFont("Verdana", 18, bold=True)
        
        self.board = self._setup_board(stations_csv, edges_csv)
        self.restart_rect = pygame.Rect(WIDTH//2 - 100, HEIGHT - 80, 200, 50)
        
        # Difficulty Buttons
        self.easy_rect = pygame.Rect(WIDTH//2 - 315, HEIGHT//2, 200, 60)
        self.med_rect = pygame.Rect(WIDTH//2 - 100, HEIGHT//2, 200, 60)
        self.hard_rect = pygame.Rect(WIDTH//2 + 115, HEIGHT//2, 200, 60)
        
        self.difficulty = None 
        self.selected_node = None
        self.pending_tickets = []
        self.pulse_timer = 0 # For pulsing animation
        
        #For sound effects
        pygame.mixer.init()
        try:
            # A lighter "tick" or "notification" sound for Detectives
            self.det_move_sound = pygame.mixer.Sound("pop_click.mp3")
            # A whoosh sound when mr. x makes a move
            self.mrx_move_sound = pygame.mixer.Sound("whoosh.mp3") #Ensure you have a file
            # Error sound
            self.error_sound = pygame.mixer.Sound("error.mp3") # Ensure you have an error.wav file
            # Game end sounds
            self.mrx_escapes_sound = pygame.mixer.Sound('mrx_escapes.mp3')
            self.sherlock_catches_mrx_sound = pygame.mixer.Sound('sherlock_catches_x.mp3')
            self.katrina_catches_mrx_sound = pygame.mixer.Sound('katrina_catches_x.mp3')
            self.sherlock_stuck_sound = pygame.mixer.Sound('sherlock_stuck.mp3')
            self.katrina_stuck_sound = pygame.mixer.Sound('katrina_stuck.mp3')
            self.mrx_stuck_sound = pygame.mixer.Sound('mrx_stuck.mp3')
        except:
            self.det_move_sound = None
            self.mrx_move_sound = None
            self.error_sound = None
            self.mrx_escapes_sound = None
            self.sherlock_catches_mrx_sound = None
            self.katrina_catches_mrx_sound = None
            self.sherlock_stuck_sound = None
            self.katrina_stuck_sound = None
            self.mrx_stuck_sound = None
        
        self.reset_game()

    def _setup_board(self, stations_file: str, edges_file: str) -> Board:
        board_obj = Board()
        y_off_base = TOP_BAR_HEIGHT + TICKET_BAR_HEIGHT + 40
        try:
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
        except: pass
        return board_obj

    def reset_game(self):
        self.difficulty = None
        self.selected_node = None
        self.pending_tickets = []
        all_nodes = list(self.board.nodes.keys())
        starts = random.sample(all_nodes, 3) if len(all_nodes) >= 3 else [1,2,3]
        self.players = [
            Player("Mr. X", PlayerType.MRX, starts[0], (40, 40, 40), {Ticket.TAXI:12, Ticket.BUS:8, Ticket.UNDERGROUND:4}, "mr_x.png"),
            Player("Sherlock", PlayerType.DETECTIVE, starts[1], (40, 80, 200), {Ticket.TAXI:10, Ticket.BUS:8, Ticket.UNDERGROUND:4}, "detective_a.png"),
            Player("Katrina", PlayerType.DETECTIVE, starts[2], (200, 40, 200), {Ticket.TAXI:10, Ticket.BUS:8, Ticket.UNDERGROUND:4}, "detective_b.png"),
        ]
        self.player_map = {p.name: p for p in self.players} 
        self.current_idx, self.turn_count = 0, 1
        self.game_over, self.game_over_msg = False, ""
        self.move_history, self.scroll_y = [], 0
        self.mrx_log = []

    def dijkstra_dist(self, start_node):
        distances = {node: float('inf') for node in self.board.nodes}
        distances[start_node] = 0
        pq = [(0, start_node)]
        while pq:
            curr_d, u = heapq.heappop(pq)
            if curr_d > distances[u]: continue
            for v, modes in self.board.edges[u]:
                if curr_d + 1 < distances[v]:
                    distances[v] = curr_d + 1
                    heapq.heappush(pq, (distances[v], v))
        return distances

    def get_hard_ai_move(self, valid_moves):
        det_nodes = [p.node for p in self.players if p.type == PlayerType.DETECTIVE]
        det_dist_maps = [self.dijkstra_dist(dn) for dn in det_nodes]
        mrx = self.players[0]
        best_move, best_score = None, -float('inf')
        for dest, ticket in valid_moves:
            safety_score = min(d_map[dest] for d_map in det_dist_maps)
            exits = self.board.edges[dest]
            ticket_penalty = 0
            if mrx.tickets[Ticket.TAXI] < 4:
                non_taxi = sum(1 for _, m_set in exits if any(m != Ticket.TAXI for m in m_set))
                if non_taxi == 0: ticket_penalty = 40 
            total_score = (safety_score * 20) + (len(exits) * 2) - ticket_penalty
            if total_score > best_score:
                best_score, best_move = total_score, (dest, ticket)
        return best_move if best_move else random.choice(valid_moves)

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
        p = self.players[self.current_idx]
        det_pos = [d.node for d in self.players if d.type == PlayerType.DETECTIVE]
        
        # Determine valid targets for pulsing highlight
        valid_targets = []
        if not self.game_over and p.type == PlayerType.DETECTIVE and not self.pending_tickets:
            for d, modes in self.board.edges[p.node]:
                if d not in det_pos and any(p.tickets[m] > 0 for m in modes):
                    valid_targets.append(d)

        # Pulse animation values
        self.pulse_timer += 0.1
        pulse_width = int(abs(math.sin(self.pulse_timer)) * 6) + 4 # Thickens/thins the ring

        # Draw Edges
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

        # Draw Nodes and Highlights
        for nid, pos in self.board.nodes.items():
            if nid in valid_targets:
                # Primary Glow Ring (Cyan)
                pygame.draw.circle(self.screen, HIGHLIGHT_COLOR, pos, NODE_RADIUS + 8, pulse_width)
                # Outer Glow Ring (Magenta)
                pygame.draw.circle(self.screen, HIGHLIGHT_SECONDARY, pos, NODE_RADIUS + 12, 2)

            all_m = set()
            for _, m_set in self.board.edges[nid]: all_m.update(m_set)
            f_clr = (255,100,100) if Ticket.UNDERGROUND in all_m else (144,238,144) if Ticket.BUS in all_m else (255,255,150)
            pygame.draw.circle(self.screen, f_clr, pos, NODE_RADIUS)
            pygame.draw.circle(self.screen, (50,50,50), pos, NODE_RADIUS, 2)
            lbl = self.font_small.render(str(nid), True, (0,0,0))
            self.screen.blit(lbl, (pos[0]-lbl.get_width()//2, pos[1]-lbl.get_height()//2))

    def draw_ticket_selector(self):
        if not self.pending_tickets: return
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        prompt = self.font_main.render("Select Mode of Transport:", True, (255, 255, 255))
        self.screen.blit(prompt, (WIDTH//2 - prompt.get_width()//2, HEIGHT//2 - 100))
        for ticket, rect in self.pending_tickets:
            pygame.draw.rect(self.screen, TRANSPORT_COLORS[ticket.value], rect, border_radius=10)
            pygame.draw.rect(self.screen, (255, 255, 255), rect, 3, border_radius=10)
            txt = self.font_main.render(ticket.value.upper(), True, (255, 255, 255))
            self.screen.blit(txt, (rect.centerx - txt.get_width()//2, rect.centery - txt.get_height()//2))

    def draw_ui(self):
        # Top background
        pygame.draw.rect(self.screen, (220, 220, 220), (0, 0, WIDTH, TOP_BAR_HEIGHT))
        
        # Player Avatars and Selection Highlight
        for i, p in enumerate(self.players):
            x = 30 + (i * 300)
            if i == self.current_idx:
                pygame.draw.rect(self.screen, HIGHLIGHT_COLOR, (x-5, 5, 280, 90), 4, border_radius=10)
            self.screen.blit(p.avatar, (x, 20))
            self.screen.blit(self.font_main.render(p.name, True, (30, 30, 30)), (x+70, 35))
            
        # Ticket Bar background
        pygame.draw.rect(self.screen, (255, 255, 255), (0, TOP_BAR_HEIGHT, WIDTH, TICKET_BAR_HEIGHT))
        
        y = TOP_BAR_HEIGHT + 15
        for p in self.players:
            # Start drawing labels for each player
            label = self.font_small.render(f"{p.name}: ", True, (70, 70, 70))
            self.screen.blit(label, (30, y))
            current_x = 30 + label.get_width()
            
            for t_type, count in p.tickets.items():
                # Define warning color (Bright Red) if tickets <= 2
                is_low = count <= 2 and p.type == PlayerType.DETECTIVE
                text_color = (220, 0, 0) if is_low else (70, 70, 70)
                
                # Create the ticket string
                t_str = f"{t_type.value.upper()}: {count}  "
                
                # If low, draw a small "glow" behind the text for extra visibility
                if is_low:
                    glow = self.font_small.render(t_str, True, (255, 200, 200))
                    self.screen.blit(glow, (current_x + 1, y + 1))
                
                # Render the actual ticket text
                t_render = self.font_small.render(t_str, True, text_color)
                self.screen.blit(t_render, (current_x, y))
                
                # Advance X position for the next ticket type
                current_x += t_render.get_width() + 10
                
            y += 35 # Move to the next player's row

    def handle_click(self, pos):
        if self.difficulty is None:
            if self.easy_rect.collidepoint(pos): self.difficulty = 'easy'
            elif self.med_rect.collidepoint(pos): self.difficulty = 'medium'
            elif self.hard_rect.collidepoint(pos): self.difficulty = 'hard'
            return
        if self.game_over:
            if self.restart_rect.collidepoint(pos): self.reset_game()
            return

        p = self.players[self.current_idx]
        if self.pending_tickets:
            for ticket, rect in self.pending_tickets:
                if rect.collidepoint(pos):
                    self.execute_move(p, self.selected_node, ticket)
                    self.pending_tickets, self.selected_node = [], None
                    return
            return

        if p.type == PlayerType.MRX:
            det_pos = [d.node for d in self.players if d.type == PlayerType.DETECTIVE]
            valid = [(d, m) for d, modes in self.board.edges[p.node] if d not in det_pos for m in modes if p.tickets[m] > 0]
            if not valid: self.game_over, self.game_over_msg = True, "Mr. X Trapped!"
            else:
                dest, _ = self.get_hard_ai_move(valid) if self.difficulty == 'hard' else random.choice(valid)
                possible_t = [m for d, modes in self.board.edges[p.node] if d == dest for m in modes if p.tickets[m] > 0]
                best_ticket = max(possible_t, key=lambda t: p.tickets[t])
                self.execute_move(p, dest, best_ticket)
        else:
            det_pos = [d.node for d in self.players if d.type == PlayerType.DETECTIVE]
            clicked_node = None
            
            # Check if any node was clicked
            for nid, npos in self.board.nodes.items():
                if math.hypot(pos[0]-npos[0], pos[1]-npos[1]) < NODE_RADIUS + 5:
                    clicked_node = nid
                    break
            
            if clicked_node is not None:
                # Find if there is a connection to this node
                connection = next((modes for d, modes in self.board.edges[p.node] if d == clicked_node), None)
                
                # VALID MOVE LOGIC
                if connection and clicked_node not in det_pos:
                    usable = [m for m in connection if p.tickets[m] > 0]
                    if len(usable) == 1: 
                        self.execute_move(p, clicked_node, usable[0])
                    elif len(usable) > 1:
                        self.selected_node = clicked_node
                        start_x = WIDTH//2 - (len(usable) * 110) // 2
                        self.pending_tickets = [(t, pygame.Rect(start_x + i*120, HEIGHT//2 - 30, 100, 60)) 
                                               for i, t in enumerate(usable)]
                    else:
                        # Case: Connection exists but NO TICKETS
                        if self.error_sound: self.error_sound.play()
                else:
                    # Case: NO CONNECTION or NODE OCCUPIED
                    if self.error_sound: self.error_sound.play()

    def execute_move(self, player, dest, ticket):
        player.tickets[ticket] -= 1
        self.move_history.append({
            "turn": self.turn_count, 
            "player": player.name, 
            "from": player.node, 
            "to": dest, 
            "ticket": ticket.value
            })
        
        # Log Logic and sound for Mr. X
        if player.type == PlayerType.MRX:
            # Play the whoosh sound effect
            if self.mrx_move_sound:
                self.mrx_move_sound.play()
            if self.turn_count in REVEAL_TURNS:
                # Reset log at a reveal turn and start with the station number
                self.mrx_log = [str(player.node)]
                self.mrx_log.append(ticket.value.upper())
            elif self.mrx_log:
                # Otherwise, append the ticket used
                self.mrx_log.append(ticket.value.upper())
        else:
            # Play the "tick" sound for detectives
            if self.det_move_sound:
                self.det_move_sound.play()
        
        player.node = dest
        self.next_turn()

    def is_player_stuck(self, player):
        """Checks if a player has any valid moves left based on their tickets."""
        # Detectives can't occupy the same node as another detective
        det_pos = [d.node for d in self.players if d.type == PlayerType.DETECTIVE and d != player]
        
        for dest, modes in self.board.edges[player.node]:
            if dest not in det_pos:
                # Check if they have at least one ticket for any mode leading to this destination
                if any(player.tickets[m] > 0 for m in modes):
                    return False # Found at least one valid move
        return True

    def next_turn(self):
        # 1. Capture Check (Detective lands on Mr. X)
        mrxnode=self.players[0].node
        for i in range(1,len(self.players)):
            if(self.players[i].node==mrxnode):
                #Detective caught Mr. X
                self.game_over, self.game_over_msg = True, f"Mr. X is arrested by {self.players[i].name}!"
                if(i==1):
                    if (self.sherlock_catches_mrx_sound): self.sherlock_catches_mrx_sound.play()
                elif (self.katrina_catches_mrx_sound):
                    self.katrina_catches_mrx_sound.play()
        
        # 2. Advance to next player
        self.current_idx = (self.current_idx + 1) % len(self.players)
        
        # 3. Stuck Detective Check (Mr. X wins if a detective is stranded)
        next_player = self.players[self.current_idx]
        if next_player.type == PlayerType.DETECTIVE:
            if self.is_player_stuck(next_player):
                if next_player.name==self.players[1].name:
                    self.game_over, self.game_over_msg = True, f"Mr. X Wins: {next_player.name} is out of tickets and stuck!"
                    if self.sherlock_stuck_sound: self.sherlock_stuck_sound.play()
                elif next_player.name==self.players[2].name:
                    self.game_over, self.game_over_msg = True, f"Mr. X Wins: {next_player.name} is out of tickets and stuck!"
                    if self.katrina_stuck_sound: self.katrina_stuck_sound.play()
                else:
                    self.game_over, self.game_over_msg = True, f"Mr. X Lost: {next_player.name} is out of tickets and stuck!"
                    if self.mrx_stuck_sound: self.mrx_stuck_sound.play()
                return

        # 4. Turn Count Check (End of round)
        if self.current_idx == 0:
            self.turn_count += 1
            if self.turn_count > MAX_TURNS: 
                self.game_over, self.game_over_msg = True, "Mr. X Escaped!"

    def draw_history_screen(self):
        self.screen.fill((30, 30, 35))
        title = self.font_main.render(f"GAME OVER: {self.game_over_msg}", True, (255, 255, 255))
        self.screen.blit(title, (WIDTH//2 - title.get_width()//2, 30))
        headers = ["Turn", "Player", "From", "To", "Ticket"]
        x_pos = [100, 250, 450, 650, 850]
        for i, h in enumerate(headers): self.screen.blit(self.font_main.render(h, True, HIGHLIGHT_COLOR), (x_pos[i], 80))
        view_h = HEIGHT - 220
        for i, m in enumerate(self.move_history):
            y_off = (i * 35) - self.scroll_y
            if 0 <= y_off <= view_h:
                y = 120 + y_off
                p_obj = self.player_map.get(m["player"])
                clr = (200, 200, 200)
                self.screen.blit(self.font_small.render(str(m["turn"]), True, clr), (100, y))
                if p_obj: self.screen.blit(p_obj.mini_avatar, (215, y - 5))
                self.screen.blit(self.font_small.render(m["player"], True, clr), (250, y))
                self.screen.blit(self.font_small.render(str(m["from"]), True, clr), (450, y))
                self.screen.blit(self.font_small.render(str(m["to"]), True, clr), (650, y))
                self.screen.blit(self.font_small.render(m["ticket"].upper(), True, clr), (850, y))
        pygame.draw.rect(self.screen, (34, 139, 34), self.restart_rect, border_radius=10)
        btn = self.font_main.render("RESTART", True, (255, 255, 255))
        self.screen.blit(btn, (self.restart_rect.centerx-btn.get_width()//2, self.restart_rect.centery-btn.get_height()//2))
        
    def draw_mrx_log(self):
        if not self.mrx_log:
            return

        # Log container settings - Lowered to align with Ticket Bar
        log_x = WIDTH - 350
        # Positioned right at the start of the ticket bar area
        log_y = TOP_BAR_HEIGHT + 15 
        log_width = 330
        log_height = 80 # Slightly taller for better readability
        
        # Draw background panel (Darker to contrast with white ticket bar)
        pygame.draw.rect(self.screen, (30, 30, 30), (log_x, log_y, log_width, log_height), border_radius=8)
        # Using Cyan/Magenta for the border to match your highlight theme
        pygame.draw.rect(self.screen, HIGHLIGHT_COLOR, (log_x, log_y, log_width, log_height), 2, border_radius=8)
        
        # Title - "MR. X LAST KNOWN"
        title = self.font_small.render("MR. X MOVEMENT LOG", True, HIGHLIGHT_COLOR)
        self.screen.blit(title, (log_x + 10, log_y + 10))
        
        # Build the log string (e.g., "103 -> BUS -> TAXI")
        log_text = " -> ".join(self.mrx_log)
        
        # Render the log content
        content = self.font_main.render(log_text, True, (255, 255, 255))
        
        # Auto-scaling if the move history gets very long
        if content.get_width() > log_width - 20:
            scale = (log_width - 20) / content.get_width()
            new_size = (int(content.get_width() * scale), int(content.get_height() * scale))
            content = pygame.transform.scale(content, new_size)
            
        self.screen.blit(content, (log_x + 10, log_y + 40))

    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT: pygame.quit(); sys.exit()
                if e.type == pygame.MOUSEBUTTONDOWN: self.handle_click(e.pos)
                if e.type == pygame.MOUSEWHEEL and self.game_over: self.scroll_y = max(0, self.scroll_y - e.y * 30)
            if self.difficulty is None:
                self.screen.fill((40, 40, 50))
                for rect, txt, clr in [(self.easy_rect, "EASY", (100,200,100)), (self.med_rect, "MEDIUM", (200,200,100)), (self.hard_rect, "HARD (Strategy)", (200,100,100))]:
                    pygame.draw.rect(self.screen, clr, rect, border_radius=10)
                    t = self.font_main.render(txt, True, (0,0,0))
                    self.screen.blit(t, (rect.centerx - t.get_width()//2, rect.centery - t.get_height()//2))
            elif not self.game_over:
                self.screen.fill((240, 240, 240))
                self.draw_ui()
                self.draw_mrx_log()
                self.draw_board_elements()
                for i, p in enumerate(self.players):
                    if p.type != PlayerType.MRX or (self.turn_count in REVEAL_TURNS and self.current_idx == 0):
                        pygame.draw.circle(self.screen, p.color, self.board.nodes[p.node], 16)
                        pygame.draw.circle(self.screen, (255,255,255), self.board.nodes[p.node], 16, 2)
                self.draw_ticket_selector()
            else: self.draw_history_screen()
            pygame.display.flip(); self.clock.tick(FPS)

if __name__ == "__main__":
    game = ScotlandYardGUI("stations3.csv", "edges3.csv")
    game.run()
