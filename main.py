# 這是我的測試程式，就 Gemini 生成的，鱈魚香絲你可以把它刪掉搞新的

import socket
import json

def start_test_server():
    host = '0.0.0.0'
    port = 65432
    
    # 使用 socket 監聽
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen()
        print(f"穩定版測試伺服器已啟動，監聽 Port: {port}...")
        
        while True:  # 外層循環：伺服器永遠不死掉
            conn, addr = s.accept()
            print(f"玩家連線自: {addr}")
            
            with conn:
                while True: # 內層循環：持續處理同一個玩家的訊息
                    try:
                        data = conn.recv(1024).decode('utf-8')
                        if not data: # 玩家正常關閉連線
                            break
                        
                        request = json.loads(data)
                        action = request.get("action")
                        
                        if action == "CreateRoom":
                            print(f"【請求】創建房間：{request.get('player_name')}")
                            response = {"action": "CreateRoomResponse", "status": "Success", "room_number": 12345}
                            conn.sendall((json.dumps(response) + "\n").encode('utf-8'))
                            
                        elif action == "JoinRoom":
                            room_id = request.get("room_number")
                            print(f"【請求】加入房間：玩家 {request.get('player_name')} 嘗試加入房號 {room_id}")
                            
                            # 簡單模擬邏輯：只有 12345 能進去
                            if room_id == "12345":
                                response = {"action": "JoinRoomResponse", "status": "Success"}
                            else:
                                response = {"action": "JoinRoomResponse", "status": "Fail", "message": "找不到房間"}
                            conn.sendall((json.dumps(response) + "\n").encode('utf-8'))

                    except ConnectionResetError:
                        print("玩家強制斷開連線，準備迎接下一位玩家。")
                        break
                    except Exception as e:
                        print(f"發生錯誤: {e}")
                        break

if __name__ == "__main__":
    start_test_server()