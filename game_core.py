import copy
import json
import os

# 定义棋子常量
EMPTY = 0
BLACK = 1
WHITE = 2

class GameState:
    """
    备忘录模式 (Memento Pattern) 的一部分
    用于保存游戏快照，支持悔棋和存档
    """
    def __init__(self, board, current_player, move_history):
        self.board = copy.deepcopy(board)
        self.current_player = current_player
        self.move_history = copy.deepcopy(move_history)

class AbstractBoardGame:
    """
    抽象基类 (Abstract Base Class)
    定义游戏的通用接口，体现面向对象的多态性 
    """
    def __init__(self, size=15):
        if not (8 <= size <= 19):
            raise ValueError("棋盘大小必须在 8*8 到 19*19 之间")
        self.size = size
        self.board = [[EMPTY for _ in range(size)] for _ in range(size)]
        self.current_player = BLACK
        self.history = []  # 存储 GameState 对象
        self.move_history = [] # 存储落子坐标，用于显示
        self.game_over = False
        self.winner = None
        self.save_state() # 保存初始状态

    def save_state(self):
        """保存当前状态到历史记录，用于悔棋"""
        state = GameState(self.board, self.current_player, self.move_history)
        self.history.append(state)

    def undo(self):
        """悔棋功能"""
        if len(self.history) < 2:
            return False, "无棋可悔"
        
        self.history.pop() # 弹出当前状态
        prev_state = self.history[-1] # 获取上一步状态
        
        # 恢复状态
        self.board = copy.deepcopy(prev_state.board)
        self.current_player = prev_state.current_player
        self.move_history = copy.deepcopy(prev_state.move_history)
        self.game_over = False
        self.winner = None
        return True, f"玩家 {'黑' if self.current_player == BLACK else '白'} 悔棋成功"

    def switch_player(self):
        self.current_player = WHITE if self.current_player == BLACK else BLACK

    def is_valid_coord(self, x, y):
        return 0 <= x < self.size and 0 <= y < self.size

    def place_stone(self, x, y):
        """模板方法：具体规则由子类实现"""
        if self.game_over:
            return False, "游戏已结束"
        
        # 检查坐标越界
        if not self.is_valid_coord(x, y):
            return False, "落子位置不合法：越界"
        
        # 检查已有棋子
        if self.board[x][y] != EMPTY:
            return False, "落子位置不合法：已有棋子"

        # 执行具体游戏的落子逻辑（由子类重写）
        success, msg = self._make_move_logic(x, y)
        
        if success:
            self.move_history.append((x, y))
            self.switch_player()
            self.save_state() # 每次落子后保存状态
            self._check_winner() # 检查胜负
        
        return success, msg

    def _make_move_logic(self, x, y):
        raise NotImplementedError

    def _check_winner(self):
        raise NotImplementedError
    
    def surrender(self):
        """投子认负"""
        self.game_over = True
        self.winner = WHITE if self.current_player == BLACK else BLACK
        return f"玩家 {'黑' if self.current_player == BLACK else '白'} 认负。"

    def save_to_file(self, filename):
        """序列化保存到文件"""
        try:
            data = {
                "type": self.__class__.__name__,
                "size": self.size,
                "board": self.board,
                "current_player": self.current_player,
                "move_history": self.move_history
                # 简化起见，不保存完整的 history 栈，加载后不可悔棋到加载前
            }
            with open(filename, 'w') as f:
                json.dump(data, f)
            return True, "保存成功"
        except Exception as e:
            return False, str(e)

    def load_from_file(self, filename):
        """从文件加载"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            # 校验游戏类型是否匹配（可选）
            if data['type'] != self.__class__.__name__:
                return False, "存档文件类型与当前游戏不匹配"
            
            self.size = data['size']
            self.board = data['board']
            self.current_player = data['current_player']
            self.move_history = data['move_history']
            self.history = [] # 重置悔棋栈
            self.save_state() # 保存当前加载的状态
            return True, "读取成功"
        except Exception as e:
            return False, "读取失败: " + str(e)

class GomokuGame(AbstractBoardGame):
    """五子棋实现类"""
    
    def _make_move_logic(self, x, y):
        # 五子棋逻辑简单，只要空地即可下
        self.board[x][y] = self.current_player
        return True, f"玩家 {'黑' if self.current_player == BLACK else '白'} 落子成功"

    def _check_winner(self):
        """判断五子连珠"""
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for r in range(self.size):
            for c in range(self.size):
                if self.board[r][c] == EMPTY:
                    continue
                p = self.board[r][c]
                for dr, dc in directions:
                    count = 1
                    for i in range(1, 5):
                        nr, nc = r + dr * i, c + dc * i
                        if self.is_valid_coord(nr, nc) and self.board[nr][nc] == p:
                            count += 1
                        else:
                            break
                    if count == 5:
                        self.game_over = True
                        self.winner = p
                        return

class GoGame(AbstractBoardGame):
    """围棋实现类"""

    def pass_turn(self):
        """虚着"""
        if self.game_over: return False, "游戏已结束"
        
        self.move_history.append("PASS")
        
        # 检查是否双重虚着导致终局 
        if len(self.move_history) >= 2 and self.move_history[-2] == "PASS":
            self.game_over = True
            self.judge_winner_area_scoring() # 系统判断胜负
            return True, "双方连续虚着，游戏结束。"
            
        self.switch_player()
        self.save_state()
        return True, "虚着成功"

    def _make_move_logic(self, x, y):
        # 围棋规则复杂：提子、无气禁入、打劫
        # 1. 尝试落子
        original_board = copy.deepcopy(self.board)
        self.board[x][y] = self.current_player
        
        # 2. 检查是否有对手棋子气尽（提子）
        opponent = WHITE if self.current_player == BLACK else BLACK
        captured_stones = self.remove_dead_stones(opponent)
        
        # 3. 检查自己是否气尽（自杀禁手，除非能提子）
        if not self.has_liberties(x, y) and captured_stones == 0:
            self.board = original_board # 撤销
            return False, f"玩家 {'黑' if self.current_player == BLACK else '白'} 落子不合法：禁入点（无气）"
        
        # 4. 检查全局同型（打劫）- 简化版：对比上一手棋盘
        # (严谨的打劫需要对比所有历史，这里对比上一手满足基本作业需求)
        if len(self.history) > 0:
            last_board = self.history[-1].board
            if self.board == last_board:
                self.board = original_board
                return False, f"玩家 {'黑' if self.current_player == BLACK else '白'} 落子不合法：全局同型（打劫）"

        return True, f"玩家 {'黑' if self.current_player == BLACK else '白'} 落子成功" + (f" (提子 {captured_stones} 颗)" if captured_stones else "")

    def get_group(self, r, c):
        """获取(r,c)位置棋子所在的块"""
        color = self.board[r][c]
        group = set()
        stack = [(r, c)]
        while stack:
            cur_r, cur_c = stack.pop()
            if (cur_r, cur_c) in group:
                continue
            group.add((cur_r, cur_c))
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nr, nc = cur_r + dr, cur_c + dc
                if self.is_valid_coord(nr, nc) and self.board[nr][nc] == color:
                    stack.append((nr, nc))
        return group

    def has_liberties(self, r, c):
        """检查某块棋是否有气"""
        group = self.get_group(r, c)
        for gr, gc in group:
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nr, nc = gr + dr, gc + dc
                if self.is_valid_coord(nr, nc) and self.board[nr][nc] == EMPTY:
                    return True
        return False

    def remove_dead_stones(self, color):
        """移除无气的棋子，返回移除数量"""
        dead_stones = []
        visited = set()
        
        for r in range(self.size):
            for c in range(self.size):
                if self.board[r][c] == color and (r, c) not in visited:
                    group = self.get_group(r, c)
                    # 检查该组是否有气
                    has_liberty = False
                    for gr, gc in group:
                        # 只要有一个棋子旁边有空位，整块活
                        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                            nr, nc = gr + dr, gc + dc
                            if self.is_valid_coord(nr, nc) and self.board[nr][nc] == EMPTY:
                                has_liberty = True
                                break
                        if has_liberty: break
                    
                    if not has_liberty:
                        dead_stones.extend(list(group))
                    
                    visited.update(group)
        
        # 提子
        for dr, dc in dead_stones:
            self.board[dr][dc] = EMPTY
            
        return len(dead_stones)

    def _check_winner(self):
        # 围棋在过程中不自动判断胜负（除非投降或双虚着），由 pass_turn 触发
        pass

    def judge_winner_area_scoring(self):
        """简单的数子法 (Area Scoring)"""
        # 注意：这里是简化的数子逻辑，真实的数子需要判断死活棋
        # 第一阶段作业通常只要求“任何一种现行方法”，最简单的是统计盘面棋子数
        black_score = 0
        white_score = 0
        for r in range(self.size):
            for c in range(self.size):
                if self.board[r][c] == BLACK:
                    black_score += 1
                elif self.board[r][c] == WHITE:
                    white_score += 1
        
        # 贴目（简易处理，黑贴3.75子，即7.5目）
        if black_score - 3.75 > white_score:
            self.winner = BLACK
        else:
            self.winner = WHITE

class GameFactory:
    """
    工厂模式 (Factory Pattern)
    用于根据用户输入创建不同的游戏实例
    """
    @staticmethod
    def create_game(game_type, size):
        if game_type == 'gomoku':
            return GomokuGame(size)
        elif game_type == 'go':
            return GoGame(size)
        else:
            raise ValueError("未知的游戏类型")