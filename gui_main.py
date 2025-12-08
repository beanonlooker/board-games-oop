import pygame
import sys
import os
import tkinter as tk
from tkinter import filedialog
from game_core import GameFactory, BLACK, WHITE, EMPTY

# --- 配置参数 ---
SCREEN_WIDTH = 900
SCREEN_HEIGHT = 700
BOARD_MARGIN = 40  # 棋盘边缘留白
CELL_SIZE = 35     # 格子大小
UI_PANEL_WIDTH = 200 # 右侧控制栏宽度

# 颜色定义
COLOR_BG = (220, 200, 170) # 默认木纹色
COLOR_GRID = (0, 0, 0)
COLOR_TEXT = (50, 50, 50)
COLOR_BUTTON = (70, 130, 180)
COLOR_BUTTON_HOVER = (100, 149, 237)
COLOR_WHITE = (255, 255, 255)

class ResourceManager:
    """资源管理器：负责加载图片，如果图片不存在则使用绘制模式"""
    def __init__(self):
        self.images = {}
        self._load_image('board', 'assets/board.jpg')
        self._load_image('black', 'assets/black.png', scale=True)
        self._load_image('white', 'assets/white.png', scale=True)
        
        # 字体初始化
        pygame.font.init()
        
        # 定义不同系统的常用中文字体列表
        font_candidates = [
            'SimHei',             # Windows 黑体
            'Microsoft YaHei',    # Windows 微软雅黑
            'PingFang SC',        # macOS 苹方
            'Heiti TC',           # macOS 黑体
            'WenQuanYi Micro Hei',# Linux 文泉驿
            'SimSun',             # Windows 宋体
            'Arial Unicode MS'    # 通用后备
        ]
        
        self.font = None
        self.small_font = None

        # 遍历列表，找到系统中存在的第一个中文字体
        system_fonts = pygame.font.get_fonts()
        chosen_font = 'arial' # 默认后备
        
        for f in font_candidates:
            # pygame.font.get_fonts() 返回的名称通常是小写且无空格
            # 我们尝试模糊匹配
            f_lower = f.lower().replace(" ", "")
            if f_lower in system_fonts:
                chosen_font = f
                break
        
        print(f"系统已选择字体: {chosen_font}") # 调试输出

        # 初始化字体
        try:
            self.font = pygame.font.SysFont(chosen_font, 24)
            self.small_font = pygame.font.SysFont(chosen_font, 16) # 这里也必须用中文字体
        except:
            # 极端的后备情况
            self.font = pygame.font.SysFont(None, 24)
            self.small_font = pygame.font.SysFont(None, 16)

    def _load_image(self, key, path, scale=False):
        if os.path.exists(path):
            try:
                img = pygame.image.load(path).convert_alpha()
                if scale:
                    img = pygame.transform.smoothscale(img, (CELL_SIZE - 2, CELL_SIZE - 2))
                self.images[key] = img
            except Exception as e:
                print(f"加载图片 {path} 失败: {e}")
                self.images[key] = None
        else:
            self.images[key] = None

class Button:
    """简单的UI按钮类"""
    def __init__(self, x, y, w, h, text, callback):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.callback = callback
        self.hovered = False

    def draw(self, screen, font):
        color = COLOR_BUTTON_HOVER if self.hovered else COLOR_BUTTON
        pygame.draw.rect(screen, color, self.rect, border_radius=5)
        text_surf = font.render(self.text, True, COLOR_WHITE)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.hovered and event.button == 1:
                self.callback()
                return True  # <--- 新增：返回 True 表示事件已被处理
        return False         # <--- 新增：返回 False 表示未触发

