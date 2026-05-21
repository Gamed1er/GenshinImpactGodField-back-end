import socket
import json
import queue
import threading

class Communicator:
    def __init__(self, host="0.0.0.0", port=65432):
        self.host = host
        self.port = port
        self.msg = queue.Queue()
        self.clients = {}
        self.client_counter = 0

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def start_server(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()

        print(f"[Communicator] 伺服器已啟動，正監聽Port {self.port}")

        accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        accept_thread.start()

    def _accept_loop(self):
        while True:
            try:
                client_socket, addr = self.server_socket.accept()
                self.client_counter += 1
                client_id = f"player_{self.client_counter}"
                self.clients[client_id] = client_socket

                print(f"[Communicator] 玩家連線來自 {addr}，指派ID: {client_id}")
                self.enqueue(client_id, "connect", {})

                client_thread = threading.Thread(
                    target=self._listen_client_loop, 
                    args=(client_id, client_socket), 
                    daemon=True
                )
                client_thread.start()

            except Exception as e:
                print(f"[Communicator] 連線異常 : {e}")
                break

    def _listen_client_loop(self, client_id, client_socket):
        buffer = ""
        try:
            while True:
                data = client_socket.recv(4096).decode('utf-8')
                if not data:
                    break

                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                        
                    try:
                        raw_data = json.loads(line)
                        event_name = raw_data.get("action", "unknown")

                        print(f"[Communicator] 收到來自 {client_id} 的原始包裹 -> action : {event_name}")
                        self.enqueue(client_id, event_name, raw_data)
                    except json.JSONDecodeError:
                        print(f"[Communicator] 來自 {client_id} 的訊息無法解析為JSON : {line}")

        except ConnectionResetError:
            pass
        except Exception as e:
            print(f"[Communicator] 玩家 {client_id} 發生異常 : {e}")
        finally:
            print(f"[Communicator] 玩家 {client_id} 離開連線")

            if client_id in self.clients:
                del self.clients[client_id]
            try:
                client_socket.close()
            except:
                pass

            self.enqueue(client_id, "disconnect", {})

    def enqueue(self, client_id, event_name, data):
        packet = {
            "client_id": client_id,
            "event": event_name,
            "data": data
        }

        self.msg.put(packet)

    def send(self, client_id, data_dict):
        client_socket = self.clients.get(client_id)
        if not client_socket:
            print(f"[Communicator] 發送失敗，找不到該玩家的連線: {client_id}")
            return
        
        try:
            message_str = json.dumps(data_dict) + "\n"
            client_socket.sendall(message_str.encode('utf-8'))
            print(f"[Communicator] 已將訊息送給 {client_id}")
        except Exception as e:
            print(f"[Communicator] {client_id}: {e}")