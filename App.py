import queue
from communicate import Communicator
from room_controller import room_controller
from moudle import *
from game import Game

def broadcast_to_room(communicator, room_num, message_dict):
    target_room = room_controller.rooms.get(room_num)
    if target_room:
        for cid in target_room.players.keys():
            communicator.send(cid, message_dict)

def send_renew_room_status(communicator, room_num, members_list):
    renew_packet = {
        "action": "RenewRoomStatus",
        "room_status": {
            "room_number": room_num,
            "players": members_list
        }
    }
    broadcast_to_room(communicator, room_num, renew_packet)

def main():
    communicator = Communicator(port=65432)
    communicator.start_server()

    while True:
        try:
            packet = communicator.msg.get(block=True, timeout=0.1)
            client_id = packet["client_id"]
            event = packet["event"]
            data = packet["data"]
            print(f"[App] 玩家 {client_id} 傳送了 {data}")
            if event == "CreateRoom":                 
                response = room_controller.create_room(client_id, data)
                communicator.send(client_id, response)
                if response["status"] == "Success":
                    player_name = data.get("player_name", "未命名玩家")
                    send_renew_room_status(communicator, response["room_number"], [player_name])

            elif event == "JoinRoom":
                response = room_controller.join_room(client_id, data)
                room_num = data.get("room_number")

                client_response = {
                        "action": response["action"],
                        "status": response["status"]
                }
                
                if "room_number" in response:
                    client_response["room_number"] = response["room_number"]
                
                if "exception" in response:
                    client_response["exception"] = response["exception"]

                communicator.send(client_id, client_response)

                if response["status"] == "Success":
                        player_list = room_controller.create_player_list(room_num)
                        send_renew_room_status(communicator, int(room_num), player_list)

            elif event == "LeaveRoom":
                response = room_controller.leave_room(client_id, data)
                room_num = data.get("room_number")

                client_response = {
                        "action": response["action"],
                        "status": response["status"]
                }

                if "exception" in response:
                        client_response["exception"] = response["exception"]

                communicator.send(client_id, client_response)

                if response["status"] == "Success" and not response.get("room_closed", False):
                        player_list = room_controller.create_player_list(room_num)
                        send_renew_room_status(communicator, int(room_num), player_list)

            elif event == "disconnect":
                disconnect_report = room_controller.disconnect(client_id)
                
                if disconnect_report:
                    room_num = disconnect_report["room_number"]
                    
                    if disconnect_report["room_closed"]:
                        terminate_packet = {
                            "action": "LeaveRoomResponse",
                            "status": "Success",
                            "note": "Someone disconnected. Game room has closed."
                        }
                        for cid in disconnect_report["remaining_client_ids"]:
                            communicator.send(cid, terminate_packet)
                    else:
                        send_renew_room_status(communicator, int(room_num), disconnect_report["remaining_members"])

            elif event == "StartGame":
                room_num = data.get("room_number")
                room_num = int(room_num)

                target_room = room_controller.rooms.get(room_num)
                if target_room and target_room.status == "LOBBY":
                    target_room.status = "PLAYING"

                    game_instance = Game(room_num, target_room.players)
                    target_room.game_instance = game_instance
                    print(f"[App] 房間 [{room_num}] 已成功初始化Game，開始向前端發送開戰資料...")

                    packets_to_send = game_instance.start_game_setup()
                    
                    for pack in packets_to_send:
                        target = pack["target"]
                        msg_data = pack["data"]
                        
                        if target == "broadcast":
                            broadcast_to_room(communicator, room_num, msg_data)
                        else:
                            communicator.send(target, msg_data)
            
            elif event == "playCard":
                room_num = data.get("room_number")
                room_num = int(room_num)

                target_room = room_controller.rooms.get(room_num)
                if target_room and target_room.status == "PLAYING" and target_room.game_instance:
                    game_instance = target_room.game_instance
                    packets_to_send = game_instance.handle_play_card(client_id, data)

                    for pack in packets_to_send:
                        target = pack["target"]
                        msg_data = pack["data"]
                        if target == "broadcast":
                            broadcast_to_room(communicator, room_num, msg_data)
                        else:
                            communicator.send(target, msg_data)

            elif event == "playCardRespond":
                room_num = data.get("room_number")
                room_num = int(room_num)

                target_room = room_controller.rooms.get(room_num)
                if target_room and target_room.status == "PLAYING" and target_room.game_instance:
                    game_instance = target_room.game_instance

                    packets_to_send = game_instance.handle_play_card_respond(client_id, data)

                    game_over = False
                    for pack in packets_to_send:
                        target   = pack["target"]
                        msg_data = pack["data"]
                        if target == "broadcast":
                            broadcast_to_room(communicator, room_num, msg_data)
                        else:
                            communicator.send(target, msg_data)
                        if msg_data.get("action") == "GameWin":
                            game_over = True

                    if game_over and room_num in room_controller.rooms:
                        del room_controller.rooms[room_num]
                        print(f"[App] 房間 [{room_num}] 遊戲結束，房間已關閉。")

            communicator.msg.task_done()

        except queue.Empty:
            pass
        except KeyboardInterrupt:
            print("\n[App] 伺服器已安全關閉。")
            break
        except Exception as e:
             print(f"[App] 發生未預期錯誤: {e}")

if __name__ == "__main__":
     main()