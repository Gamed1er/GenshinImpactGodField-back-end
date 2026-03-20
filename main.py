import socket
import json

# 存放房間資料的字典：{ "12345": ["Name1", "Name2"] }
rooms = {}

def start_server():
    host = '0.0.0.0'
    port = 65432
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen()
        print(f"房間伺服器已啟動...")

        while True:
            conn, addr = s.accept()
            with conn:
                while True:
                    try:
                        data = conn.recv(1024).decode('utf-8')
                        if not data: break
                        request = json.loads(data)
                        action = request.get("action")

                        if action == "CreateRoom":
                            room_id = "12345" # 測試用固定房號
                            player_name = request.get("player_name")
                            rooms[room_id] = [player_name]
                            
                            # 1. 回傳成功創建
                            response = {"action": "CreateRoomResponse", "status": "Success", "room_number": room_id}
                            conn.sendall((json.dumps(response) + "\n").encode('utf-8'))
                            
                            # 2. 立即發送房間狀態更新
                            renew_msg = {
                                "action": "RenewRoomStatus",
                                "room_status": {"room_number": room_id, "players": rooms[room_id]}
                            }
                            conn.sendall((json.dumps(renew_msg) + "\n").encode('utf-8'))

                        elif action == "JoinRoom":
                            room_id = request.get("room_number")
                            player_name = request.get("player_name")
                            
                            if room_id in rooms:
                                rooms[room_id].append(player_name)
                                # 回傳加入成功
                                response = {"action": "JoinRoomResponse", "status": "Success", "room_number": room_id}
                                conn.sendall((json.dumps(response) + "\n").encode('utf-8'))
                                
                                # 更新房間狀態
                                renew_msg = {
                                    "action": "RenewRoomStatus",
                                    "room_status": {"room_number": room_id, "players": rooms[room_id]}
                                }
                                conn.sendall((json.dumps(renew_msg) + "\n").encode('utf-8'))
                            else:
                                response = {"action": "JoinRoomResponse", "status": "Fail"}
                                conn.sendall((json.dumps(response) + "\n").encode('utf-8'))

                    except Exception as e:
                        print(f"錯誤: {e}")
                        break

start_server()