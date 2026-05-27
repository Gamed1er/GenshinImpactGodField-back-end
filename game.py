from moudle import *
import os
import json
import random

class Game:
    def __init__(self, room_number, players_dict):
        self.room_number = room_number
        self.players = players_dict

        self.card_pool = self._load_card_pool()
        self.cards_database = self._load_cards_database()
        self.current_turn_id = None
        self.turn_type = "Action"

        self.active_combat = {
            "attacker_id": None,
            "target_id": None,
            "attack_value": 0,
            "attack_cards": []
        }

    def _load_card_pool(self):
        try:
            with open("Cards/card.json", "r", encoding="utf-8") as f:
                card_data = json.load(f)
                return list(card_data.keys())
        except Exception as e:
            print(f"[Game] 無法讀取 Cards/card.json : {e}")
            return [f"card{i}" for i in range(1, 21)]
        
    def _load_cards_database(self):
        database = {}
        cards_dir = "Cards"

        for file_name in os.listdir(cards_dir):
            if file_name.endswith(".json") and file_name != "card.json":
                file_path = os.path.join(cards_dir, file_name)
                with open(file_path, "r", encoding="utf-8") as f:
                    card_content = json.load(f)
                    card_id = card_content.get("id")
                    if card_id:
                        database[card_id] = card_content
                        print(f"[Game] 成功載入單張卡片檔案: {card_id} ({file_name})")
        return database
        
    def draw_random_cards(self, count):
        drawn = []
        for _ in range(count):
            if self.card_pool:
                drawn.append(random.choice(self.card_pool))
        return drawn
    
    def start_game_setup(self):
        try:
            for p in self.players.values():
                p.alive = True
                p.hp = 50
                p.mp = 10
                p.element = "NONE"
                p.strength = 0
                p.agile = 0
                p.shield = 0
                p.burning = 0
                p.frozen = 0

                p.hand = self.draw_random_cards(8)

            client_ids = list(self.players.keys())
            self.current_turn_id = random.choice(client_ids)
            self.turn_type = "Action"
            print(f"[Game] 房間 [{self.room_number}] 玩家初始手牌發放完畢。先攻輪到: {self.players[self.current_turn_id].name}")

            dispatch_list = []
            dispatch_list.append({
                "target": "broadcast",
                "data": {"action": "GameStarted"}
            })

            public_players_info = []
            for p in self.players.values():
                public_players_info.append({
                    "name": p.name,
                    "alive": p.alive,
                    "hp": p.hp,
                    "mp": p.mp,
                    "element": p.element,
                    "strength": p.strength,
                    "agile": p.agile,
                    "shield" : p.shield,
                    "burning": p.burning,
                    "frozen": p.frozen
                })

            for cid, p in self.players.items():
                dispatch_list.append({
                    "target": cid, 
                    "data": {
                        "action": "RenewGameStatus",
                        "players": public_players_info,
                        "cards": p.hand
                    }
                })

            for cid, p in self.players.items():
                if(self.current_turn_id == cid):
                    dispatch_list.append({
                    "target": cid, 
                    "data": {
                        "action": "PlayerTurns",
                        "type" : "Action"
                        }
                    })
                else:
                    dispatch_list.append({
                    "target": cid, 
                    "data": {
                        "action": "PlayerTurns",
                        "type" : "None"
                        }
                    })



            

            return dispatch_list
        except Exception as e:
            print(f"[Game] 發生錯誤 {e}")
    
    def _get_public_players_info(self):
        return [{
            "name": p.name, "alive": p.alive, "hp": p.hp, "mp": p.mp,
            "element": p.element, "strength": p.strength, "agile": p.agile, "shield" : p.shield,
            "burning": p.burning, "frozen": p.frozen
        } for p in self.players.values()]
    
    def handle_play_card(self, client_id, data):
        print(data)
        attacker_name = data.get("attacker")
        target_name = data.get("target")
        played_card_ids = data.get("cards", [])

        for cid, p  in self.players.items():
            if p.name == attacker_name:
                attacker_obj = p
                break

        for card_id in played_card_ids:
            if card_id in attacker_obj.hand:
                attacker_obj.hand.remove(card_id)

        total_attack = 0
        for card_id in played_card_ids:
            card_info = self.cards_database.get(card_id)
            if card_info:
                total_attack += card_info.get("attribute", {}).get("attack", 0)

        dispatch_list = []
        action_display = {
            "action": "PlayerAction",
            "attacker": attacker_obj.name,
            "target": target_name,
            "card": played_card_ids,
            "damage_details": {
                "final_damage" : total_attack,
                "is_true_damage" : False, 
                "addition" : [],
                "element" : "NONE"
            }
        }
        dispatch_list.append({"target": "broadcast", "data": action_display})

        is_offensive = (total_attack > 0 and target_name and target_name != attacker_obj.name)

        if not is_offensive:
            attacker_obj.hand.extend(self.draw_random_cards(len(played_card_ids)))

            all_ids = list(self.players.keys())
            curr_idx = all_ids.index(self.current_turn_id)
            self.current_turn_id = all_ids[(curr_idx + 1) % len(all_ids)]
            self.turn_type = "Action"

            public_info = self._get_public_players_info()
            for cid, p in self.players.items():
                dispatch_list.append({
                    "target": cid,
                    "data": {"action": "RenewGameStatus", "players": public_info, "cards": p.hand}
                })

            next_player_name = self.players[self.current_turn_id].name
            for cid, p in self.players.items():
                if p.name == next_player_name:
                    dispatch_list.append({
                        "target": cid,
                        "data": {"action": "PlayerTurns", "type": "Action"}
                    })
                else:
                    dispatch_list.append({
                        "target": cid,
                        "data": {"action": "PlayerTurns", "type": "None"}
                    })

        else:
            target_id = None
            for cid, p in self.players.items():
                if p.name == target_name:
                    target_id = cid
                    break

            if target_id:
                print(target_name)
                self.active_combat["attacker_id"] = attacker_obj.id
                self.active_combat["target_id"] = target_id
                self.active_combat["attack_value"] = total_attack
                self.active_combat["attack_cards"] = played_card_ids

                self.turn_type = "Respond"

                for cid, p in self.players.items():
                    if cid == target_id:
                        dispatch_list.append({
                            "target": cid,
                            "data": {"action": "PlayerTurns", "type": "Response"}
                        })
                    else:
                        dispatch_list.append({
                            "target": cid,
                            "data": {"action": "PlayerTurns", "type": "None"}
                        })

        return dispatch_list
    
    def handle_play_card_respond(self, client_id, data):
        target_obj = self.players[client_id]
        respond_card_ids = data.get("cards", [])

        for card_id in respond_card_ids:
            if card_id in target_obj.hand:
                target_obj.hand.remove(card_id)

        total_defense = 0
        for card_id in respond_card_ids:
            card_info = self.cards_database.get(card_id)
            if card_info:
                total_defense += card_info.get("attribute", {}).get("defense", 0)

        dispatch_list = []

        response_display = {
            "action": "PlayerResponse",
            "attacker": self.players[self.active_combat["attacker_id"]].name,
            "target": target_obj.name,
            "card": respond_card_ids,
            "damage_details" : {
                "final_defense" : total_defense,
                "addition" : []
            }
        }

        dispatch_list.append({"target": "broadcast", "data": response_display})

        raw_damage = self.active_combat["attack_value"]
        final_damage = max(0, raw_damage - total_defense)
        
        target_obj.hp = max(0, target_obj.hp - final_damage)
        if target_obj.hp == 0:
            target_obj.alive = False

        attacker_obj = self.players[self.active_combat["attacker_id"]]
        attacker_obj.hand.extend(self.draw_random_cards(len(self.active_combat["attack_cards"])))
        target_obj.hand.extend(self.draw_random_cards(len(respond_card_ids)))

        dispatch_list.append({
            "target": "broadcast",
            "data": {
                "action" : "PlayerRoundEnd",
                "effects" : [
                    {
                        "target" : f"{attacker_obj.name} / {target_obj.name}",
                        "type" : "damage",
                        "amount" : final_damage
                    }
                ]
            }
        })

        all_ids = list(self.players.keys())
        curr_idx = all_ids.index(self.current_turn_id)
        self.current_turn_id = all_ids[(curr_idx + 1) % len(all_ids)]
        self.turn_type = "Action"

        self.active_combat = {"attacker_id": None, "target_id": None, "attack_value": 0, "attack_cards": []}

        public_info = self._get_public_players_info()
        for cid, p in self.players.items():
            dispatch_list.append({
                "target": cid,
                "data": {"action": "RenewGameStatus", "players": public_info, "cards": p.hand}
            })

        next_player_name = self.players[self.current_turn_id].name

        for cid, p in self.players.items():
            if p.name == next_player_name:
                dispatch_list.append({
                    "target": cid,
                    "data": {"action": "PlayerTurns", "type": "Action"}
                })
            else:
                dispatch_list.append({
                    "target": cid,
                    "data": {"action": "PlayerTurns", "type": "None"}
                })
        return dispatch_list
    