class GUIClient:
    """
    GUI客户端：体现显示逻辑与业务逻辑分离 
    只负责渲染和输入转发，不处理游戏规则
    """
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("棋类对战平台")
        self.clock = pygame.time.Clock()
        self.res = ResourceManager()
        
        self.game = None
        self.offset_x = 0
        self.offset_y = 0
        self.buttons = []
        self.msg_log = ["欢迎来到对战平台", "请调整大小并选择游戏"]

        # --- 新增：当前选择的棋盘大小 ---
        self.selected_size = 15 
        
        self.state = "MENU" 
        self.init_menu_buttons()

    def log(self, text):
        self.msg_log.append(text)
        if len(self.msg_log) > 10:
            self.msg_log.pop(0)

    def change_size(self, delta):
        """调整棋盘大小，限制在 8-19 之间"""
        new_size = self.selected_size + delta
        if 8 <= new_size <= 19:
            self.selected_size = new_size
            # 大小改变后，需要刷新菜单按钮显示的文字
            self.init_menu_buttons()

    def init_menu_buttons(self):
        """初始化主菜单按钮 (动态显示大小)"""
        self.buttons = []
        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        
        # 1. 尺寸调节区域
        # 减号按钮
        btn_minus = Button(cx + 120, cy - 100, 40, 40, "-", 
                           lambda: self.change_size(-1))
        # 加号按钮
        btn_plus = Button(cx + 170, cy - 100, 40, 40, "+", 
                          lambda: self.change_size(1))
        
        # 2. 游戏开始按钮 (使用当前 selected_size)
        # 注意：这里lambda中需要用 default argument 绑定当前的 size，否则会闭包捕获
        btn_gomoku = Button(cx - 100, cy - 20, 200, 40, "开始五子棋", 
                            lambda s=self.selected_size: self.start_game('gomoku', s))
        
        btn_go = Button(cx - 100, cy + 40, 200, 40, "开始围棋", 
                        lambda s=self.selected_size: self.start_game('go', s))
        
        self.buttons.extend([btn_minus, btn_plus, btn_gomoku, btn_go])

    def init_game_buttons(self):
        """初始化游戏界面按钮"""
        self.buttons = []
        x_start = SCREEN_WIDTH - UI_PANEL_WIDTH + 20
        y_start = 50
        gap = 50 # 稍微调小间距，以便放下更多按钮

        # 1. 常用操作
        self.buttons.append(Button(x_start, y_start, 160, 35, "悔棋", self.cmd_undo))
        y_start += gap
        
        if isinstance(self.game, GameFactory.create_game('go', 9).__class__):
             self.buttons.append(Button(x_start, y_start, 160, 35, "虚着", self.cmd_pass))
             y_start += gap

        # 2. 存档/读档 (新增)
        self.buttons.append(Button(x_start, y_start, 160, 35, "保存局面", self.cmd_save))
        y_start += gap
        self.buttons.append(Button(x_start, y_start, 160, 35, "读取存档", self.cmd_load))
        y_start += gap

        # 3. 胜负与流程
        self.buttons.append(Button(x_start, y_start, 160, 35, "认负", self.cmd_surrender))
        y_start += gap
        self.buttons.append(Button(x_start, y_start, 160, 35, "重开", self.cmd_restart))
        y_start += gap
        self.buttons.append(Button(x_start, y_start, 160, 35, "返回菜单", self.cmd_back_menu))

    # --- 交互逻辑 (Controller) ---

    def start_game(self, g_type, size):
        try:
            self.game = GameFactory.create_game(g_type, size)
            self.state = "GAME"
            # 计算棋盘在屏幕中的居中位置
            board_pixel_size = size * CELL_SIZE
            self.offset_x = (SCREEN_WIDTH - UI_PANEL_WIDTH - board_pixel_size) // 2
            self.offset_y = (SCREEN_HEIGHT - board_pixel_size) // 2
            self.log(f"开始游戏: {"五子棋" if g_type == 'gomoku' else "围棋"}, 大小: {size}x{size}")
            self.init_game_buttons()
        except Exception as e:
            self.log(f"错误: {str(e)}")

    def handle_board_click(self, pos):
        """处理鼠标点击棋盘 """
        if self.state != "GAME" or self.game.game_over:
            return

        mx, my = pos
        # 坐标转换：屏幕坐标 -> 棋盘矩阵坐标
        col = round((mx - self.offset_x - CELL_SIZE/2) / CELL_SIZE)
        row = round((my - self.offset_y - CELL_SIZE/2) / CELL_SIZE)

        # 调用后端逻辑
        success, msg = self.game.place_stone(row, col)
        self.log(msg)

    def cmd_undo(self):
        success, msg = self.game.undo()
        self.log(msg)

    def cmd_pass(self):
        if hasattr(self.game, 'pass_turn'):
            success, msg = self.game.pass_turn()
            self.log(msg)

    def cmd_surrender(self):
        msg = self.game.surrender()
        self.log(msg)

    def cmd_restart(self):
        # 保持当前类型重开
        t = 'gomoku' if 'Gomoku' in self.game.__class__.__name__ else 'go'
        self.start_game(t, self.game.size)

    def cmd_back_menu(self):
        self.state = "MENU"
        self.game = None
        self.init_menu_buttons()

    def cmd_save(self):
        """弹出保存文件对话框"""
        # 初始化 tkinter 并不显示主窗口
        root = tk.Tk()
        root.withdraw() 
        
        # 弹出保存对话框
        file_path = filedialog.asksaveasfilename(
            title="保存当前棋局",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialdir=os.getcwd() # 默认在当前目录
        )
        root.destroy() #以此销毁，防止阻塞
        
        if file_path:
            success, msg = self.game.save_to_file(file_path)
            self.log(msg)
        else:
            self.log("取消保存")

    def cmd_load(self):
        """弹出读取文件对话框"""
        root = tk.Tk()
        root.withdraw()
        
        file_path = filedialog.askopenfilename(
            title="读取存档",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialdir=os.getcwd()
        )
        root.destroy()
        
        if file_path:
            # 读取前先记录一下当前的类型，如果读取的文件类型不同可能需要警告（这里简化处理）
            success, msg = self.game.load_from_file(file_path)
            self.log(msg)
            if success:
                # 读取成功后，如果棋盘大小变了，需要重新计算居中偏移
                # 重新复用 start_game 的部分逻辑来重置界面
                board_pixel_size = self.game.size * CELL_SIZE
                self.offset_x = (SCREEN_WIDTH - UI_PANEL_WIDTH - board_pixel_size) // 2
                self.offset_y = (SCREEN_HEIGHT - board_pixel_size) // 2
                # 刷新大小显示
                self.selected_size = self.game.size 
        else:
            self.log("取消读取")

    # --- 渲染逻辑 (View) ---

    def draw_board_grid(self):
        size = self.game.size
        # 1. 绘制背景（图片或纯色） 
        bg_img = self.res.images['board']
        rect_area = (self.offset_x, self.offset_y, size * CELL_SIZE, size * CELL_SIZE)
        
        if bg_img:
            # 平铺或拉伸背景图
            scaled_bg = pygame.transform.scale(bg_img, (size * CELL_SIZE, size * CELL_SIZE))
            self.screen.blit(scaled_bg, (self.offset_x, self.offset_y))
        else:
            pygame.draw.rect(self.screen, COLOR_BG, rect_area)
        
        # 2. 绘制网格线
        for i in range(size):
            # 横线
            start_pos = (self.offset_x + CELL_SIZE//2, self.offset_y + CELL_SIZE//2 + i * CELL_SIZE)
            end_pos = (self.offset_x + size * CELL_SIZE - CELL_SIZE//2, self.offset_y + CELL_SIZE//2 + i * CELL_SIZE)
            pygame.draw.line(self.screen, COLOR_GRID, start_pos, end_pos, 1)
            # 竖线
            start_pos = (self.offset_x + CELL_SIZE//2 + i * CELL_SIZE, self.offset_y + CELL_SIZE//2)
            end_pos = (self.offset_x + CELL_SIZE//2 + i * CELL_SIZE, self.offset_y + size * CELL_SIZE - CELL_SIZE//2)
            pygame.draw.line(self.screen, COLOR_GRID, start_pos, end_pos, 1)

        # 3. 绘制星位 (仅19路围棋)
        if size == 19:
            stars = [(3,3), (3,9), (3,15), (9,3), (9,9), (9,15), (15,3), (15,9), (15,15)]
            for r, c in stars:
                cx = self.offset_x + c * CELL_SIZE + CELL_SIZE // 2
                cy = self.offset_y + r * CELL_SIZE + CELL_SIZE // 2
                pygame.draw.circle(self.screen, COLOR_GRID, (cx, cy), 3)

    def draw_stones(self):
        """渲染棋子 """
        for r in range(self.game.size):
            for c in range(self.game.size):
                piece = self.game.board[r][c]
                if piece == EMPTY:
                    continue
                
                cx = self.offset_x + c * CELL_SIZE + CELL_SIZE // 2
                cy = self.offset_y + r * CELL_SIZE + CELL_SIZE // 2
                
                img_key = 'black' if piece == BLACK else 'white'
                img = self.res.images[img_key]
                
                if img:
                    # 使用图片渲染
                    img_rect = img.get_rect(center=(cx, cy))
                    self.screen.blit(img, img_rect)
                else:
                    # 图片缺失时回退到绘制圆形
                    color = (0, 0, 0) if piece == BLACK else (255, 255, 255)
                    pygame.draw.circle(self.screen, color, (cx, cy), CELL_SIZE // 2 - 2)
                    # 增加立体感（可选）
                    if piece == WHITE:
                         pygame.draw.circle(self.screen, (200, 200, 200), (cx, cy), CELL_SIZE // 2 - 2, 1)

        # 标记最新落子（红色小点）
        if self.game.move_history and isinstance(self.game.move_history[-1], tuple):
            last_r, last_c = self.game.move_history[-1]
            cx = self.offset_x + last_c * CELL_SIZE + CELL_SIZE // 2
            cy = self.offset_y + last_r * CELL_SIZE + CELL_SIZE // 2
            pygame.draw.rect(self.screen, (255, 0, 0), (cx-2, cy-2, 4, 4))

    def draw_ui_panel(self):
        panel_x = SCREEN_WIDTH - UI_PANEL_WIDTH
        # 绘制背景
        pygame.draw.rect(self.screen, (240, 240, 240), (panel_x, 0, UI_PANEL_WIDTH, SCREEN_HEIGHT))
        
        # 1. 显示当前执子
        info_text = f"当前执子: {'黑方' if self.game.current_player == BLACK else '白方'}"
        ts = self.res.font.render(info_text, True, COLOR_TEXT)
        self.screen.blit(ts, (panel_x + 10, 20))

        # 2. 显示胜负信息
        if self.game.game_over:
            if self.game.winner:
                win_text = f"胜者: {'黑方' if self.game.winner == BLACK else '白方'}"
                color = (255, 0, 0)
            else:
                win_text = "平局"
                color = (0, 0, 255)
            ts = self.res.font.render(win_text, True, color)
            self.screen.blit(ts, (panel_x + 10, SCREEN_HEIGHT - 60))

        # 3. 绘制日志区域分割线
        log_top_y = SCREEN_HEIGHT - 300  # 稍微调高一点，给日志更多空间
        pygame.draw.line(self.screen, (200, 200, 200), (panel_x, log_top_y), (SCREEN_WIDTH, log_top_y))
        
        # --- 自动换行逻辑开始 ---
        font = self.res.small_font
        max_width = UI_PANEL_WIDTH - 15  # 预留左右边距
        line_height = 20                 # 行高
        max_lines = 12                   # 最多显示多少行（防止溢出屏幕上边界）
        
        display_lines = [] # 存储处理后切分好的所有行

        # 遍历所有日志消息
        for msg in self.msg_log:
            current_line = ""
            for char in msg:
                test_line = current_line + char
                # 检查宽度
                if font.size(test_line)[0] <= max_width:
                    current_line = test_line
                else:
                    display_lines.append(current_line) # 保存这一行
                    current_line = char # 新起一行
            display_lines.append(current_line) # 保存最后剩余的部分
        
        # 只截取最后 N 行显示，保证看到的是最新的
        visible_lines = display_lines[-max_lines:]
        
        # 渲染
        y = log_top_y + 10
        for line in visible_lines:
            t = font.render(line, True, (100, 100, 100))
            self.screen.blit(t, (panel_x + 5, y))
            y += line_height

    def run(self):
        while True:
            # 1. 事件处理
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                
                # --- 修改开始 ---
                # 优先处理按钮事件
                btn_handled = False
                for btn in self.buttons:
                    if btn.handle_event(event):
                        btn_handled = True
                        break # 一个事件只触发一个按钮
                
                # 如果按钮处理了这个事件（比如点击了开始），就跳过后续的棋盘判定
                if btn_handled:
                    continue 
                # --- 修改结束 ---

                # 棋盘点击事件
                if event.type == pygame.MOUSEBUTTONDOWN and self.state == "GAME":
                    if event.button == 1: 
                        if (self.offset_x < event.pos[0] < self.offset_x + self.game.size * CELL_SIZE and
                            self.offset_y < event.pos[1] < self.offset_y + self.game.size * CELL_SIZE):
                            self.handle_board_click(event.pos)

            self.screen.fill(COLOR_WHITE)

            if self.state == "MENU":
                # 绘制标题
                title = self.res.font.render("Python 棋类对战平台", True, COLOR_TEXT)
                title_rect = title.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 160))
                self.screen.blit(title, title_rect)
                
                # --- 新增：绘制当前选中的尺寸数字 ---
                size_text = self.res.font.render(f"棋盘大小: {self.selected_size} x {self.selected_size}", True, COLOR_TEXT)
                # 放在减号和加号按钮中间
                size_rect = size_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 80))
                self.screen.blit(size_text, size_rect)
            
            elif self.state == "GAME":
                self.draw_board_grid()
                self.draw_stones()
                self.draw_ui_panel()

            for btn in self.buttons:
                btn.draw(self.screen, self.res.font)

            pygame.display.flip()
            self.clock.tick(30)

if __name__ == "__main__":
    app = GUIClient()
    app.run()