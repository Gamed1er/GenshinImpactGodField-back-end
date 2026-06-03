from moudle import player
import random

# ────────────────────────────────────────────────
#  元素反應表
#  key   : (攻擊元素, 受害者身上已有的元素)
#  value : 反應描述
# ────────────────────────────────────────────────
ELEMENT_REACTIONS = {
    ("PYRO",    "HYDRO")   : "pyro_hydro",    # 傷害 x1.5
    ("HYDRO",   "PYRO")    : "pyro_hydro",
    ("PYRO",    "CRYO")    : "pyro_cryo",     # 傷害 x1.5
    ("CRYO",    "PYRO")    : "pyro_cryo",
    ("PYRO",    "ELECTRO") : "pyro_electro",  # 傷害 x2
    ("ELECTRO", "PYRO")    : "pyro_electro",
    ("PYRO",    "DENDRO")  : "burning",       # 被攻擊者 +1 燃燒
    ("DENDRO",  "PYRO")    : "burning",
    ("HYDRO",   "CRYO")    : "frozen",        # 被攻擊者冰凍
    ("CRYO",    "HYDRO")   : "frozen",
    ("HYDRO",   "ELECTRO") : "hydro_electro", # 被攻擊者 -1 力量
    ("ELECTRO", "HYDRO")   : "hydro_electro",
    ("HYDRO",   "DENDRO")  : "hydro_dendro",  # 被攻擊者 -1 敏捷
    ("DENDRO",  "HYDRO")   : "hydro_dendro",
    ("CRYO",    "ELECTRO") : "cryo_electro",  # 攻擊者 +1 力量
    ("ELECTRO", "CRYO")    : "cryo_electro",
    ("CRYO",    "DENDRO")  : "cryo_dendro",   # 攻擊者 +1 敏捷
    ("DENDRO",  "CRYO")    : "cryo_dendro",
    ("ELECTRO", "DENDRO")  : "burning",       # 被攻擊者 +1 燃燒
    ("DENDRO",  "ELECTRO") : "burning",
}

# 會影響攻擊力倍率的反應（在計算傷害時就要套用）
DAMAGE_MODIFIER_REACTIONS = {"pyro_hydro", "pyro_cryo", "pyro_electro"}


