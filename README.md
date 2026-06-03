# 原神 + 神界

# 後端技術文件

## 檔案架構

```
/FinalProject (back-end)
│
├── Cards/
│   ├── Weapon/          # 攻擊牌 JSON（抽牌機率 31%）
│   ├── Defense/         # 防禦牌 JSON（抽牌機率 31%）
│   ├── Other/           # 道具牌 JSON（抽牌機率 31%）
│   └── Skill/           # 技能牌 JSON（抽牌機率 7%）
│
├── App.py               # 主程式，事件分派中心
├── communicate.py       # TCP 連線管理，封包收發
├── room_controller.py   # 房間建立 / 加入 / 離開 / 斷線處理
├── game.py              # 遊戲流程控制，每個房間一個 Game 實例
├── effect_processor.py  # 純計算層，處理卡片效果與元素反應
└── moudle.py            # player、room 資料結構定義
```

---

## 模組職責

| 模組 | 職責 | 不做什麼 |
|------|------|----------|
| `communicate.py` | TCP 連線、封包序列化 / 反序列化、分配 client_id | 不處理遊戲邏輯 |
| `App.py` | 從 queue 取封包，依 action 分派 | 不做計算，只做路由 |
| `room_controller.py` | 管理房間生命週期 | 不知道遊戲規則 |
| `game.py` | 回合流程、封包組裝、狀態推進 | 不直接操作 socket |
| `effect_processor.py` | 傷害計算、元素反應、效果套用 | 不發送封包 |
| `moudle.py` | 純資料結構 | 不含任何邏輯 |

---

## 伺服器啟動流程

```
App.main()
  └─ Communicator.start_server()
       ├─ 綁定 0.0.0.0:65432
       ├─ 印出本機 IP
       └─ 啟動 _accept_loop 執行緒（daemon）

_accept_loop（背景執行緒）
  └─ 每個新連線
       ├─ 指派 client_id（player_1, player_2, ...）
       └─ 啟動 _listen_client_loop 執行緒（daemon）

_listen_client_loop（每個客戶端一條執行緒）
  └─ 持續讀取，以 \n 分割 JSON
       ├─ 解析成封包 → 放入 msg queue
       └─ 斷線時自動 enqueue disconnect 事件

App 主迴圈（主執行緒）
  └─ 從 msg queue 取封包 → 依 action 分派處理
```

---

## 房間生命週期

```
CreateRoom ──→ LOBBY
                 │
             JoinRoom（可多人加入）
                 │
             StartGame ──→ PLAYING
                              │
                         遊戲結束（GameWin）
                              │
                         房間銷毀
```

**房間自動銷毀條件：**
- 大廳中最後一人離開
- 遊戲進行中有人斷線
- 遊戲結束（GameWin 廣播後）

---

## 遊戲回合流程

### 攻擊回合（出攻擊牌）

```
玩家發送 playCard
    │
    ├─ 道具牌（attack=0，無 attack_all_player）
    │       ├─ 扣 MP（若有 skill 效果）
    │       ├─ 結算卡片效果
    │       ├─ 廣播 PlayerAction（damage=0）
    │       ├─ 廣播 PlayerRoundEnd
    │       ├─ 燃燒結算
    │       └─ 推進回合
    │
    ├─ 單體攻擊（attack>0）
    │       ├─ 扣 MP
    │       ├─ 計算攻擊力（含 strength、爆擊、元素反應倍率）
    │       ├─ 廣播 PlayerAction
    │       └─ 請目標回應（PlayerTurns: Respond）
    │
    └─ 範圍攻擊（含 attack_all_player）
            ├─ 扣 MP
            ├─ 對所有存活敵人擲骰（依 rate）
            ├─ 建立 defense_queue
            └─ 對第一個目標廣播 PlayerAction，請求回應
```

### 防禦回合（出防禦牌）

```
玩家發送 playCardRespond
    │
    ├─ 計算防禦力（base_defense + agile，需有防禦牌）
    ├─ 廣播 PlayerResponse
    ├─ 判斷是否穿透（net_damage）
    ├─ 套用傷害（護盾 → HP）
    ├─ 復活判斷（check_revive）
    ├─ 元素反應（get_reaction_key → apply_post_reaction）
    ├─ 結算攻擊牌效果（hit_victim = raw_attack > 0）
    ├─ 結算防禦牌效果
    │
    ├─ 若 is_abyss 且 raw_attack > final_defense
    │       └─ 斬殺（HP → 0）
    │
    ├─ 廣播 PlayerRoundEnd（單一封包，所有效果合併）
    │
    ├─ 若 defense_queue 非空（AOE）
    │       └─ 對下一個目標廣播 PlayerAction
    │
    └─ 若 defense_queue 為空
            ├─ 補牌
            ├─ 死亡判斷 → 廣播 PlayerDead
            ├─ 勝利判斷 → 廣播 GameWin → 銷毀房間
            ├─ 燃燒結算（當前玩家）
            └─ 推進回合（跳過冰凍玩家）
```

---

## 元素反應表

