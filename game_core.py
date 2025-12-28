import copy
import json
import random

# 常量
EMPTY = 0
BLACK = 1
WHITE = 2

class AIFactory:
    @staticmethod
    def create_ai(game_type):
        if game_type == 'gomoku': return GomokuAI()
        elif game_type == 'reversi': return ReversiAI()
        elif game_type == 'go': return GoAI()
        return RandomAI()

class AIInterface:
    def get_move(self, game): raise NotImplementedError

class RandomAI(AIInterface):
    def get_move(self, game):
        moves = game.get_valid_moves(game.current_player)
        return random.choice(moves) if moves else None

class GomokuAI(AIInterface):
    def get_move(self, game):
        if len(game.move_history) == 0:
            return (game.size // 2, game.size // 2)

        candidates = self._get_neighbor_moves(game)
        if not candidates: return None

        best_score = -1
        best_move = candidates[0]

        for r, c in candidates:
            my_score = self._evaluate_point_power(game, r, c, game.current_player)
            
            rival = BLACK if game.current_player == WHITE else WHITE
            rival_score = self._evaluate_point_power(game, r, c, rival)
            
            total_score = my_score + rival_score

            if total_score > best_score:
                best_score = total_score
                best_move = (r, c)
        
        return best_move

    def _get_neighbor_moves(self, game):
        """只搜索有棋子周围的空位"""
        moves = set()
        size = game.size
        has_stone = False
        for r in range(size):
            for c in range(size):
                if game.board[r][c] != EMPTY:
                    has_stone = True
                    for i in range(-2, 3):
                        for j in range(-2, 3):
                            if i==0 and j==0: continue
                            nr, nc = r+i, c+j
                            if 0<=nr<size and 0<=nc<size and game.board[nr][nc] == EMPTY:
                                moves.add((nr, nc))
        if not has_stone: # 空盘
            return [(size//2, size//2)]
        return list(moves)

    def _evaluate_point_power(self, game, r, c, color):
        """
        计算在 (r,c) 落子后，该点在四个方向上形成的棋型分数总和
        """
        score = 0
        # 四个方向：横、竖、左斜、右斜
        directions = [(1,0), (0,1), (1,1), (1,-1)]
        
        for dr, dc in directions:
            # 向两个方向延伸计数
            count = 1 
            # 检查两端是否被堵
            blocked_sides = 0 

            # 正向延伸 (Forward)
            i = 1
            while True:
                nr, nc = r + dr*i, c + dc*i
                if not game.is_valid_coord(nr, nc): # 出界算被堵
                    blocked_sides += 1; break
                val = game.board[nr][nc]
                if val == color: count += 1
                elif val == EMPTY: break # 空位停止
                else: # 敌方棋子，算被堵
                    blocked_sides += 1; break
                i += 1
            
            # 反向延伸 (Backward)
            i = 1
            while True:
                nr, nc = r - dr*i, c - dc*i
                if not game.is_valid_coord(nr, nc):
                    blocked_sides += 1; break
                val = game.board[nr][nc]
                if val == color: count += 1
                elif val == EMPTY: break
                else:
                    blocked_sides += 1; break
                i += 1

            # --- 评分规则表 (根据连子数和被堵情况) ---
            # 连5 (赢了)
            if count >= 5: 
                score += 100000
            # 连4
            elif count == 4:
                if blocked_sides == 0: score += 10000 # 活四 
                elif blocked_sides == 1: score += 1000 # 冲四
            # 连3
            elif count == 3:
                if blocked_sides == 0: score += 1000 # 活三 
                elif blocked_sides == 1: score += 100 # 眠三
            # 连2
            elif count == 2:
                if blocked_sides == 0: score += 100 # 活二
                elif blocked_sides == 1: score += 10 # 眠二
            
            # 额外加分：位置越靠中间越好
            score += (7 - max(abs(r-7), abs(c-7)))

        return score

class ReversiAI(AIInterface):
    def get_move(self, game):
        moves = game.get_valid_moves(game.current_player)
        if not moves: return None

        # 权重图 (8x8)
        WEIGHTS = [
            [100, -20, 10,  5,  5, 10, -20, 100],
            [-20, -50, -2, -2, -2, -2, -50, -20],
            [ 10,  -2, -1, -1, -1, -1,  -2,  10],
            [  5,  -2, -1, -1, -1, -1,  -2,   5],
            [  5,  -2, -1, -1, -1, -1,  -2,   5],
            [ 10,  -2, -1, -1, -1, -1,  -2,  10],
            [-20, -50, -2, -2, -2, -2, -50, -20],
            [100, -20, 10,  5,  5, 10, -20, 100]
        ]
        
        best_score = -99999
        best_move = moves[0]

        for r, c in moves:
            # 贪婪评估：只看这一步带来的位置分 + 翻转数量
            # 1. 位置分
            pos_score = 0
            if game.size == 8: pos_score = WEIGHTS[r][c]
            else: pos_score = 10 # 非标准棋盘随便给分
            
            # 2. 翻转数量
            flip_count = game._can_flip(r, c, game.current_player)
            
            # 综合分：优先占角(100)，其次吃子
            score = pos_score + flip_count
            
            if score > best_score:
                best_score = score
                best_move = (r, c)
                
        return best_move

class GoAI(AIInterface):
    def get_move(self, game):
        valid = game.get_valid_moves(game.current_player)
        if not valid: return None
        random.shuffle(valid) # 默认随机

        opp = BLACK if game.current_player == WHITE else WHITE
        for r, c in valid:
            # 检查四周是否有对手的棋子
            for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
                nr, nc = r+dr, c+dc
                if game.is_valid_coord(nr, nc) and game.board[nr][nc] == opp:
                    pass
        
        safe_moves = []
        for r, c in valid:
            my_neighbors = 0
            for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
                nr, nc = r+dr, c+dc
                if game.is_valid_coord(nr, nc) and game.board[nr][nc] == game.current_player:
                    my_neighbors += 1
            if my_neighbors < 4: 
                safe_moves.append((r,c))
        
        return safe_moves[0] if safe_moves else valid[0]


class GameState:
    def __init__(self, board, player, history):
        self.board = copy.deepcopy(board)
        self.player = player
        self.history = copy.deepcopy(history)

class AbstractBoardGame:
    def __init__(self, size=15):
        self.size = size
        self.board = [[EMPTY]*size for _ in range(size)]
        self.current_player = BLACK
        self.undo_stack = []
        self.move_history = []
        self.game_over = False
        self.winner = None
        self._save_undo()

    def _save_undo(self):
        self.undo_stack.append(GameState(self.board, self.current_player, self.move_history))

    def undo(self):
        if len(self.undo_stack) < 2: return False, "无棋可悔"
        self.undo_stack.pop()
        s = self.undo_stack[-1]
        self.board = copy.deepcopy(s.board)
        self.current_player = s.player
        self.move_history = copy.deepcopy(s.history)
        self.game_over = False; self.winner = None
        return True, "悔棋成功"

    def is_valid_coord(self, r, c):
        return 0 <= r < self.size and 0 <= c < self.size

    def place_stone(self, r, c):
        if self.game_over: return False, "结束"
        if not self.is_valid_coord(r, c): return False, "越界"
        
        suc, msg = self._logic_place(r, c)
        if suc:
            self.move_history.append((r, c))
            self.current_player = WHITE if self.current_player == BLACK else BLACK
            self._save_undo()
            self._check_winner()
            self._after_turn()
        return suc, msg

    # --- 抽象接口 ---
    def _logic_place(self, r, c): raise NotImplementedError
    def get_valid_moves(self, player): raise NotImplementedError
    def _check_winner(self): raise NotImplementedError
    def _after_turn(self): pass
    
    # --- 通用功能 ---
    def save_to_file(self, fpath, meta=None):
        try:
            d = {"type": self.__class__.__name__, "size": self.size, "board": self.board, 
                 "player": self.current_player, "history": self.move_history, "meta": meta or {}}
            with open(fpath, 'w') as f: json.dump(d, f)
            return True, "保存成功"
        except Exception as e: return False, str(e)
    
    def load_from_file(self, fpath):
        try:
            with open(fpath, 'r') as f: d = json.load(f)
            if d['type'] != self.__class__.__name__: return False, "类型不符"
            self.size = d['size']; self.board = d['board']
            self.current_player = d['player']; self.move_history = d['history']
            self.undo_stack = []; self._save_undo(); self._check_winner()
            return True, d.get('meta', {})
        except Exception as e: return False, str(e)

    def surrender(self):
        self.game_over = True
        self.winner = WHITE if self.current_player == BLACK else BLACK
        return "认负"

# --- 五子棋规则 ---
class GomokuGame(AbstractBoardGame):
    def get_valid_moves(self, player):
        return [(r,c) for r in range(self.size) for c in range(self.size) if self.board[r][c]==EMPTY]

    def _logic_place(self, r, c):
        if self.board[r][c] != EMPTY: return False, "已有子"
        self.board[r][c] = self.current_player
        return True, "落子"

    def _check_winner(self):
        for r in range(self.size):
            for c in range(self.size):
                p = self.board[r][c]
                if p == EMPTY: continue
                # 检查4个方向
                for dr, dc in [(0,1), (1,0), (1,1), (1,-1)]:
                    if self._check_line(r, c, dr, dc, p):
                        self.game_over = True; self.winner = p; return

    def _check_line(self, r, c, dr, dc, p):
        for i in range(5):
            nr, nc = r + dr*i, c + dc*i
            if not self.is_valid_coord(nr, nc) or self.board[nr][nc] != p:
                return False
        return True

# --- 黑白棋规则 ---
class ReversiGame(AbstractBoardGame):
    def __init__(self, size=8):
        super().__init__(size)
        # 初始化中心4子
        m = size // 2
        self.board[m-1][m-1] = WHITE; self.board[m][m] = WHITE
        self.board[m-1][m] = BLACK; self.board[m][m-1] = BLACK
        self.undo_stack = []; self._save_undo()

    def get_valid_moves(self, player):
        valid = []
        for r in range(self.size):
            for c in range(self.size):
                if self._can_flip(r, c, player) > 0: valid.append((r,c))
        return valid

    def _can_flip(self, r, c, player, execute=False):
        if self.board[r][c] != EMPTY: return 0
        opp = WHITE if player == BLACK else BLACK
        flipped = 0
        
        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]:
            path = []
            cx, cy = r + dr, c + dc
            while self.is_valid_coord(cx, cy) and self.board[cx][cy] == opp:
                path.append((cx, cy))
                cx += dr; cy += dc
            
            # 必须以己方棋子结尾
            if path and self.is_valid_coord(cx, cy) and self.board[cx][cy] == player:
                flipped += len(path)
                if execute:
                    for fx, fy in path: self.board[fx][fy] = player
        
        if execute and flipped > 0: self.board[r][c] = player
        return flipped

    def _logic_place(self, r, c):
        cnt = self._can_flip(r, c, self.current_player, execute=True)
        if cnt == 0: return False, "非法"
        return True, f"翻转{cnt}"

    def _after_turn(self):
        # 检查下家是否有棋，无则跳过
        nxt = self.current_player
        if not self.get_valid_moves(nxt):
            self.current_player = WHITE if nxt == BLACK else BLACK # 换回原玩家
            if not self.get_valid_moves(self.current_player):
                self.game_over = True; self._check_winner() # 双方无棋
            else:
                self.move_history.append("PASS"); self._save_undo() # Pass

    def _check_winner(self):
        b = sum(row.count(BLACK) for row in self.board)
        w = sum(row.count(WHITE) for row in self.board)
        if b > w: self.winner = BLACK
        elif w > b: self.winner = WHITE
        else: self.winner = None

# --- 围棋规则 (简化版) ---
class GoGame(AbstractBoardGame):
    def get_valid_moves(self, player):
        # 允许下在任何空位
        return [(r,c) for r in range(self.size) for c in range(self.size) if self.board[r][c]==EMPTY]

    def _logic_place(self, r, c):
        if self.board[r][c] != EMPTY: return False, "有子"
        self.board[r][c] = self.current_player
        # 提子逻辑
        opp = WHITE if self.current_player == BLACK else BLACK
        self._capture_dead(r, c, opp)
        return True, "落子"

    def _capture_dead(self, r, c, opp_color):
        # 检查落子点四周的敌子，如果气为0则提走
        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
            nr, nc = r+dr, c+dc
            if self.is_valid_coord(nr, nc) and self.board[nr][nc] == opp_color:
                group, liberties = self._get_group_libs(nr, nc, opp_color)
                if liberties == 0:
                    for gr, gc in group: self.board[gr][gc] = EMPTY

    def _get_group_libs(self, r, c, color):
        group = set(); stack = [(r,c)]; libs = 0; visited = set()
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in group: continue
            group.add((cx, cy))
            for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
                nx, ny = cx+dr, cy+dc
                if not self.is_valid_coord(nx, ny): continue
                if self.board[nx][ny] == EMPTY:
                    if (nx, ny) not in visited: libs+=1; visited.add((nx,ny))
                elif self.board[nx][ny] == color:
                    stack.append((nx, ny))
        return group, libs

    def pass_turn(self):
        self.move_history.append("PASS")
        self.current_player = WHITE if self.current_player == BLACK else BLACK
        self._save_undo()

    def _check_winner(self): pass # 围棋数子太复杂，暂不自动判胜负

class GameFactory:
    @staticmethod
    def create_game(t, s):
        if t == 'gomoku': return GomokuGame(s)
        elif t == 'reversi': return ReversiGame(s)
        elif t == 'go': return GoGame(s)
        raise ValueError("Unknown")