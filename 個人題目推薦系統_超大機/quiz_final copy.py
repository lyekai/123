import os
import pandas as pd
from dotenv import load_dotenv
import google.generativeai as genai
from fpdf import FPDF
import gradio as gr
from datetime import datetime

load_dotenv()

def get_chinese_font_file() -> str:
    fonts_path = r"C:\\Windows\\Fonts"
    candidates = ["kaiu.ttf", "msjh.ttc", "msjhbd.ttc", "msjhl.ttc"]
    for font in candidates:
        font_path = os.path.join(fonts_path, font)
        if os.path.exists(font_path):
            return os.path.abspath(font_path)
    return None

def generate_prompt(student_name: str, theme: str, num_tf: int, num_mc: int, num_app: int) -> str:
    return f"""你是一名資深數學老師，請根據"{student_name}"同學的答題狀況進行錯誤題目預測：

1. 每個欄位皆表示為一位學生在各題的答題狀況；
2. 其中0表示該學生在該題答錯，1表示該題答對，
3. 禁止出與數學無關的題目，不要輸出答案，
4. 數學題目中須結合與'{theme}'相關的連貫故事
5. 每種題型（是非題 / 選擇題 / 應用題）標題只能出現一次。
6. 禁止出現多組題目、多份試卷、備用題或延伸題
7. 所有題目請用繁體中文撰寫
8. 題號後方不須空行

請預測該學生的錯題，並生成一份包含：
- 是非題：{num_tf} 題
- 選擇題：{num_mc} 題
- 應用題：{num_app} 題

📌 **題目格式請完全照以下方式呈現（必須一致）：**
一、是非題  
台灣的人口密度比美國高，則台灣是基準量？  

二、選擇題  
若圓的半徑為3公分，面積是多少？ (1)9π(2)6π(3)3π(4)12π  

三、應用題  
媽媽買了3顆蘋果和2根香蕉共花60元，若每顆蘋果20元，香蕉多少錢？

📄格式與語言注意事項：
- 題號格式為：1. 2. 3. ……（中間無空格，無換行）
- 選擇題選項必須以 (1)(2)(3)(4) 呈現，且選項不得重複。
- 所有內容不得加入「請作答」「請觀察圖」或其他引導語。
- 禁止產出除題目以外的內容。
"""

def generate_pdf(text: str) -> str:
    pdf = FPDF(format="A4")
    pdf.add_page()

    font_path = get_chinese_font_file()
    if not font_path:
        return "錯誤：找不到中文字型，請安裝 kaiu.ttf 或 msjh.ttc"

    font_name = os.path.splitext(os.path.basename(font_path))[0]
    pdf.add_font("ChineseFont", "", font_path, uni=True)
    pdf.set_font("ChineseFont", size=12)

    y_offset = 15
    line_height = 8
    pdf.set_y(y_offset)

    for line in text.splitlines():
        font_size = 14 if line.strip() in ["一、是非題", "二、選擇題", "三、應用題"] else 12
        pdf.set_font("ChineseFont", size=font_size)
        pdf.multi_cell(0, line_height, line, border=0, align='L')
        if pdf.get_y() > pdf.h - 15:
            pdf.add_page()
            pdf.set_y(15)

    pdf_filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(pdf_filename)
    return pdf_filename

def gradio_handler(csv_file, student_name, theme, num_tf, num_mc, num_app):
    if csv_file is not None:
        df = pd.read_csv(csv_file.name)
        if student_name not in df.columns:
            return f"找不到名字：{student_name}，請確認是否正確輸入。", None

        df_preview = df.head(30)
        csv_preview = df_preview.to_csv(index=False)

        prompt = f"""以下是學生答題資料（前30筆，包含「{student_name}」）：\n{csv_preview}\n\n請依照以下規則產題：\n{generate_prompt(student_name, theme, num_tf, num_mc, num_app)}"""

        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("未能加载 GEMINI_API_KEY，请检查 .env 文件中的配置")

        model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        pdf_path = generate_pdf(response_text)
        return response_text, pdf_path
    else:
        return "請上傳包含答題資料的 CSV 檔案", None

def generate_feedback_handler(csv_file, student_name):
    if csv_file is not None:
        df = pd.read_csv(csv_file.name)
        if student_name not in df.columns:
            return f"找不到名字：{student_name}，請確認是否正確輸入。"

        student_data = df[student_name].tolist()
        student_summary = ', '.join([str(x) for x in student_data])

        feedback_prompt = f"""你是一名有經驗的數學老師。根據學生「{student_name}」的答題狀況（1為答對，0為答錯），請給出學習回饋與改善建議。

答題紀錄如下：
{student_summary}

請以繁體中文提供：
1. 學生整體表現的簡要評估
2. 容易出錯的類型與可能原因
3. 具體可行的學習建議（避免空泛建議）"""

        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("未能加载 GEMINI_API_KEY，请检查 .env 文件中的配置")

        model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
        response = model.generate_content(feedback_prompt)
        return response.text.strip()
    else:
        return "請上傳包含答題資料的 CSV 檔案"

# Gradio UI
with gr.Blocks() as demo:
    gr.Markdown("# 📊 錯題分析與考卷生成系統")
    
    with gr.Row():
        csv_input = gr.File(label="上傳 CSV 檔案")
        student_name_input = gr.Textbox(label="請輸入你的姓名", value="張智翔")
        theme_input = gr.Textbox(label="請輸入題目主題", value="神秘花園")
    
    with gr.Row():
        num_tf = gr.Slider(0, 10, value=3, step=1, label="是非題數")
        num_mc = gr.Slider(0, 10, value=4, step=1, label="選擇題數")
        num_app = gr.Slider(0, 10, value=3, step=1, label="應用題數")
    
    output_text = gr.Textbox(label="生成題目內容", lines=15, interactive=False)
    output_pdf = gr.File(label="下載 PDF 考卷")
    submit_button = gr.Button("✏️ 生成考卷")

    submit_button.click(
        fn=gradio_handler,
        inputs=[csv_input, student_name_input, theme_input, num_tf, num_mc, num_app],
        outputs=[output_text, output_pdf]
    )

    gr.Markdown("---")

    feedback_button = gr.Button("📋 生成報表")
    feedback_output = gr.Textbox(label="報表建議回饋", lines=10, interactive=False)

    feedback_button.click(
        fn=generate_feedback_handler,
        inputs=[csv_input, student_name_input],
        outputs=feedback_output
    )

demo.launch()
