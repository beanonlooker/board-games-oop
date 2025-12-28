import json
import os
import hashlib

USER_FILE = "users.json"

class UserManager:
    def __init__(self):
        self.users = self._load()
        self.current_user = None

    def _load(self):
        if not os.path.exists(USER_FILE): return {}
        try:
            with open(USER_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}

    def _save(self):
        with open(USER_FILE, 'w', encoding='utf-8') as f: json.dump(self.users, f, indent=4)

    def register(self, user, pwd):
        if user in self.users: return False, "用户已存在"
        if not user or not pwd: return False, "不能为空"
        self.users[user] = {
            "pwd": hashlib.md5(pwd.encode()).hexdigest(),
            "wins": 0, "total": 0
        }
        self._save()
        return True, "注册成功"

    def login(self, user, pwd):
        if user not in self.users: return False, "用户不存在"
        if self.users[user]["pwd"] != hashlib.md5(pwd.encode()).hexdigest():
            return False, "密码错误"
        self.current_user = user
        return True, f"欢迎回来, {user}"

    def logout(self):
        self.current_user = None

    def update_stats(self, is_win):
        if self.current_user:
            self.users[self.current_user]["total"] += 1
            if is_win: self.users[self.current_user]["wins"] += 1
            self._save()

    def get_user_data(self, username):
        if not username or username not in self.users: return "游客"
        u = self.users[username]
        rate = 0
        if u['total'] > 0: rate = int((u['wins'] / u['total']) * 100)
        return f"{username} (胜{u['wins']}/局{u['total']} {rate}%)"