| 攻擊元素 | 身上元素 | 反應 | 效果 |
|----------|----------|------|------|
| 火 | 水 | pyro_hydro | 傷害 ×1.5 |
| 火 | 冰 | pyro_cryo | 傷害 ×1.5 |
| 火 | 雷 | pyro_electro | 傷害 ×2 |
| 火 / 雷 | 草 | burning | 被攻擊者 +4 層燃燒 |
| 水 | 冰 | frozen | 被攻擊者冰凍（跳過下一回合） |
| 水 | 雷 | hydro_electro | 被攻擊者 −4 力量 |
| 水 | 草 | hydro_dendro | 被攻擊者 −4 敏捷 |
| 冰 | 雷 | cryo_electro | 攻擊者 +4 力量 |
| 冰 | 草 | cryo_dendro | 攻擊者 +4 敏捷 |
| 岩 | 任意 | geo | 攻擊者 +5 護盾 |
| 深淵 | — | — | 斬殺（若穿透防禦牌） |
| 風 | — | — | 真實傷害（略過防禦，護盾仍有效） |

**觸發條件：** 只要 `raw_attack > 0` 即觸發（打到護盾也算）。

**元素掛載限制：**
- 風、岩、深淵無法掛在玩家身上
- 玩家最多同時擁有一種元素
- 元素反應觸發後清除身上元素

---

## 玩家屬性說明

| 屬性 | 上限 | 說明 |
|------|------|------|
| HP | 99 | 降至 0 視為死亡 |
| MP | 99 | 使用技能牌消耗 |
| 護盾 | 99 | 優先吸收傷害，吸收後扣減 |
| 力量 | 999 | 加在每次攻擊的總傷害上 |
| 敏捷 | 999 | 防禦時加總防禦力（需有防禦牌，只作用一次）；回血時增加回復量 |
| 燃燒 | 999 | 攻擊回合結束時受到等同層數的傷害，並消耗一層 |
| 冰凍 | 999 | 跳過下一個行動回合，之後移除 |

---

## 卡片效果欄位說明

```jsonc
{
  "id": "CardID",
  "type": "Attack / Defense / Both",
  "element": "NONE / PYRO / HYDRO / CRYO / ELECTRO / DENDRO / ANEMO / GEO / ABYSS",
  "attribute": { "attack": 0, "defense": 0 },
  "effects": {
    "change_attack_attribute": { "attack": 0 },
    "apply_element":           { "to_apply": "attacker/victim/this", "element": "..." },
    "apply_effects":           { "effect": "hp/mp/shield/strength/agile/frozen/burning", "to_apply": "...", "amount": 0 },
    "apply_effects2":          { "..." },
    "critic":                  { "rate": 0.0 },
    "add_damage_when_exist_element": { "element": ["..."], "amount": 0 },
    "add_damage_when_frozen":  { "amount": 0 },
    "attack_all_player":       { "attack": 0, "rate": 1.0 },
    "randomly_trigger_effect": { "polls": [ { "apply_effects": { "..." } } ] },
    "revive":                  { "to_apply": "victim/this" },
    "skill":                   { "mp_cost": 0 },
    "wipe_effect":             { "to_apply": "this" }
  }
}
```

**卡片類型判斷邏輯：**
- `attack = 0` 且無 `attack_all_player` → 道具牌
- 有 `attack_all_player` → 範圍攻擊牌
- 其他 → 單體攻擊牌

**skill 牌特殊規則：** 使用後不從手牌移除，但仍正常抽一張新牌。

---

## 前後端通訊協定

### 前端 → 後端

| action | 時機 | 關鍵欄位 |
|--------|------|----------|
| `CreateRoom` | 建立房間 | `player_name` |
| `JoinRoom` | 加入房間 | `player_name`, `room_number` |
| `LeaveRoom` | 離開房間 | `room_number`, `player_name` |
| `StartGame` | 開始遊戲 | `room_number` |
| `playCard` | 攻擊方出牌 | `attacker`, `target`, `cards`, `room_number` |
| `playCardRespond` | 防禦方回應 | `player`, `cards`, `room_number` |

### 後端 → 前端

| action | 時機 |
|--------|------|
| `RenewRoomStatus` | 房間人員異動 |
| `RenewGameStatus` | 遊戲狀態更新（HP/MP/手牌等） |
| `PlayerTurns` | 告知各玩家目前輪到誰（Action/Respond/None） |
| `PlayerAction` | 攻擊方出牌結果（含傷害預覽） |
| `PlayerResponse` | 防禦方回應結果（含防禦力） |
| `PlayerRoundEnd` | 回合結算（所有效果合併為單一封包） |
| `PlayerDead` | 玩家死亡通知 |
| `GameWin` | 遊戲結束，宣布勝者 |

---

## 手牌規則

- 初始手牌：8 張
- 手牌上限：16 張
- 每次出牌後補回等量新牌
- 未出任何牌時補 1 張
- skill 牌使用後不消失，但仍補牌

**抽牌機率：**

| 類別 | 機率 |
|------|------|
| Weapon | 31% |
| Defense | 31% |
| Other | 31% |
| Skill | 7% |
