import os
import re
import pandas as pd
from dotenv import load_dotenv
from fpdf import FPDF
import streamlit as st
from datetime import datetime
from duckduckgo_search import DDGS
import google.generativeai as genai

# 載入 .env 並設置 Gemini API 金鑰
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

if not os.getenv("GEMINI_API_KEY"):
    st.error("⚠️ 尚未設定 GOOGLE_API_KEY，請建立 .env 檔案並放入你的 Gemini 金鑰")
    st.stop()

def get_chinese_font_file() -> str:
    fonts_path = r"C:\\Windows\\Fonts"
    candidates = ["kaiu.ttf", "msjh.ttc", "msjhbd.ttc", "msjhl.ttc"]
    for font in candidates:
        font_path = os.path.join(fonts_path, font)
        if os.path.exists(font_path):
            return os.path.abspath(font_path)
    return None

def search_theme_info(theme: str, max_results: int = 3) -> str:
    try:
        with DDGS() as ddgs:
            results = ddgs.text(theme, max_results=max_results)
            summaries = []
            for i, res in enumerate(results):
                title = res.get("title", "")
                snippet = res.get("body", "")
                summaries.append(f"{i+1}. {title}：{snippet}")
            if summaries:
                return "\n".join(summaries)
            else:
                raise Exception("DuckDuckGo 無結果")
    except Exception as e:
        fallback_prompt = f"請用繁體中文簡要介紹「{theme}」這個主題，字數約150～200字，用於包裝數學故事背景。"
        try:
            model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
            response = model.generate_content(fallback_prompt)
            return f"（備援）Gemini 提供的主題說明：\n{response.text.strip()}"
        except Exception as ge:
            return f"❗主題查詢失敗\nDuckDuckGo 錯誤：{str(e)}\nGemini 錯誤：{str(ge)}"

def generate_prompt(student_name, theme, num_tf, num_mc, num_app, theme_info):
    return f"""你是一名資深數學老師，請根據"{student_name}"同學的答題狀況與所有人的易錯題目進行錯誤題目預測：

以下是與主題「{theme}」相關的背景資料，請根據這些資訊融合題目故事中，讓整份試卷充滿沉浸感：

{theme_info}

📌 **整體要求：**
1. 以「{theme}」為主題撰寫一個完整故事，角色與背景需一致。
2. 該故事將貫穿整份試卷，三種類型的題目須有承接性。
3. 每大題（是非、選擇、應用）開頭需有100～150字故事延續情節。
4. 所有題目需與數學概念相關，避免出現答案與解說。
5. 僅以繁體中文撰寫，語句清晰。

📄 格式範例如下：
一、是非題  
"故事背景"  
1.(題目)  
...

二、選擇題  
"故事背景"  
1.(題目)  
...

三、應用題  
"故事背景"  
1.(題目)  
...

選項格式：選擇題使用 (1)(2)(3)(4)，選項不得重複。

題數：
- 是非題：{num_tf} 題  
- 選擇題：{num_mc} 題  
- 應用題：{num_app} 題
"""

def generate_pdf(text: str) -> str:
    pdf = FPDF(format="A4")
    pdf.add_page()
    font_path = get_chinese_font_file()
    if not font_path:
        return "❗找不到中文字型（請安裝 kaiu.ttf 或 msjh.ttc）"

    pdf.add_font("ChineseFont", "", font_path, uni=True)
    pdf.set_font("ChineseFont", size=12)
    pdf.set_y(15)
    line_height = 8

    lines = text.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped in ["一、是非題", "二、選擇題", "三、應用題"]:
            pdf.set_font("ChineseFont", size=14)
            pdf.ln(8)
            pdf.multi_cell(0, line_height, stripped)
            pdf.ln(6)
        elif re.match(r"^\d+\.", stripped):
            pdf.set_font("ChineseFont", size=12)
            pdf.multi_cell(0, line_height, stripped)
        elif stripped:
            pdf.multi_cell(0, line_height, stripped)

        if pdf.get_y() > pdf.h - 15:
            pdf.add_page()
            pdf.set_y(15)

    pdf_filename = f"超大機題目_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(pdf_filename)
    return pdf_filename

def generate_solution_pdf(question_text: str) -> str:
    prompt = f"""你是一名有經驗的數學老師，請根據以下題目撰寫詳解（跳過故事背景）：

{question_text}

詳解格式：
【第X題詳解】
（解說文字）

請用繁體中文、條理清楚、解釋數學概念與解題思路。"""
    model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
    response = model.generate_content(prompt)
    return generate_pdf(response.text.strip())

# 初始化 session state
if "response_text" not in st.session_state:
    st.session_state["response_text"] = ""

def generate_feedback(df, student_name):
    wrong = df[df[student_name] == 0]
    if wrong.empty:
        return f"學生「{student_name}」沒有錯題，表現優秀！"
    wrong_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(wrong['題目'])])
    prompt = f"""以下是學生「{student_name}」在數學測驗中的錯題：

{wrong_text}

請依以下三點提供分析與建議（使用繁體中文）：
1. 錯題共通點
2. 可能錯誤原因
3. 可執行的學習建議"""
    model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
    response = model.generate_content(prompt)
    return response.text.strip()

# UI 部分
st.set_page_config("超大機", layout="wide")
st.title("📘 超大機：沉浸式數學練習題產生器")

with st.sidebar:
    st.header("🧑‍🎓 學生設定")
    uploaded_file = st.file_uploader("上傳學生作答 CSV", type=["csv"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        student_names = [col for col in df.columns if col != "題目"]
        student = st.selectbox("請選擇學生姓名", options=student_names)
        theme = st.text_input("主題", "海綿寶寶")
        tf = st.slider("是非題數", 1, 10, 2)
        mc = st.slider("選擇題數", 1, 10, 2)
        app = st.slider("應用題數", 1, 10, 2)

if uploaded_file:
    st.subheader("📄 題目生成")
    if st.button("✏️ 生成題目"):
        with st.spinner("生成中..."):
            preview_df = df[["題目", student]].head(30)
            theme_info = search_theme_info(theme)
            gen_prompt = f"以下為學生作答資料（前30題）：\n{preview_df.to_csv(index=False)}\n\n{generate_prompt(student, theme, tf, mc, app, theme_info)}"
            model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
            result = model.generate_content(gen_prompt)
            question_text = result.text.strip()
            st.text_area("🧠 題目內容", question_text, height=400)
            pdf_path = generate_pdf(question_text)
            if pdf_path:
                with open(pdf_path, "rb") as f:
                    st.download_button("📥 下載題目 PDF", data=f, file_name=pdf_path, mime="application/pdf")

    st.divider()
    st.subheader("📘 題目詳解")
    if st.button("📘 生成詳解 PDF"):
        with st.spinner("產生詳解中..."):
            sol_path = generate_solution_pdf(question_text)
            with open(sol_path, "rb") as f:
                st.download_button("📥 下載詳解 PDF", data=f, file_name=sol_path, mime="application/pdf")

    st.divider()
    st.subheader("📊 錯題分析報告")
    if st.button("📋 生成報表建議"):
        with st.spinner("分析中..."):
            feedback = generate_feedback(df, student)
            st.markdown("### 🔍 分析結果")
            st.write(feedback)
