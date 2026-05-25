import queue
import time
from communicate import Communicator
from room_controller import room_controller
from moudle import *

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

                if response["status"] == "Success":
                        print(111)
                        player_list = room_controller.create_player_list(room_num)
                        print(player_list)
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
                        send_renew_room_status(communicator, int(room_num), response["members_internal"])

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