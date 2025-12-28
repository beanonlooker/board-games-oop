import pygame
import sys
import json
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox, ttk
# 引入核心
from game_core import GameFactory, AIFactory, BLACK, WHITE, EMPTY
from user_manager import UserManager
from network_mgr import NetworkManager

# --- 全局配置 ---
SCREEN_W, SCREEN_H = 960, 700
CELL_SIZE = 35
PANEL_W = 260
COLORS = {
    'bg': (220, 200, 170), 'grid': (0,0,0), 
    'btn': (70, 130, 180), 'btn_h': (100, 149, 237),
    'txt': (50, 50, 50), 'red': (200, 50, 50), 'blue': (50, 50, 200)
}

class ResourceManager:
    def __init__(self):
        self.images = {}
        pygame.font.init()
        # 字体自动回退
        candidates = ['SimHei', 'Microsoft YaHei', 'PingFang SC', 'Heiti TC', 'Arial Unicode MS']
        sys_fonts = pygame.font.get_fonts()
        font_name = 'arial'
        for f in candidates:
            if f.lower().replace(" ","") in sys_fonts:
                font_name = f; break
        self.font = pygame.font.SysFont(font_name, 24)
        self.s_font = pygame.font.SysFont(font_name, 16)
        try:
            self.images['board'] = pygame.image.load('assets/board.jpg')
            self.images['black'] = pygame.image.load('assets/black.png')
            self.images['white'] = pygame.image.load('assets/white.png')
        except: pass

class Button:
    def __init__(self, x, y, w, h, text, callback):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text; self.callback = callback; self.hovered = False
    
    def draw(self, screen, font):
        c = COLORS['btn_h'] if self.hovered else COLORS['btn']
        pygame.draw.rect(screen, c, self.rect, border_radius=5)
        ts = font.render(self.text, True, (255,255,255))
        screen.blit(ts, ts.get_rect(center=self.rect.center))

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.hovered: self.callback(); return True
        return False

