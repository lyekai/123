import os
import csv
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

# 載入 Gemini API 金鑰
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# 定義階段、年級、科目
grades_subjects = {
    "一年級": ["國語", "數學", "英文"],
    "二年級": ["國語", "數學", "英文"],
    "三年級": ["國語", "數學", "英文", "自然", "社會"],
    "四年級": ["國語", "數學", "英文", "自然", "社會"],
    "五年級": ["國語", "數學", "英文", "自然", "社會"],
    "六年級": ["國語", "數學", "英文", "自然", "社會"]
}

# 建立 curriculum 資料夾
output_dir = "curriculum"
os.makedirs(output_dir, exist_ok=True)

# 定義 Gemini 模型
model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")

# 查詢 prompt 模板
def get_prompt(grade, subject):
    return f"""你是一名國小教師，請根據台灣教育部課綱與常見教學內容，整理出「國小{grade}{subject}」的主要學習內容。

請輸出一份教學大綱，包含以下欄位：
1. 單元名稱
2. 教學目標
3. 涉及的數學或科學或語文概念（根據科目）
4. 學生常見的迷思或錯誤概念（如有）
5. 詳細的單元內容說明（可包含教學方式、教材例子等）

請以繁體中文逐列列出，不需使用表格符號，格式如下：
單元名稱：xxx
教學目標：xxx
概念：xxx
常見錯誤：xxx
詳細內容：xxx

---

依此格式列出 5～10 組，內容需真實、具體，擬作課綱資料使用。
"""

# 開始生成與儲存
for grade, subjects in grades_subjects.items():
    for subject in subjects:
        prompt = get_prompt(grade, subject)
        try:
            print(f"🔍 正在查詢：國小{grade}{subject}...")
            response = model.generate_content(prompt)
            content = response.text.strip()

            # 轉為 csv 格式
            units = content.split("\n\n")
            rows = [["單元名稱", "教學目標", "概念", "常見錯誤", "詳細內容"]]
            for unit in units:
                lines = unit.splitlines()
                unit_data = {}
                for line in lines:
                    if "單元名稱：" in line:
                        unit_data["單元名稱"] = line.split("：", 1)[1].strip()
                    elif "教學目標：" in line:
                        unit_data["教學目標"] = line.split("：", 1)[1].strip()
                    elif "概念：" in line:
                        unit_data["概念"] = line.split("：", 1)[1].strip()
                    elif "常見錯誤：" in line:
                        unit_data["常見錯誤"] = line.split("：", 1)[1].strip()
                    elif "詳細內容：" in line:
                        unit_data["詳細內容"] = line.split("：", 1)[1].strip()
                if len(unit_data) == 5:
                    rows.append([
                        unit_data["單元名稱"],
                        unit_data["教學目標"],
                        unit_data["概念"],
                        unit_data["常見錯誤"],
                        unit_data["詳細內容"]
                    ])

            filename = f"{output_dir}/國小{grade}{subject}.csv"
            with open(filename, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(rows)

            print(f"✅ 已完成：{filename}")
        except Exception as e:
            print(f"❌ 發生錯誤：國小{grade}{subject}：{str(e)}")

print("🎉 全部課綱資料已完成！")

