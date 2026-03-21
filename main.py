import socket
import json
import random

# 存放房間資料的字典：{ "12345": ["Name1", "Name2"] }
rooms = {}

def start_server():
    host = '127.0.0.1'
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
                            room_id = random.randint(10000, 99999) # 測試用固定房號
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
                        
                        elif action == "LeaveRoom":
                            room_id = request.get("room_number")
                            player_name = request.get("player_name")
                            
                            # 統一轉換為字串比較，避免型別錯誤
                            room_id = str(room_id) if room_id else None
                            
                            if room_id in rooms:
                                if player_name in rooms[room_id]:
                                    rooms[room_id].remove(player_name)
                                    print(f"【請求】離開房間：玩家 {player_name} 已離開房號 {room_id}")
                                    
                                    # 如果房間沒人了，釋放記憶體
                                    if not rooms[room_id]:
                                        del rooms[room_id]
                                        print(f"房間 {room_id} 已空，正式關閉。")
                                    
                                    # 回傳成功訊息
                                    response = {"action": "LeaveRoomResponse", "status": "Success"}
                                    conn.sendall((json.dumps(response) + "\n").encode('utf-8'))
                                    
                                    # 如果你之後實作了廣播系統，這裡應該還要發送 RenewRoomStatus 給房間內剩餘的人
                                else:
                                    response = {"action": "LeaveRoomResponse", "status": "Fail", "message": "玩家不在房間內"}
                                    conn.sendall((json.dumps(response) + "\n").encode('utf-8'))
                            else:
                                response = {"action": "LeaveRoomResponse", "status": "Fail", "message": "找不到房間"}
                                conn.sendall((json.dumps(response) + "\n").encode('utf-8'))


                    except Exception as e:
                        print(f"錯誤: {e}")
                        break

start_server()