class EffectProcessor:

    # ════════════════════════════════════════════════
    #  1. 卡片類型判斷
    # ════════════════════════════════════════════════

    @staticmethod
    def is_utility_card(card_info: dict) -> bool:
        """道具牌：攻擊力為 0 且沒有 attack_all_player"""
        if not card_info:
            return True
        effects = card_info.get("effects", {})
        attack  = card_info.get("attribute", {}).get("attack", 0)
        return attack == 0 and "attack_all_player" not in effects

    @staticmethod
    def is_aoe_card(card_info: dict) -> bool:
        """範圍攻擊牌"""
        if not card_info:
            return False
        return "attack_all_player" in card_info.get("effects", {})

    # ════════════════════════════════════════════════
    #  2. 攻擊力計算
    #     victim 可為 None（不計算元素 / 冰凍加傷）
    # ════════════════════════════════════════════════

    @staticmethod
    def calc_attack(
        cards: list[dict],
        attacker: player,
        reaction_key: str | None = None,
        victim: player | None = None
    ) -> tuple[int, list[str], str]:
        """
        計算這次出牌的總攻擊力。
        回傳 (final_attack, additions, final_element)
        final_element 可能被 change_attack_attribute 改變。
        """
        additions     = []
        base_damage   = 0
        final_element = None  # 由外部傳入，這裡只負責偵測是否被覆蓋

        for card in cards:
            if not card:
                continue
            effects   = card.get("effects", {})
            attribute = card.get("attribute", {})

            # 基礎攻擊值
            base_damage += attribute.get("attack", 0)

            # change_attack_attribute：修改攻擊值，也可轉換攻擊元素
            if "change_attack_attribute" in effects:
                cfg   = effects["change_attack_attribute"]
                delta = cfg.get("attack", 0)
                base_damage += delta
                if "element" in cfg:
                    final_element = cfg["element"]  # 覆蓋攻擊元素

            # 爆擊
            if "critic" in effects:
                rate = effects["critic"].get("rate", 0)
                if random.random() < rate:
                    base_damage *= 2
                    additions.append("爆擊")

            # add_damage_when_shield：攻擊者有護盾時加傷
            if "add_damage_when_shield" in effects:
                if attacker.shield > 0:
                    bonus = effects["add_damage_when_shield"].get("amount", 0)
                    base_damage += bonus
                    additions.append(f"護盾加傷 +{bonus}")

            # add_damage_when_exist_element
            if "add_damage_when_exist_element" in effects and victim is not None:
                cfg               = effects["add_damage_when_exist_element"]
                required_elements = cfg.get("element", [])
                bonus             = cfg.get("amount", 0)
                victim_elem       = victim.element if victim.element else "NONE"
                if victim_elem in required_elements:
                    base_damage += bonus
                    additions.append(f"元素加傷 +{bonus}")

            # add_damage_when_frozen
            if "add_damage_when_frozen" in effects and victim is not None:
                if victim.frozen > 0:
                    bonus = effects["add_damage_when_frozen"].get("amount", 0)
                    base_damage += bonus
                    additions.append(f"冰凍加傷 +{bonus}")

        # strength 加在最終傷害上
        if attacker.strength != 0:
            base_damage += attacker.strength
            additions.append(f"力量 {attacker.strength:+d}")

        # 元素反應傷害倍率
        if reaction_key in DAMAGE_MODIFIER_REACTIONS:
            if reaction_key in ("pyro_hydro", "pyro_cryo"):
                base_damage = int(base_damage * 1.5)
                additions.append("元素反應 x1.5")
            elif reaction_key == "pyro_electro":
                base_damage *= 2
                additions.append("元素反應 x2")

        return max(0, base_damage), additions, final_element

    # ════════════════════════════════════════════════
    #  3. 防禦力計算
    # ════════════════════════════════════════════════

    @staticmethod
    def calc_defense(cards: list[dict], defender: player) -> tuple[int, list[str]]:
        """回傳 (final_defense, additions)"""
        additions    = []
        base_defense = 0

        for card in cards:
            if not card:
                continue
            base_defense += card.get("attribute", {}).get("defense", 0)

        # 敏捷加總防禦，只作用一次（需有防禦牌才生效）
        if defender.agile != 0 and base_defense > 0:
            base_defense += defender.agile
            additions.append(f"敏捷 {defender.agile:+d}")

        return max(0, base_defense), additions

    # ════════════════════════════════════════════════
    #  4. 元素反應
    # ════════════════════════════════════════════════

    @staticmethod
    def get_reaction_key(attack_element: str, victim: player) -> str | None:
        victim_element = victim.element if victim.element else "NONE"

        # GEO：攻擊或身上有 GEO 時，只要另一方不是 NONE 就觸發反應
        if attack_element == "GEO" and victim_element != "NONE":
            return "geo"
        if victim_element == "GEO" and attack_element not in ("NONE", "ANEMO", "GEO", "ABYSS"):
            return "geo"

        if attack_element == "NONE" or victim_element == "NONE":
            return None
        return ELEMENT_REACTIONS.get((attack_element, victim_element))

    @staticmethod
    def apply_post_reaction(
        reaction_key: str | None,
        attack_element: str,
        attacker: player,
        victim: player
    ) -> list[dict]:
        """
        結算不影響攻擊力的元素反應後效，並更新雙方元素狀態。
        回傳 effect_log。
        """
        effect_log = []

        # GEO 反應：給攻擊者 5 點護盾，清除受害者元素，不掛新元素
        if reaction_key == "geo":
            victim.element = "NONE"
            attacker.shield = min(99, attacker.shield + 5)
            effect_log.append({"target": "attacker", "type": "shield", "amount": 5})
            return effect_log

        if reaction_key is None:
            # 無反應：直接掛元素
            if attack_element not in ("NONE", "ANEMO", "GEO", "ABYSS"):
                victim.element = attack_element
            return effect_log

        # 有反應：清除被攻擊者的元素
        victim.element = "NONE"

        if reaction_key == "burning":
            victim.burning += 4
            effect_log.append({"target": "victim", "type": "burn", "amount": 4})

        elif reaction_key == "frozen":
            victim.frozen = 1
            effect_log.append({"target": "victim", "type": "frozen", "amount": 1})

        elif reaction_key == "hydro_electro":
            victim.strength -= 4
            effect_log.append({"target": "victim", "type": "strength", "amount": -4})

        elif reaction_key == "hydro_dendro":
            victim.agile -= 4
            effect_log.append({"target": "victim", "type": "agile", "amount": -4})

        elif reaction_key == "cryo_electro":
            attacker.strength += 4
            effect_log.append({"target": "attacker", "type": "strength", "amount": 4})

        elif reaction_key == "cryo_dendro":
            attacker.agile += 4
            effect_log.append({"target": "attacker", "type": "agile", "amount": 4})

        return effect_log

    # ════════════════════════════════════════════════
    #  5. 傷害套用（HP / Shield）
    # ════════════════════════════════════════════════

    @staticmethod
    def apply_damage(
        victim: player,
        raw_attack: int,
        raw_defense: int,
        is_true_damage: bool = False
    ) -> tuple[int, int]:
        """
        套用傷害，回傳 (damage_to_shield, damage_to_hp)。
        真實傷害略過防禦，但仍可被護盾擋。
        不在此處判斷死亡，死亡由 check_revive 統一處理。
        """
        net = raw_attack if is_true_damage else max(0, raw_attack - raw_defense)

        dmg_shield = 0
        if victim.shield > 0:
            absorbed      = min(victim.shield, net)
            victim.shield -= absorbed
            dmg_shield    = absorbed
            net           -= absorbed

        victim.hp  = max(0, victim.hp - net)
        dmg_hp     = net

        return dmg_shield, dmg_hp

    @staticmethod
    def check_revive(victim: player, cards_database: dict) -> bool:
        """
        在 apply_damage 後呼叫。
        若 HP <= 0，掃描手牌是否有含 revive 效果的牌。
        有的話：復活到 HP=10，移除該牌，回傳 True。
        沒有的話：標記 alive=False，回傳 False。
        """
        if victim.hp > 0:
            return True  # 還活著，不需要處理

        # 找手牌中第一張有 revive 效果的牌
        for card_id in list(victim.hand):
            card_info = cards_database.get(card_id)
            if not card_info:
                continue
            effects = card_info.get("effects", {})
            if "revive" not in effects:
                continue

            # 確認 to_apply 是否適用（victim 或 this 都代表自己）
            to_apply = effects["revive"].get("to_apply", "victim")
            if to_apply in ("victim", "this"):
                victim.hand.remove(card_id)
                victim.hp    = 10
                victim.alive = True
                print(f"[EffectProcessor] {victim.name} 觸發復活！HP 回復至 10。")
                return True

        # 沒有復活牌，正式死亡
        victim.alive = False
        return False

    # ════════════════════════════════════════════════
    #  6. 道具牌 / 防禦牌效果套用
    # ════════════════════════════════════════════════

    @staticmethod
    def apply_utility_effects(
        cards: list[dict],
        caster: player,
        attacker: player | None,
        victim: player | None,
        cards_database: dict | None = None,
        hit_victim: bool = True          # 攻擊有穿透護盾時才能對 victim 生效
    ) -> list[dict]:
        """
        結算道具牌 / 防禦牌上的效果。
        回傳 effect_log。
        """
        effect_log = []

        def _resolve_target(to_apply: str) -> player | None:
            if to_apply == "this":     return caster
            if to_apply == "attacker": return attacker
            if to_apply == "victim":   return victim
            return None

        # 將卡片的 effect 欄位名稱對應到前端的 type 名稱
        EFFECT_TO_TYPE = {
            "hp"      : "heal",
            "mp"      : "mp_heal",
            "shield"  : "shield",
            "strength": "strength",
            "agile"   : "agile",
            "frozen"  : "frozen",
            "burning" : "burn",
        }

        def _apply_one_effect(cfg: dict):
            """處理單一 apply_effects 格式的 dict，並記錄到 effect_log"""
            target = _resolve_target(cfg.get("to_apply", "this"))
            effect = cfg.get("effect", "")
            amount = cfg.get("amount", 0)
            if target and effect:
                EffectProcessor._apply_stat(target, effect, amount)
                # hp 扣血用 damage，hp 回血用 heal
                if effect == "hp":
                    frontend_type = "damage" if amount < 0 else "heal"
                else:
                    frontend_type = EFFECT_TO_TYPE.get(effect, effect)
                effect_log.append({
                    "target": cfg.get("to_apply", "this"),
                    "type"  : frontend_type,
                    "amount": abs(amount)
                })

        def _apply_dealt_extra_damage(cfg: dict):
            """dealt_extra_damage：直接扣對象 HP（真實傷害，不經護盾）"""
            target = _resolve_target(cfg.get("to_apply", "victim"))
            amount = cfg.get("amount", 0)
            if target and amount > 0:
                target.hp = max(0, target.hp - amount)
                effect_log.append({
                    "target": cfg.get("to_apply", "victim"),
                    "type":   "damage",
                    "amount": amount
                })

        for card in cards:
            if not card:
                continue
            effects = card.get("effects", {})

            # ── apply_element ──────────────────────
            if "apply_element" in effects:
                cfg    = effects["apply_element"]
                to_app = cfg.get("to_apply", "this")
                target = _resolve_target(to_app)
                elem   = cfg.get("element", "NONE")
                # 套用到 victim 時需要有穿透
                if target and elem != "NONE" and not (to_app == "victim" and not hit_victim):
                    target.element = elem

            # ── apply_effects / apply_effects2 ─────
            for key in ("apply_effects", "apply_effects2"):
                if key in effects:
                    cfg    = effects[key]
                    to_app = cfg.get("to_apply", "this")
                    # 若有 element 欄位，當作 apply_element 處理
                    if "element" in cfg:
                        target = _resolve_target(to_app)
                        elem   = cfg["element"]
                        if target and elem != "NONE" and not (to_app == "victim" and not hit_victim):
                            target.element = elem
                        continue
                    # 套用到 victim 時需要有穿透
                    if to_app == "victim" and not hit_victim:
                        continue
                    _apply_one_effect(cfg)

            # ── randomly_trigger_effect ────────────
            if "randomly_trigger_effect" in effects:
                polls = effects["randomly_trigger_effect"].get("polls", [])
                if polls:
                    chosen = random.choice(polls)  # 從 polls 中隨機選一個
                    # chosen 是 { "effect_type": { ...cfg } } 格式
                    for effect_type, cfg in chosen.items():
                        if effect_type == "apply_effects":
                            _apply_one_effect(cfg)
                        elif effect_type == "dealt_extra_damage":
                            _apply_dealt_extra_damage(cfg)
                        elif effect_type == "apply_element":
                            target = _resolve_target(cfg.get("to_apply", "this"))
                            elem   = cfg.get("element", "NONE")
                            if target and elem != "NONE":
                                target.element = elem

            # ── wipe_effect：清除元素與狀態，不需要發送 effect_log ──
            if "wipe_effect" in effects:
                to_apply = effects["wipe_effect"].get("to_apply", "this")
                target   = _resolve_target(to_apply)
                if target:
                    target.element = "NONE"
                    if target.burning > 0:
                        effect_log.append({"target": to_apply, "type": "burn",   "amount": -target.burning})
                        target.burning = 0
                    if target.frozen > 0:
                        effect_log.append({"target": to_apply, "type": "frozen", "amount": -target.frozen})
                        target.frozen  = 0

            # ── skill：MP 由 Game._deduct_mp 統一處理 ─
            # （不在此處扣，避免重複）

        return effect_log

    # ════════════════════════════════════════════════
    #  7. 屬性套用輔助（含上下限）
    # ════════════════════════════════════════════════

    @staticmethod
    def _apply_stat(target: player, stat: str, amount: int):
        stat_map = {
            "hp": "hp", "mp": "mp", "shield": "shield",
            "strength": "strength", "agile": "agile",
            "frozen": "frozen", "burning": "burning",
        }
        attr = stat_map.get(stat)
        if attr is None:
            return
        # 回血時加上 agile 加乘
        if attr == "hp" and amount > 0:
            amount += target.agile
        new_val = getattr(target, attr, 0) + amount
        if attr in ("shield", "burning", "frozen", "hp", "mp"):
            new_val = max(0, new_val)
        # HP / MP / 護盾上限為 99，其他屬性（strength、agile 等）無上限限制
        cap = 99 if attr in ("hp", "mp", "shield") else 999
        setattr(target, attr, min(new_val, cap))

    # ════════════════════════════════════════════════
    #  8. 回合開始效果（燃燒扣血 / 冰凍消層）
    # ════════════════════════════════════════════════

    @staticmethod
    def process_turn_start_effects(target: player) -> list[dict]:
        """
        在某玩家的回合開始時呼叫。
        回傳 effect_log。
        注意：燃燒改為回合結束時結算（由 Game._advance_turn 處理）。
              冰凍跳回合的邏輯由 Game._advance_turn 處理，這裡只負責消耗層數。
        """
        effect_log = []

        if target.frozen > 0:
            target.frozen -= 1
            effect_log.append({"target": "self", "type": "frozen", "amount": -1})

        return effect_log

    # ════════════════════════════════════════════════
    #  9. 特殊元素判斷
    # ════════════════════════════════════════════════

    @staticmethod
    def is_true_damage(attack_element: str) -> bool:
        """ANEMO：真實傷害（略過防禦，但可被護盾擋）"""
        return attack_element == "ANEMO"

    @staticmethod
    def is_instant_kill(attack_element: str) -> bool:
        """ABYSS：斬殺（HP 歸 0）"""
        return attack_element == "ABYSS"