# --- 主客户端 ---
class GUIClient:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("对战平台 v5.1 - 修复EVE无限弹窗")
        self.clock = pygame.time.Clock()
        self.res = ResourceManager()
        self.um = UserManager()
        self.net = None 
        
        self.game = None
        self.state = "MENU" # MENU, GAME, REPLAY, NET_WAIT
        self.mode_name = ""
        self.p_black_name = "游客"; self.p_white_name = "AI"
        
        # 联机状态
        self.my_net_color = None 
        self.is_network_game = False
        self.net_config_cache = {}

        self.buttons = []; self.logs = []
        self.sel_size = 15
        
        # AI 对象
        self.ai_black = None; self.ai_white = None
        self.last_ai_time = 0 # AI 思考冷却
        self.replay_moves = []; self.replay_idx = 0
        
        self.init_menu_buttons()

    def log(self, t):
        self.logs.append(str(t))
        if len(self.logs)>12: self.logs.pop(0)

    # --- 游戏启动逻辑 ---
    def start_game(self, gtype, mode):
        self.is_network_game = False
        self.start_game_common(gtype, mode)

    def start_game_common(self, gtype, mode):
        try:
            size = 8 if gtype == 'reversi' else self.sel_size
            self.game = GameFactory.create_game(gtype, size)
            
            curr = self.um.current_user if self.um.current_user else "游客"
            ai_name = "AI(智能)"
            
            self.ai_black = None; self.ai_white = None

            if self.is_network_game:
                pass 
            else:
                if mode == 'PVE':
                    self.ai_white = AIFactory.create_ai(gtype)
                    self.p_black_name = curr; self.p_white_name = ai_name
                elif mode == 'EVP':
                    self.ai_black = AIFactory.create_ai(gtype)
                    self.p_black_name = ai_name; self.p_white_name = curr
                elif mode == 'PVP':
                    self.p_black_name = curr; self.p_white_name = "对手(本地)"
                elif mode == 'EVE':
                    self.ai_black = AIFactory.create_ai(gtype)
                    self.ai_white = AIFactory.create_ai(gtype)
                    self.p_black_name = "AI-黑"; self.p_white_name = "AI-白"

            self.state = "GAME"
            self.mode_name = mode
            self.logs = [f"开始 {gtype} ({mode})"]
            self.init_game_buttons()
        except Exception as e: self.log(f"错误: {e}")

    # --- 核心修复：update_ai ---
    def update_ai(self):
        # 1. 如果游戏已结束，直接返回，不再执行后续逻辑
        if self.state != "GAME" or self.game.game_over: return
        if self.is_network_game: return 

        current_ai = None
        if self.game.current_player == BLACK: current_ai = self.ai_black
        else: current_ai = self.ai_white
        
        if current_ai:
            now = pygame.time.get_ticks()
            if now - self.last_ai_time < 500: return # 0.5秒冷却
            self.last_ai_time = now
            pygame.event.pump() 
            
            mv = current_ai.get_move(self.game)
            if mv:
                self.game.place_stone(mv[0], mv[1])
                if self.game.game_over: self.on_game_over()
            else:
                # AI 无棋可下
                if hasattr(self.game, 'pass_turn'):
                    self.game.pass_turn(); self.log("AI Pass")
                else:
                    # 关键修改：
                    # 1. 强制设置游戏结束，防止死循环
                    self.game.game_over = True 
                    self.log("AI无棋可下，强制结束")
                    # 2. 调用结算流程
                    self.on_game_over()

    # --- 网络联机模块 ---
    def _show_host_dialog(self):
        root = tk.Tk(); root.title("创建房间"); 
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = 300, 250; x, y = (sw-w)//2, (sh-h)//2
        root.geometry(f"{w}x{h}+{x}+{y}"); root.attributes('-topmost', True)

        res = {"gtype": None, "size": 15, "color": 1}

        tk.Label(root, text="游戏类型:").pack(pady=5)
        tm = {"五子棋": "gomoku", "围棋": "go", "黑白棋": "reversi"}
        cb = ttk.Combobox(root, values=list(tm.keys()), state="readonly")
        cb.current(0); cb.pack()

        tk.Label(root, text="大小 (8-19):").pack(pady=5)
        ent = tk.Entry(root); ent.insert(0, "15"); ent.pack()
        
        def on_cb(e):
            if cb.get() == "黑白棋": ent.delete(0, tk.END); ent.insert(0,"8")
            else: ent.delete(0, tk.END); ent.insert(0,"15")
        cb.bind("<<ComboboxSelected>>", on_cb)

        tk.Label(root, text="我执:").pack(pady=5)
        cv = tk.IntVar(value=1)
        f = tk.Frame(root); f.pack()
        tk.Radiobutton(f, text="黑", variable=cv, value=1).pack(side=tk.LEFT)
        tk.Radiobutton(f, text="白", variable=cv, value=2).pack(side=tk.LEFT)

        def ok():
            try:
                sz = int(ent.get())
                if not 8<=sz<=19: raise ValueError
                res["gtype"]=tm[cb.get()]; res["size"]=sz; res["color"]=cv.get()
                root.destroy()
            except: messagebox.showerror("Err","大小错误"); return
        
        tk.Button(root, text="创建", command=ok).pack(pady=15)
        root.mainloop()
        return res["gtype"], res["size"], res["color"]

    def cmd_net_host(self):
        gtype, size, myc = self._show_host_dialog()
        pygame.event.clear()
        if not gtype: return

        self.net = NetworkManager(is_server=True)
        suc, msg = self.net.start_server()
        self.log(msg)
        if not suc: return

        self.state = "NET_WAIT"
        name_map = {"gomoku":"五子棋","go":"围棋","reversi":"黑白棋"}
        self.mode_name = f"等待 ({name_map[gtype]})"
        self.init_menu_buttons()
        self.net_config_cache = {"gtype":gtype, "size":size, "host_color":myc}

    def cmd_net_join(self):
        root = tk.Tk(); root.withdraw(); root.attributes('-topmost',True)
        ip = simpledialog.askstring("连接", "主机IP:", initialvalue="127.0.0.1")
        root.destroy(); pygame.event.clear()
        if not ip: return

        self.net = NetworkManager(is_server=False)
        suc, msg = self.net.connect_to_server(ip)
        self.log(msg)
        if suc:
            self.state = "NET_WAIT"
            self.mode_name = "连接成功, 等待配置..."
            self.logs.append("等待主机开始...")
        else: self.net = None

    def _process_net(self):
        if not self.net: return
        while not self.net.msg_queue.empty():
            msg = self.net.msg_queue.get()
            t = msg.get("type")
            if t == "SYS":
                self.log(f"[网] {msg['msg']}")
                if self.net.is_server and "已连接" in msg['msg']:
                    self.start_network_game_host()
            elif t == "START": self.handle_net_start(msg)
            elif t == "MOVE": self.handle_net_move(msg)
            elif t == "UNDO": self.game.undo(); self.log("对方悔棋")
            elif t == "SURRENDER": self.log(self.game.surrender()); self.on_game_over()
            elif t == "PASS": 
                if hasattr(self.game,'pass_turn'): self.game.pass_turn(); self.log("对方Pass")
            elif t == "DISCONNECT":
                self.log("断开连接"); self.back_menu()

    def start_network_game_host(self):
        cfg = self.net_config_cache
        opp_c = WHITE if cfg['host_color']==BLACK else BLACK
        self.net.send({
            "type": "START", "gtype": cfg['gtype'], "size": cfg['size'],
            "your_color": opp_c, "host_name": self.um.current_user or "主机"
        })
        self.setup_net_game_local(cfg['gtype'], cfg['size'], cfg['host_color'], "客机")

    def handle_net_start(self, msg):
        self.setup_net_game_local(msg['gtype'], msg['size'], msg['your_color'], msg.get('host_name','主机'))

    def setup_net_game_local(self, gtype, size, my_c, opp_name):
        self.is_network_game = True
        self.my_net_color = my_c
        self.sel_size = size
        self.start_game_common(gtype, "NET")
        
        me = self.um.current_user or "我"
        if my_c == BLACK: self.p_black_name=me; self.p_white_name=opp_name
        else: self.p_black_name=opp_name; self.p_white_name=me
        self.mode_name = "联机对战"
        self.init_game_buttons()

    def handle_net_move(self, msg):
        self.game.place_stone(msg['r'], msg['c'])
        if self.game.game_over: self.on_game_over()

    def net_send_action(self, at, **kwargs):
        if self.is_network_game and self.net:
            d = {"type": at}; d.update(kwargs)
            self.net.send(d)

    # --- 游戏操作 ---
    def game_over_ui(self, title, is_win):
        root = tk.Tk(); root.withdraw(); root.attributes('-topmost',True)
        messagebox.showinfo("结束", title)
        root.destroy(); pygame.event.clear()
        if self.um.current_user: self.um.update_stats(is_win)

    def on_game_over(self):
        w = self.game.winner
        msg = "黑方胜" if w==BLACK else ("白方胜" if w==WHITE else "平局")
        is_win = False
        if self.is_network_game:
            if w == self.my_net_color: is_win = True
        else:
            if self.p_black_name == self.um.current_user and w == BLACK: is_win=True
            if self.p_white_name == self.um.current_user and w == WHITE: is_win=True
        self.game_over_ui(msg, is_win)

    def cmd_undo_proxy(self):
        if self.is_network_game: self.game.undo(); self.net_send_action("UNDO")
        else: self.game.undo()
    def cmd_surrender_proxy(self):
        self.log(self.game.surrender())
        if self.is_network_game: self.net_send_action("SURRENDER")
        self.on_game_over()
    def cmd_pass_proxy(self):
        if hasattr(self.game,'pass_turn'):
            self.game.pass_turn()
            if self.is_network_game: self.net_send_action("PASS")

    # --- 登录注册 ---
    def cmd_login(self):
        root = tk.Tk(); root.title("账户"); 
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = 320, 180; x, y = (sw-w)//2, (sh-h)//2
        root.geometry(f"{w}x{h}+{x}+{y}"); root.attributes('-topmost',True); root.resizable(False,False)

        tk.Label(root, text="用户名:").place(x=40,y=30)
        eu = tk.Entry(root); eu.place(x=100,y=30,width=160); eu.focus_set()
        tk.Label(root, text="密码:").place(x=40,y=70)
        ep = tk.Entry(root, show="*"); ep.place(x=100,y=70,width=160)

        def on_log():
            s, m = self.um.login(eu.get(), ep.get())
            if s: messagebox.showinfo("成功", m, parent=root); root.destroy()
            else: messagebox.showerror("失败", m, parent=root)
        def on_reg():
            s, m = self.um.register(eu.get(), ep.get())
            if s: messagebox.showinfo("成功", m+"\n请登录", parent=root)
            else: messagebox.showerror("失败", m, parent=root)

        tk.Button(root, text="登录", command=on_log, bg="#4CAF50", fg="white").place(x=60,y=120,width=80)
        tk.Button(root, text="注册", command=on_reg, bg="#2196F3", fg="white").place(x=180,y=120,width=80)
        root.mainloop()
        pygame.event.clear(); self.init_menu_buttons()

    # --- 渲染逻辑 ---
    def run(self):
        while True:
            self._process_net()
            self.update_ai()
            
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    if self.net: self.net.close()
                    pygame.quit(); sys.exit()
                
                handled = False
                for b in self.buttons:
                    if b.handle_event(e): handled=True; break
                if handled: continue
                
                if self.state == "GAME" and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    can = True
                    if self.is_network_game and self.game.current_player != self.my_net_color: can=False
                    if self.game.current_player==BLACK and self.ai_black: can=False
                    if self.game.current_player==WHITE and self.ai_white: can=False
                    
                    if can: self._handle_click(e.pos)

            self.screen.fill(COLORS['bg'])
            if self.state in ["MENU", "NET_WAIT"]:
                t = self.res.font.render(f"对战平台 - 尺寸: {self.sel_size}x{self.sel_size}", True, COLORS['txt'])
                self.screen.blit(t, (SCREEN_W//2-140, SCREEN_H//2-240))
                u = self.um.get_user_data(self.um.current_user)
                self.screen.blit(self.res.s_font.render(f"用户: {u}", True, (0,0,150)), (10, 10))
                if self.state == "NET_WAIT":
                    self.screen.blit(self.res.font.render(self.mode_name, True, (200,0,0)), (SCREEN_W//2-100, 300))
            else:
                self.draw_board_grid()
                self.draw_stones()
                self.draw_ui_panel()
            
            for b in self.buttons: b.draw(self.screen, self.res.s_font)
            pygame.display.flip(); self.clock.tick(30)

    def _handle_click(self, pos):
        bs = self.game.size * CELL_SIZE
        ox, oy = (SCREEN_W-PANEL_W-bs)//2, (SCREEN_H-bs)//2
        mg = CELL_SIZE//2
        if not (ox-mg < pos[0] < ox+bs+mg and oy-mg < pos[1] < oy+bs+mg): return

        is_rev = isinstance(self.game, GameFactory.create_game('reversi',8).__class__)
        if is_rev: c, r = int((pos[0]-ox)/CELL_SIZE), int((pos[1]-oy)/CELL_SIZE)
        else: c, r = round((pos[0]-ox)/CELL_SIZE), round((pos[1]-oy)/CELL_SIZE)
        
        if 0<=r<self.game.size and 0<=c<self.game.size:
            suc, msg = self.game.place_stone(r, c)
            self.log(msg)
            if suc and self.is_network_game: self.net_send_action("MOVE", r=r, c=c)
            if self.game.game_over: self.on_game_over()

    def draw_board_grid(self):
         bs = self.game.size * CELL_SIZE
         ox, oy = (SCREEN_W-PANEL_W-bs)//2, (SCREEN_H-bs)//2
         if 'board' in self.res.images: self.screen.blit(pygame.transform.scale(self.res.images['board'], (bs, bs)), (ox, oy))
         else: pygame.draw.rect(self.screen, (230,190,140), (ox, oy, bs, bs))
         for i in range(self.game.size+1):
             s, e = i*CELL_SIZE, self.game.size*CELL_SIZE
             pygame.draw.line(self.screen, COLORS['grid'], (ox, oy+s), (ox+e, oy+s))
             pygame.draw.line(self.screen, COLORS['grid'], (ox+s, oy), (ox+s, oy+e))

    def draw_stones(self):
        bs = self.game.size * CELL_SIZE
        ox, oy = (SCREEN_W-PANEL_W-bs)//2, (SCREEN_H-bs)//2
        is_rev = isinstance(self.game, GameFactory.create_game('reversi',8).__class__)
        off = CELL_SIZE//2 if is_rev else 0
        for r in range(self.game.size):
            for c in range(self.game.size):
                p = self.game.board[r][c]
                if p != EMPTY:
                    cx, cy = ox+c*CELL_SIZE+off, oy+r*CELL_SIZE+off
                    col = (0,0,0) if p==BLACK else (255,255,255)
                    pygame.draw.circle(self.screen, col, (cx, cy), 15)
                    if p==WHITE: pygame.draw.circle(self.screen, (0,0,0), (cx, cy), 15, 1)

    def draw_ui_panel(self):
        px = SCREEN_W - PANEL_W
        pygame.draw.rect(self.screen, (240,240,240), (px, 0, PANEL_W, SCREEN_H))
        u = self.um.get_user_data(self.um.current_user)
        self.screen.blit(self.res.s_font.render(f"用户: {u}", True, (0,0,150)), (px+10, 10))
        
        pygame.draw.rect(self.screen, (220,220,220), (px+5, 35, PANEL_W-10, 70))
        bc = COLORS['red'] if self.game.current_player==BLACK else COLORS['txt']
        wc = COLORS['blue'] if self.game.current_player==WHITE else COLORS['txt']
        self.screen.blit(self.res.s_font.render(f"● {self.p_black_name}", True, bc), (px+10, 40))
        self.screen.blit(self.res.s_font.render(f"○ {self.p_white_name}", True, wc), (px+10, 65))
        self.screen.blit(self.res.s_font.render(f"模式: {self.mode_name}", True, (100,100,100)), (px+10, 90))
        
        cp = "黑" if self.game.current_player==BLACK else "白"
        self.screen.blit(self.res.font.render(f"当前: {cp}", True, (0,0,0)), (px+10, 120))
        
        if self.is_network_game:
            role = "我执黑" if self.my_net_color==BLACK else "我执白"
            turn = "轮到我" if self.game.current_player==self.my_net_color else "对方..."
            c = (200,0,0) if self.game.current_player==self.my_net_color else (100,100,100)
            self.screen.blit(self.res.s_font.render(f"{role} | {turn}", True, c), (px+10, 150))

        y = SCREEN_H - 290
        for l in self.logs:
            self.screen.blit(self.res.s_font.render(str(l), True, (100,100,100)), (px+5, y)); y+=20

    def init_menu_buttons(self):
        self.buttons = []
        cx, cy = SCREEN_W//2, SCREEN_H//2
        if self.state == "NET_WAIT":
            self.buttons.append(Button(cx-80, cy+100, 160, 40, "取消/返回", self.back_menu))
            return

        self.buttons.append(Button(cx-100, cy-200, 200, 40, "登录 / 注册", self.cmd_login))
        self.buttons.append(Button(cx-60, cy-150, 40, 40, "-", lambda: self.ch_size(-1)))
        self.buttons.append(Button(cx+20, cy-150, 40, 40, "+", lambda: self.ch_size(1)))
        
        self.buttons.append(Button(cx-200, cy-100, 180, 40, "创建联机 (Host)", self.cmd_net_host))
        self.buttons.append(Button(cx+20, cy-100, 180, 40, "加入联机 (Join)", self.cmd_net_join))

        y = cy - 30
        for i, (k, n) in enumerate([('gomoku','五子棋'), ('go','围棋'), ('reversi','黑白棋')]):
            row = y + i*50
            self.buttons.append(Button(cx-220, row, 120, 40, f"{n} PVP", lambda k=k: self.start_game(k,'PVP')))
            self.buttons.append(Button(cx-80, row, 120, 40, f"{n} PVE", lambda k=k: self.start_game(k,'PVE')))
            self.buttons.append(Button(cx+60, row, 120, 40, f"{n} EVE", lambda k=k: self.start_game(k,'EVE')))
        
        self.buttons.append(Button(cx-160, cy+160, 140, 40, "读档", self.cmd_load))
        self.buttons.append(Button(cx+20, cy+160, 140, 40, "回放", self.cmd_replay))

    def init_game_buttons(self):
        self.buttons = []
        x, y = SCREEN_W-PANEL_W+20, 180
        if self.state == "GAME":
            self.buttons.append(Button(x, y, 160, 35, "悔棋", self.cmd_undo_proxy))
            self.buttons.append(Button(x, y+45, 160, 35, "存档", self.cmd_save))
            self.buttons.append(Button(x, y+90, 160, 35, "认负", self.cmd_surrender_proxy))
            if isinstance(self.game, GameFactory.create_game('go',9).__class__):
                self.buttons.append(Button(x, y+135, 160, 35, "虚着", self.cmd_pass_proxy))
        else:
            self.buttons.append(Button(x, y, 160, 35, "上一步", lambda: self.replay_step(-1)))
            self.buttons.append(Button(x, y+45, 160, 35, "下一步", lambda: self.replay_step(1)))
        
        self.buttons.append(Button(x, y+200, 160, 35, "返回菜单", self.back_menu))

    def back_menu(self):
        if self.net: self.net.close(); self.net=None
        self.state="MENU"; self.game=None; self.init_menu_buttons()
    def ch_size(self, d):
        n = self.sel_size+d
        if 8<=n<=19: self.sel_size=n; self.init_menu_buttons()
    
    def _get_file(self, mode='load'):
        root = tk.Tk(); root.withdraw(); root.attributes('-topmost',True)
        try:
            if mode=='save': p = filedialog.asksaveasfilename(defaultextension=".json")
            else: p = filedialog.askopenfilename(filetypes=[("JSON","*.json")])
        except: p = None
        root.destroy(); pygame.event.clear()
        return p

    def cmd_load(self):
        p = self._get_file('load')
        if not p: return
        try:
            with open(p) as f: d = json.load(f)
            t_map = {'GomokuGame':'gomoku','GoGame':'go','ReversiGame':'reversi'}
            self.game = GameFactory.create_game(t_map.get(d.get('type')), d.get('size',15))
            suc, meta = self.game.load_from_file(p)
            if suc:
                self.state = "GAME"
                self.mode_name = meta.get('mode', '读档')
                self.p_black_name = meta.get('black', '未知')
                self.p_white_name = meta.get('white', '未知')
                self.init_game_buttons()
        except Exception as e: self.log(f"Err: {e}")

    def cmd_save(self):
        p = self._get_file('save')
        if p:
            meta = {"black": self.p_black_name, "white": self.p_white_name, "mode": self.mode_name}
            suc, msg = self.game.save_to_file(p, meta)
            self.log(msg)

    def cmd_replay(self):
        p = self._get_file('load')
        if not p: return
        try:
            with open(p) as f: d = json.load(f)
            t_map = {'GomokuGame':'gomoku','GoGame':'go','ReversiGame':'reversi'}
            self.game = GameFactory.create_game(t_map.get(d.get('type')), d.get('size',15))
            self.replay_moves = d.get('history', [])
            if not self.replay_moves: self.replay_moves = d.get('move_history', [])
            self.replay_idx = 0
            self.game = GameFactory.create_game(t_map.get(d.get('type')), d.get('size',15))
            self.state = "REPLAY"
            self.mode_name = "回放"
            self.init_game_buttons()
        except: self.log("回放失败")

    def replay_step(self, d):
        if d == 1 and self.replay_idx < len(self.replay_moves):
            mv = self.replay_moves[self.replay_idx]; self.replay_idx += 1
            if mv == "PASS": 
                if hasattr(self.game, 'pass_turn'): self.game.pass_turn()
            else: self.game.place_stone(mv[0], mv[1])
        elif d == -1 and self.replay_idx > 0:
            self.game.undo(); self.replay_idx -= 1

if __name__ == "__main__":
    GUIClient().run()