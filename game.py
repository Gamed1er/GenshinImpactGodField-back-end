from moudle import player
from effect_processor import EffectProcessor
import os
import json
import random


class Game:
    def __init__(self, room_number, players_dict):
        self.room_number  = room_number
        self.players      = players_dict          # { client_id: player }

        self.card_pool       = self._load_card_pool()
        self.cards_database  = self._load_cards_database()

        self.current_turn_id = None
        self.turn_type       = "Action"           # "Action" | "Respond"

        # 當前進行中的戰鬥狀態
        self.active_combat = {
            "attacker_id"   : None,
            "attack_value"  : 0,
            "attack_cards"  : [],
            "attack_element": "NONE",
            "is_true_damage": False,
            "is_aoe"        : False,
        }

        # 範圍攻擊排隊等待回應的受害者（先進先出）
        self.defense_queue: list[str] = []

    # ════════════════════════════════════════════════
    #  資源載入
    # ════════════════════════════════════════════════

    def _load_cards_database(self) -> dict:
        database = {}
        base_dir = "Cards"
        for folder in ["Defense", "Weapon", "Skill", "Other"]:
            folder_path = os.path.join(base_dir, folder)
            for file_name in os.listdir(folder_path):
                if file_name.endswith(".json"):
                    with open(os.path.join(folder_path, file_name), "r", encoding="utf-8") as f:
                        card = json.load(f)
                        if card.get("id"):
                            database[card["id"]] = card
            print(f"[Game] 子資料夾 [{folder}] 載入完畢。")
        print(f"[Game] 卡片資料庫載入成功，共 {len(database)} 張。")
        return database

    # ════════════════════════════════════════════════
    #  工具方法
    # ════════════════════════════════════════════════

    def _load_card_pool(self) -> dict:
        """依資料夾分類載入卡池，回傳 { "Weapon": [...], "Defense": [...], ... }"""
        pool = {"Weapon": [], "Defense": [], "Other": [], "Skill": []}
        base_dir = "Cards"
        for folder in pool.keys():
            folder_path = os.path.join(base_dir, folder)
            try:
                for file_name in os.listdir(folder_path):
                    if file_name.endswith(".json"):
                        with open(os.path.join(folder_path, file_name), "r", encoding="utf-8") as f:
                            card = json.load(f)
                            if card.get("id"):
                                pool[folder].append(card["id"])
            except Exception as e:
                print(f"[Game] 載入卡池 [{folder}] 失敗：{e}")
        return pool

    def draw_random_cards(self, count: int) -> list:
        """
        依機率從各類別抽牌：
        Weapon 31% / Defense 31% / Other 31% / Skill 7%
        """
        WEIGHTS    = {"Weapon": 31, "Defense": 31, "Other": 31, "Skill": 7}
        categories = [c for c, cards in self.card_pool.items() if cards]
        weights    = [WEIGHTS[c] for c in categories]
        drawn      = []
        for _ in range(count):
            category = random.choices(categories, weights=weights, k=1)[0]
            drawn.append(random.choice(self.card_pool[category]))
        return drawn

    def _get_player_by_name(self, name: str) -> tuple[str, player] | tuple[None, None]:
        """以名稱找玩家，回傳 (client_id, player_obj)"""
        for cid, p in self.players.items():
            if p.name == name:
                return cid, p
        return None, None

    def _get_public_players_info(self) -> list:
        return [{
            "name"    : p.name,
            "alive"   : p.alive,
            "hp"      : p.hp,
            "mp"      : p.mp,
            "element" : p.element,
            "strength": p.strength,
            "agile"   : p.agile,
            "shield"  : p.shield,
            "burning" : p.burning,
            "frozen"  : p.frozen,
        } for p in self.players.values()]

    def _broadcast_player_turns(self, action_cid: str, action_type: str) -> list:
        """
        廣播回合狀態：指定玩家收到 action_type，其他人收到 "None"。
        action_cid 為 None 時全部送 "None"（用於結算動畫期間）。
        """
        packets = []
        for cid in self.players:
            t = action_type if cid == action_cid else "None"
            packets.append({"target": cid, "data": {"action": "PlayerTurns", "type": t}})
        return packets

    def _advance_turn(self) -> list:
        """
        結束本回合，推進到下一個存活且未冰凍的玩家，
        回傳要發送的封包清單（PlayerRoundEnd 燃燒結算 + RenewGameStatus + PlayerTurns）。
        """
        packets = []

        # ── 燃燒結算（攻擊回合結束時，對當前行動玩家）────
        current_player = self.players[self.current_turn_id]
        if current_player.burning > 0:
            burn_dmg = current_player.burning
            current_player.hp = max(0, current_player.hp - burn_dmg)
            current_player.burning -= 1

            packets.append({
                "target": "broadcast",
                "data": {
                    "action" : "PlayerRoundEnd",
                    "effects": [{"target": "self", "type": "burn", "amount": burn_dmg}]
                }
            })

            # 燃燒致死判斷
            if current_player.hp <= 0:
                revived = EffectProcessor.check_revive(current_player, self.cards_database)
                if not revived:
                    packets.append({
                        "target": "broadcast",
                        "data": {
                            "action": "PlayerDead",
                            "name"  : current_player.name,
                            "place" : "attacker"
                        }
                    })
                    alive_players = [p for p in self.players.values() if p.alive]
                    if len(alive_players) <= 1:
                        winner = alive_players[0].name if alive_players else current_player.name
                        packets += self._end_game(winner)
                        return packets

        # ── 推進到下一個存活且未冰凍的玩家 ───────────
        all_ids  = list(self.players.keys())
        curr_idx = all_ids.index(self.current_turn_id)
        n        = len(all_ids)

        for offset in range(1, n + 1):
            next_id = all_ids[(curr_idx + offset) % n]
            next_p  = self.players[next_id]

            if not next_p.alive:
                continue

            if next_p.frozen > 0:
                next_p.frozen -= 1
                print(f"[Game] 玩家 {next_p.name} 被冰凍，跳過回合。")
                continue

            self.current_turn_id = next_id
            break
        else:
            self.current_turn_id = all_ids[0]

        self.turn_type = "Action"

        # 回合開始效果（冰凍消層）
        next_player    = self.players[self.current_turn_id]
        turn_start_log = EffectProcessor.process_turn_start_effects(next_player)

        # 更新所有人的遊戲狀態
        public_info = self._get_public_players_info()
        for cid, p in self.players.items():
            packets.append({
                "target": cid,
                "data": {"action": "RenewGameStatus", "players": public_info, "cards": p.hand}
            })

        # 告知各玩家輪到誰行動
        packets += self._broadcast_player_turns(self.current_turn_id, "Action")

        return packets

    def _deduct_mp(self, p: player, cards: list[dict]) -> list:
        """
        掃描出的牌，扣除含 skill 效果的 MP 消耗。
        扣完後廣播 RenewMp 封包讓前端即時更新 MP 顯示。
        回傳封包清單。
        """
        total_cost = 0
        for card in cards:
            if not card:
                continue
            skill = card.get("effects", {}).get("skill")
            if skill:
                total_cost += skill.get("mp_cost", 0)

        if total_cost == 0:
            return []

        p.mp = max(0, p.mp - total_cost)
        print(f"[Game] {p.name} 消耗 {total_cost} MP，剩餘 {p.mp} MP")

        public_info = self._get_public_players_info()
        return [{
            "target": cid,
            "data": {
                "action" : "RenewGameStatus",
                "players": public_info,
                "cards"  : self.players[cid].hand
            }
        } for cid in self.players]

    def _end_game(self, winner_name: str) -> list:
        """廣播遊戲結束封包"""
        print(f"[Game] 房間 [{self.room_number}] 遊戲結束，勝者：{winner_name}")
        return [{
            "target": "broadcast",
            "data": {
                "action": "GameWin",
                "winner": winner_name
            }
        }]

    def _replenish_hand(self, p: player, used_card_ids: list):
        """
        消耗的牌從手牌移除，並補回等量的牌。
        skill 牌例外：不移除，但仍補一張新牌。
        手牌上限為 16。
        """
        for card_id in used_card_ids:
            card_info = self.cards_database.get(card_id)
            is_skill  = card_info and "skill" in card_info.get("effects", {})
            if not is_skill and card_id in p.hand:
                p.hand.remove(card_id)
        new_cards = self.draw_random_cards(len(used_card_ids))
        space     = max(0, 16 - len(p.hand))
        p.hand.extend(new_cards[:space])

    # ════════════════════════════════════════════════
    #  遊戲開始
    # ════════════════════════════════════════════════

    def start_game_setup(self) -> list:
        try:
            for p in self.players.values():
                p.alive    = True
                p.hp       = 50
                p.mp       = 10
                p.element  = "NONE"
                p.strength = 0
                p.agile    = 0
                p.shield   = 0
                p.burning  = 0
                p.frozen   = 0
                p.hand     = self.draw_random_cards(8)

            self.current_turn_id = random.choice(list(self.players.keys()))
            self.turn_type       = "Action"
            print(f"[Game] 房間 [{self.room_number}] 先攻：{self.players[self.current_turn_id].name}")

            packets     = [{"target": "broadcast", "data": {"action": "GameStarted"}}]
            public_info = self._get_public_players_info()

            for cid, p in self.players.items():
                packets.append({
                    "target": cid,
                    "data": {"action": "RenewGameStatus", "players": public_info, "cards": p.hand}
                })

            packets += self._broadcast_player_turns(self.current_turn_id, "Action")
            return packets

        except Exception as e:
            print(f"[Game] start_game_setup 錯誤：{e}")
            return []

    # ════════════════════════════════════════════════
    #  攻擊方出牌
    # ════════════════════════════════════════════════

    def handle_play_card(self, client_id: str, data: dict) -> list:
        """
        處理攻擊方出牌事件（playCard）。
        負責：
          1. 判斷牌的類型（道具 / 單體攻擊 / 範圍攻擊）
          2. 計算攻擊力（含 strength、爆擊、元素反應倍率）
          3. 廣播 PlayerAction
          4. 請求第一個受害者回應（或直接結算道具效果後推進回合）
        """
        attacker_name   = data.get("attacker")
        target_name     = data.get("target")
        played_card_ids = data.get("cards", [])

        attacker_id, attacker_obj = self._get_player_by_name(attacker_name)
        if not attacker_obj:
            print(f"[Game] handle_play_card：找不到攻擊者 {attacker_name}")
            return []

        # 取得牌的詳細資料（過濾找不到的牌並 log 警告）
        played_cards = []
        for cid in played_card_ids:
            card = self.cards_database.get(cid)
            if card is None:
                print(f"[Game] 警告：卡片 ID [{cid}] 在資料庫中找不到，已略過")
            else:
                played_cards.append(card)

        # 若有傳卡片 ID 但全部找不到，直接 log 並返回，不推進回合
        if played_card_ids and not played_cards:
            print(f"[Game] 警告：{attacker_name} 傳入的卡片全部無效，忽略此次出牌")
            return []

        # ── 判斷牌的類型 ──────────────────────────────
        has_aoe     = any(EffectProcessor.is_aoe_card(c)     for c in played_cards if c)
        has_attack  = any(not EffectProcessor.is_utility_card(c) and not EffectProcessor.is_aoe_card(c)
                         for c in played_cards if c)
        is_utility  = not has_aoe and not has_attack

        # 取得攻擊元素（以第一張有元素的攻擊牌為準）
        attack_element = "NONE"
        for c in played_cards:
            if c and c.get("element", "NONE") != "NONE":
                attack_element = c["element"]
                break

        packets = []

        # ════════════════════════════
        #  A. 道具牌（非攻擊行為）
        # ════════════════════════════
        if is_utility:
            print(f"[Game] {attacker_name} 使出道具牌：{played_card_ids}")

            # 扣 MP（含 skill 效果的牌）
            packets += self._deduct_mp(attacker_obj, played_cards)

            # 結算道具效果
            # 道具牌情境下，attacker 同時作為 victim（to_apply="victim" 的效果也套到自己）
            effect_log = EffectProcessor.apply_utility_effects(
                played_cards,
                caster          = attacker_obj,
                attacker        = attacker_obj,
                victim          = attacker_obj,
                cards_database  = self.cards_database
            )

            # 補牌（若沒有出任何牌，仍補一張）
            if played_card_ids:
                self._replenish_hand(attacker_obj, played_card_ids)
            else:
                if len(attacker_obj.hand) < 16:
                    attacker_obj.hand.extend(self.draw_random_cards(1))

            packets.append({
                "target": "broadcast",
                "data": {
                    "action": "PlayerAction",
                    "attacker": attacker_obj.name,
                    "target": attacker_obj.name,
                    "card": played_card_ids,
                    "damage_details": {
                        "final_damage"  : 0,
                        "is_true_damage": False,
                        "addition"      : [],
                        "element"       : "NONE"
                    }
                }
            })

            packets.append({
                "target": "broadcast",
                "data": {
                    "action" : "PlayerRoundEnd",
                    "effects": effect_log
                }
            })
            packets += self._advance_turn()
            return packets

        # ════════════════════════════
        #  B. 範圍攻擊
        # ════════════════════════════
        if has_aoe:
            aoe_cards = [c for c in played_cards if c and EffectProcessor.is_aoe_card(c)]
            aoe_rate  = aoe_cards[0]["effects"]["attack_all_player"].get("rate", 1.0) if aoe_cards else 1.0

            # 扣 MP
            packets += self._deduct_mp(attacker_obj, played_cards)

            # 先計算基礎 aoe 攻擊力（不含元素反應，因每個目標的反應不同）
            raw_aoe_damage = sum(
                c["effects"]["attack_all_player"].get("attack", 0)
                for c in aoe_cards
            ) + attacker_obj.strength

            # 儲存戰鬥狀態
            self.active_combat.update({
                "attacker_id"   : client_id,
                "attack_value"  : raw_aoe_damage,
                "attack_cards"  : played_card_ids,
                "attack_element": attack_element,
                "is_true_damage": EffectProcessor.is_true_damage(attack_element),
                "is_aoe"        : True,
            })

            # 決定命中的受害者名單（依 aoe_rate 擲骰）
            self.defense_queue = [
                cid for cid, p in self.players.items()
                if cid != client_id and p.alive and random.random() < aoe_rate
            ]

            if not self.defense_queue:
                # 全員閃避：直接推進回合
                print(f"[Game] {attacker_name} 範圍攻擊全員閃避")
                self._replenish_hand(attacker_obj, played_card_ids)
                packets.append({"target": "broadcast",
                                 "data": {"action": "PlayerRoundEnd", "effects": []}})
                packets += self._advance_turn()
                return packets

            # 取第一個受害者
            first_victim_id  = self.defense_queue.pop(0)
            first_victim_obj = self.players[first_victim_id]
            self.active_combat["target_id"] = first_victim_id

            # 計算針對第一個目標的攻擊力（含元素反應）
            reaction_key = EffectProcessor.get_reaction_key(attack_element, first_victim_obj)
            # AOE 牌的攻擊力以 attack_all_player.attack + strength 為主
            final_attack = raw_aoe_damage
            additions = []
            if reaction_key in ("pyro_hydro", "pyro_cryo"):
                final_attack = int(final_attack * 1.5)
                additions.append("元素反應 x1.5")
            elif reaction_key == "pyro_electro":
                final_attack *= 2
                additions.append("元素反應 x2")

            is_true = EffectProcessor.is_true_damage(attack_element)

            packets.append({
                "target": "broadcast",
                "data": {
                    "action": "PlayerAction",
                    "attacker": attacker_name,
                    "target": first_victim_obj.name,
                    "card": played_card_ids,
                    "damage_details": {
                        "final_damage"  : final_attack,
                        "is_true_damage": is_true,
                        "addition"      : additions,
                        "element"       : attack_element
                    }
                }
            })
            self.active_combat["attack_value"] = final_attack
            self.turn_type = "Respond"
            packets += self._broadcast_player_turns(first_victim_id, "Respond")
            return packets

        # ════════════════════════════
        #  C. 單體攻擊
        # ════════════════════════════
        target_id, target_obj = self._get_player_by_name(target_name)
        if not target_id:
            print(f"[Game] handle_play_card：找不到目標 {target_name}")
            return []

        # 扣 MP
        packets += self._deduct_mp(attacker_obj, played_cards)

        # 元素反應判斷（若護盾還在，不掛元素，此處先用護盾判斷略過）
        reaction_key = EffectProcessor.get_reaction_key(attack_element, target_obj)
        final_attack, additions, overridden_element = EffectProcessor.calc_attack(
            played_cards, attacker_obj, reaction_key, victim=target_obj
        )
        if overridden_element:
            attack_element = overridden_element
        is_true = EffectProcessor.is_true_damage(attack_element)

        # 儲存戰鬥狀態
        self.active_combat.update({
            "attacker_id"   : client_id,
            "target_id"     : target_id,
            "attack_value"  : final_attack,
            "attack_cards"  : played_card_ids,
            "attack_element": attack_element,
            "is_true_damage": is_true,
            "is_aoe"        : False,
        })
        self.defense_queue = []
        self.turn_type = "Respond"

        packets.append({
            "target": "broadcast",
            "data": {
                "action": "PlayerAction",
                "attacker": attacker_name,
                "target": target_name,
                "card": played_card_ids,
                "damage_details": {
                    "final_damage"  : final_attack,
                    "is_true_damage": is_true,
                    "addition"      : additions,
                    "element"       : attack_element
                }
            }
        })
        packets += self._broadcast_player_turns(target_id, "Respond")
        return packets

    # ════════════════════════════════════════════════
    #  防禦方回應
    # ════════════════════════════════════════════════

    def handle_play_card_respond(self, client_id: str, data: dict) -> list:
        """
        處理防禦方回應事件（playCardRespond）。
        負責：
          1. 計算防禦力（含 agile）
          2. 廣播 PlayerResponse
          3. 結算傷害（HP / Shield / 元素反應）
          4. 廣播 PlayerRoundEnd
          5. 若 defense_queue 還有人 → 請下一個人回應
             否則 → 補牌並推進回合
        """
        defender_obj      = self.players[client_id]
        respond_card_ids  = data.get("cards", [])
        respond_cards     = [self.cards_database.get(cid) for cid in respond_card_ids]

        attacker_id  = self.active_combat["attacker_id"]
        attacker_obj = self.players[attacker_id]

        # ── 計算防禦力 ─────────────────────────────
        final_defense, def_additions = EffectProcessor.calc_defense(respond_cards, defender_obj)

        packets = []

        # 扣 MP（防禦牌也可能有 skill 效果）
        packets += self._deduct_mp(defender_obj, respond_cards)

        # 結算防禦牌上的道具效果（例如防禦牌掛元素到 this）
        defend_effect_log = EffectProcessor.apply_utility_effects(
            respond_cards,
            caster          = defender_obj,
            attacker        = attacker_obj,
            victim          = defender_obj,
            cards_database  = self.cards_database
        )

        # ── 廣播防禦結果 ───────────────────────────
        packets.append({
            "target": "broadcast",
            "data": {
                "action": "PlayerResponse",
                "attacker": attacker_obj.name,
                "target": defender_obj.name,
                "card": respond_card_ids,
                "damage_details": {
                    "final_defense": final_defense,
                    "addition"     : def_additions
                }
            }
        })

        # ── 元素反應（攻擊元素 vs 護盾後的元素狀態）────
        attack_element = self.active_combat["attack_element"]
        is_true        = self.active_combat["is_true_damage"]

        # 計算實際穿透傷害：真實傷害略過防禦，一般傷害扣完防禦和護盾後若 > 0 才掛元素
        raw_attack = self.active_combat["attack_value"]
        if is_true:
            net_damage = max(0, raw_attack - defender_obj.shield)
        else:
            net_damage = max(0, raw_attack - final_defense - defender_obj.shield)

        if raw_attack > 0:
            reaction_key = EffectProcessor.get_reaction_key(attack_element, defender_obj)
        else:
            reaction_key = None

        # 深淵：先算一般傷害，再獨立結算斬殺
        is_abyss = EffectProcessor.is_instant_kill(attack_element)
        if is_abyss:
            # 先套正常傷害（不含斬殺）
            dmg_shield, dmg_hp = EffectProcessor.apply_damage(
                defender_obj, raw_attack, final_defense, is_true_damage=False
            )
        else:
            dmg_shield, dmg_hp = EffectProcessor.apply_damage(
                defender_obj, raw_attack, final_defense, is_true_damage=is_true
            )

        # 復活判斷（一般傷害後先檢查）
        was_dead = defender_obj.hp <= 0
        revived  = EffectProcessor.check_revive(defender_obj, self.cards_database)

        # 後效元素反應
        reaction_log = EffectProcessor.apply_post_reaction(
            reaction_key, attack_element, attacker_obj, defender_obj
        )

        # 攻擊牌上的額外效果
        attack_cards_info = [self.cards_database.get(cid) for cid in self.active_combat["attack_cards"]]
        attack_effect_log = EffectProcessor.apply_utility_effects(
            attack_cards_info,
            caster         = attacker_obj,
            attacker       = attacker_obj,
            victim         = defender_obj,
            cards_database = self.cards_database,
            hit_victim     = raw_attack > 0
        )

        # ── 組合 round_effects ────────────────────────
        round_effects = []
        if dmg_shield > 0:
            round_effects.append({"target": "victim", "type": "shield", "amount": -dmg_shield})
        if dmg_hp > 0:
            round_effects.append({"target": "victim", "type": "damage", "amount": dmg_hp})
        if was_dead and revived and defender_obj.alive:
            revive_heal = min(99, 10 + defender_obj.agile)
            defender_obj.hp = min(99, revive_heal)
            round_effects.append({"target": "victim", "type": "heal", "amount": revive_heal})
        round_effects += reaction_log
        round_effects += attack_effect_log
        round_effects += defend_effect_log

        # ── 深淵：斬殺效果合併進 round_effects ────────
        if is_abyss and raw_attack > final_defense and defender_obj.alive:
            abyss_damage       = defender_obj.hp
            defender_obj.hp    = 0
            defender_obj.alive = False
            revived_abyss      = EffectProcessor.check_revive(defender_obj, self.cards_database)
            if revived_abyss:
                revive_heal = min(99, 10 + defender_obj.agile)
                defender_obj.hp = min(99, revive_heal)
                round_effects.append({"target": "victim", "type": "heal",  "amount": revive_heal})
            else:
                round_effects.append({"target": "victim", "type": "abyss", "amount": abyss_damage})

        # ── 單一 PlayerRoundEnd ───────────────────────
        packets.append({
            "target": "broadcast",
            "data": {"action": "PlayerRoundEnd", "effects": round_effects}
        })

        # ── 玩家死亡通知 ──────────────────────────────
        if not defender_obj.alive:
            packets.append({
                "target": "broadcast",
                "data": {
                    "action": "PlayerDead",
                    "name"  : defender_obj.name,
                    "place" : attacker_obj.name
                }
            })

        # ── 補回防禦牌 ────────────────────────────
        self._replenish_hand(defender_obj, respond_card_ids)

        # ── 判斷是否還有下一個受害者（AOE）─────────
        if self.defense_queue:
            next_victim_id  = self.defense_queue.pop(0)
            next_victim_obj = self.players[next_victim_id]
            self.active_combat["target_id"] = next_victim_id

            # 重新計算針對下一個目標的攻擊力（元素反應可能不同）
            attack_cards  = [self.cards_database.get(cid) for cid in self.active_combat["attack_cards"]]
            next_reaction = EffectProcessor.get_reaction_key(attack_element, next_victim_obj)

            base_aoe = sum(
                c["effects"]["attack_all_player"].get("attack", 0)
                for c in attack_cards if c and EffectProcessor.is_aoe_card(c)
            ) + attacker_obj.strength

            next_attack = base_aoe
            next_additions = []
            if next_reaction in ("pyro_hydro", "pyro_cryo"):
                next_attack = int(next_attack * 1.5)
                next_additions.append("元素反應 x1.5")
            elif next_reaction == "pyro_electro":
                next_attack *= 2
                next_additions.append("元素反應 x2")

            self.active_combat["attack_value"] = next_attack

            packets.append({
                "target": "broadcast",
                "data": {
                    "action": "PlayerAction",
                    "attacker": attacker_obj.name,
                    "target": next_victim_obj.name,
                    "card": self.active_combat["attack_cards"],
                    "damage_details": {
                        "final_damage"  : next_attack,
                        "is_true_damage": is_true,
                        "addition"      : next_additions,
                        "element"       : attack_element
                    }
                }
            })
            packets += self._broadcast_player_turns(next_victim_id, "Respond")

        else:
            # 所有受害者都回應完畢，補回攻擊牌並推進回合
            self._replenish_hand(attacker_obj, self.active_combat["attack_cards"])

            # 清空戰鬥狀態
            self.active_combat = {
                "attacker_id"   : None,
                "target_id"     : None,
                "attack_value"  : 0,
                "attack_cards"  : [],
                "attack_element": "NONE",
                "is_true_damage": False,
                "is_aoe"        : False,
            }

            # 檢查是否遊戲結束
            alive_players = [p for p in self.players.values() if p.alive]
            if len(alive_players) == 1:
                packets += self._end_game(alive_players[0].name)
            elif len(alive_players) == 0:
                # 極端情況：同歸於盡，以攻擊者為勝者
                packets += self._end_game(attacker_obj.name)
            else:
                packets += self._advance_turn()

        return packets