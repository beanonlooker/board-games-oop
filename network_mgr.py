import socket
import threading
import json
import queue
import time

# 默认端口
DEFAULT_PORT = 8899

class NetworkManager:
    def __init__(self, is_server=False):
        self.is_server = is_server
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn = None # 实际用于通信的socket对象
        self.running = True
        self.msg_queue = queue.Queue() # 消息队列，供GUI轮询
        self.connected = False
        self.remote_addr = None

    def start_server(self, port=DEFAULT_PORT):
        """启动服务端，等待连接"""
        try:
            self.sock.bind(('0.0.0.0', port))
            self.sock.listen(1)
            #开启线程等待连接，避免阻塞主界面
            threading.Thread(target=self._accept_client, daemon=True).start()
            return True, f"服务启动，监听端口 {port}..."
        except Exception as e:
            return False, str(e)

    def _accept_client(self):
        try:
            self.conn, addr = self.sock.accept()
            self.remote_addr = addr
            self.connected = True
            self.msg_queue.put({"type": "SYS", "msg": f"客户端 {addr} 已连接"})
            # 开启接收线程
            threading.Thread(target=self._recv_loop, daemon=True).start()
        except:
            pass

    def connect_to_server(self, ip, port=DEFAULT_PORT):
        """连接到服务端"""
        try:
            self.sock.connect((ip, port))
            self.conn = self.sock
            self.connected = True
            self.msg_queue.put({"type": "SYS", "msg": f"已连接到 {ip}:{port}"})
            threading.Thread(target=self._recv_loop, daemon=True).start()
            return True, "连接成功"
        except Exception as e:
            return False, str(e)

    def _recv_loop(self):
        """后台接收消息循环"""
        while self.running and self.conn:
            try:
                data = self.conn.recv(4096)
                if not data: break
                
                msg_str = data.decode('utf-8')
                try:
                    msg = json.loads(msg_str)
                    self.msg_queue.put(msg)
                except:
                    print(f"解析失败: {msg_str}")
                    
            except ConnectionResetError:
                break
            except Exception as e:
                print(f"网络错误: {e}")
                break
        
        self.connected = False
        self.msg_queue.put({"type": "SYS", "msg": "连接断开"})
        self.msg_queue.put({"type": "DISCONNECT"})

    def send(self, data_dict):
        """发送JSON消息"""
        if self.conn and self.connected:
            try:
                msg = json.dumps(data_dict)
                self.conn.sendall(msg.encode('utf-8'))
            except Exception as e:
                print(f"发送失败: {e}")

    def close(self):
        self.running = False
        if self.conn: self.conn.close()
        if self.sock: self.sock.close()