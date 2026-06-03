import os
import json

def generate_card_map():
    # 🎯 1. 定義要掃描的核心卡牌資料夾（自動忽略 .idea, .mvn 等無關目錄）
    target_folders = ["Defense", "Other", "Skill", "Weapon"]
    
    # 尋找當前目錄下的 CardData 資料夾，或者如果本身就在 CardData 裡面也能執行
    base_dir = "../../../java"
    if os.path.exists("CardData"):
        base_dir = ""
    
    card_ids = set() # 使用 set 確保卡牌 ID 不會重複
    
    print(f"🔍 開始掃描 [{base_dir}] 中的卡牌 ID...")
    
    # 🎯 2. 開始巡邏資料夾
    for folder in target_folders:
        folder_path = os.path.join(base_dir, folder)
        if not os.path.exists(folder_path):
            print(f"⚠️ 找不到資料夾: {folder_path}，跳過...")
            continue
            
        print(f"📁 正在掃描子目錄: {folder}")
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # 排除隱藏檔案或系統檔案
                if file.startswith('.') or file.startswith('Thumbs'):
                    continue
                
                # 💡 從檔名萃取卡牌 ID (去除副檔名，例如 BreakDream.json -> BreakDream)
                card_id, _ = os.path.splitext(file)
                if card_id:
                    card_ids.add(card_id)

    # 🎯 3. 依照字母排序，並組裝成 { "CardID": 0 } 的格式
    sorted_card_ids = sorted(list(card_ids))
    card_map = {card_id: 0 for card_id in sorted_card_ids}
    
    # 🎯 4. 匯出成 JSON 檔案
    output_filename = "card_map.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        # indent=4 確保輸出的格式有縮排、非常漂亮好讀
        json.dump(card_map, f, indent=4, ensure_ascii=False)
        
    print("\n🎉 ==== 蒐集報告 ====")
    print(f"✅ 成功找到 {len(card_map)} 張獨立卡牌！")
    print(f"💾 檔案已成功導出至: {os.path.abspath(output_filename)}")
    print("=====================\n")

if __name__ == "__main__":
    generate_card_map()