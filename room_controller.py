from random import randint
from moudle import *

class RoomController:
    def __init__(self):
        self.rooms = {}

    def _generate_unique_room_number(self):
        while True:
            num = randint(10000, 99999)
            if num not in self.rooms:
                return num
            
    def create_room(self, client_id, data):
        try:
            player_name = data.get("player_name", "未命名玩家")
            room_num = self._generate_unique_room_number()
            new_room = room(room_num)

            new_player = player(client_id, player_name)
            new_room.players[client_id] = new_player

            self.rooms[room_num] = new_room
            print(f"[Room_controller] 玩家 {player_name}({client_id}) 創建了新房間 [{room_num}]")

            return {
                "action" : "CreateRoomResponse",
                "status" : "Success",
                "room_number" : room_num
            }
        except Exception as e:
            return {
                "action" : "CreateRoomResponse",
                "status" : "Fail",
                "exception" : e
            }
        
    def join_room(self, client_id, data):
        print(self.rooms)
        try:
            player_name = data.get("player_name", "未命名玩家")
            room_num = data.get("room_number")
            target = self.rooms[room_num]

            if room_num not in self.rooms:
                print(f"[Room_controller] 玩家 {player_name}嘗試加入不存在的房號 [{room_num}]")
                return {
                    "action" : "JoinRoomResponse",
                    "status" : "Fail",
                    "exception" : "room doesn't exist."
                }
            
            if target.status != "LOBBY":
                print(f"[Room_controller] 玩家 {player_name}嘗試加入已經開始的房間 [{room_num}]")
                return {
                    "action" : "JoinRoomResponse",
                    "status" : "Fail",
                    "exception" : "room is already started."
                }
            
            new_player = player(client_id, player_name)
            target.players[client_id] = new_player

            print(f"[Room_controller] 玩家 {player_name}({client_id}) 成功加入了房間 [{room_num}]")

            return{
                "action" : "JoinRoomResponse",
                "status" : "Success",
                "room_number" : room_num
            }
        
        except Exception as e:
            print(f"[Room_controller] 玩家 {player_name}({client_id}) 加入失敗 {e}")
            return {
                    "action" : "JoinRoomResponse",
                    "status" : "Fail",
                    "exception" : e
            }
        
    def leave_room(self, client_id, data):
        try:
            room_num = data.get("room_number")
            player_name = data.get("player_name", "未命名玩家")

            if room_num not in self.rooms:
                print(f"[Room_controller] 玩家 {player_name}({client_id}) 離開失敗 : 房間不存在")
                return{
                    "action" : "LeaveRoomResponse",
                    "status" : "Fail",
                    "exception" : "room doesn't exist"
                }
            
            room = self.rooms[room_num]

            if client_id in room.players:
                left_player = room.players.pop(client_id)
                print(f"[Room_controller] 玩家 {player_name}({client_id}) 主動離開了房間 [{room_num}]")

                if not room.players:
                    del self.rooms[room_num]
                    print(f"[Room_controller] 房間 [{room_num}] 已經沒有任何人，自動銷毀房間")
                    return{
                        "action" : "LeaveRoomResponse",
                        "status" : "Success",
                        "room_closed" : True
                    }

                return{
                    "action" : "LeaveRoomResponse",
                    "status" : "Success"
                }
            else:
                print(f"[Room_controller] 玩家 {player_name}({client_id}) 離開失敗 : 玩家不在房間中")
                return{
                    "action" : "LeaveRoomResponse",
                    "status" : "Fail",
                    "exception" : "player not in the room"
                }
            
        except Exception as e:
            print(f"[Room_controller] 玩家 {player_name}({client_id}) 離開失敗")
            return {
                "action" : "LeaveRoomResponse",
                "status" : "Fail",
                "exception" : e
            }


    def disconnect(self, client_id):
        for room_num, target_room in list(self.rooms.items()):
            if client_id in target_room.players:
                dropped_player = target_room.players.pop(client_id)
                print(f"[Room_controller] 偵測到斷線：玩家 {dropped_player.name} 斷開連線 [{room_num}]")

                if target_room.status != "LOBBY" or not target_room.players:
                    if room_num in self.rooms:
                        del self.rooms[room_num]
                    print(f"[Room_controller] 房間 [{room_num}] 遊戲中有人斷線或已無人，自動關閉並銷毀房間")
                    return {
                        "room_number": room_num,
                        "room_closed": True,  
                        "remaining_client_ids": list(target_room.players.keys())
                    }
                else:
                    remaining_members = [p.name for p in target_room.players.values()]
                    return {
                        "room_number": room_num,
                        "room_closed": False, 
                        "remaining_members": remaining_members
                    }
                
        return None

    def create_player_list(self, room_num):
        List = []
        for player in self.rooms[room_num].players.values():
            List.append(player.name)

        return List
    
room_controller = RoomController()


