import os
import re
import pandas as pd
from dotenv import load_dotenv
from fpdf import FPDF
import streamlit as st
from datetime import datetime
from duckduckgo_search import DDGS
import google.generativeai as genai
from prompt_utils import generate_prompt

# ──────────────────────【初始化設定】──────────────────────
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

if not os.getenv("GEMINI_API_KEY"):
    st.error("⚠️ 尚未設定 GEMINI_API_KEY，請建立 .env 檔案並放入你的 Gemini 金鑰")
    st.stop()

def get_chinese_font_file() -> str:
    fonts_path = r"C:\\Windows\\Fonts"
    for font in ["kaiu.ttf", "msjh.ttc", "msjhbd.ttc", "msjhl.ttc"]:
        path = os.path.join(fonts_path, font)
        if os.path.exists(path):
            return os.path.abspath(path)
    return None

# ──────────────────────【主題查詢】──────────────────────
def search_theme_info(theme: str, max_results: int = 3) -> str:
    try:
        with DDGS() as ddgs:
            results = ddgs.text(theme, max_results=max_results)
            if results:
                return "\n".join([f"{i+1}. {r.get('title','')}：{r.get('body','')}" for i, r in enumerate(results)])
            raise Exception("DuckDuckGo 無結果")
    except Exception as e:
        fallback_prompt = f"請用繁體中文簡要介紹「{theme}」這個主題，字數約150～200字，用於包裝數學故事背景。"
        try:
            model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
            response = model.generate_content(fallback_prompt)
            return f"（備援）Gemini 提供的主題說明：\n{response.text.strip()}"
        except Exception as ge:
            return f"❗主題查詢失敗\nDuckDuckGo 錯誤：{str(e)}\nGemini 錯誤：{str(ge)}"

# ──────────────────────【PDF 產生】──────────────────────
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
    for line in text.splitlines():
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

# ──────────────────────【Streamlit UI】──────────────────────
st.set_page_config("超大機", layout="wide")
st.title("📘 超大機：沉浸式練習題產生器")

# 初始化 session_state
if "selected_df" not in st.session_state:
    st.session_state["selected_df"] = None
if "selected_file" not in st.session_state:
    st.session_state["selected_file"] = None
if "response_text" not in st.session_state:
    st.session_state["response_text"] = ""

with st.sidebar:
    st.header("🧑‍🎓 學生設定")
    root_dir = "file"

    # 第一層：階段
    all_stages = [d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]
    stage = st.selectbox("階段", all_stages)

    # 第二層：年級（僅限國小有）
    grade = None
    if stage == "國小":
        stage_path = os.path.join(root_dir, stage)
        all_grades = [d for d in os.listdir(stage_path) if os.path.isdir(os.path.join(stage_path, d))]
        grade = st.selectbox("年級", all_grades)

    # 第三層：科目
    subject_path = os.path.join(root_dir, stage, grade) if grade else os.path.join(root_dir, stage)
    subjects = [d for d in os.listdir(subject_path) if os.path.isdir(os.path.join(subject_path, d))]
    subject = st.selectbox("科目", subjects)

    # 查找檔案按鈕
    if st.button("🔍 查找檔案") or st.session_state["selected_df"] is None:
        file_path = os.path.join(subject_path, subject)
        csv_files = [f for f in os.listdir(file_path) if f.endswith(".csv")]
        if csv_files:
            selected_file = st.selectbox("請選擇檔案", csv_files, key="file_select")
            df = pd.read_csv(os.path.join(file_path, selected_file))
            st.session_state["selected_df"] = df
            st.session_state["selected_file"] = selected_file
            st.success(f"✅ 成功載入檔案：{selected_file}")
        else:
            st.warning("⚠️ 此資料夾內無可用的 CSV 檔案")
            st.session_state["selected_df"] = None
            st.session_state["selected_file"] = None

    # 顯示學生設定欄位
    if st.session_state["selected_df"] is not None:
        df = st.session_state["selected_df"]
        student_list = [col for col in df.columns if col != "題目"]
        student = st.selectbox("學生姓名", student_list)
        theme = st.text_input("主題", "海綿寶寶")
        tf = st.slider("是非題", 1, 10, 2)
        mc = st.slider("選擇題", 1, 10, 2)
        app = st.slider("應用題", 1, 10, 2)

# 題目生成
if st.session_state["selected_df"] is not None:
    st.subheader("📄 題目生成")
    if st.button("✏️ 生成題目"):
        with st.spinner("生成中..."):
            preview_df = df[["題目", student]].head(30)
            theme_info = search_theme_info(theme)
            gen_prompt = f"以下為學生作答資料（前30題）：\n{preview_df.to_csv(index=False)}\n\n{generate_prompt(student, theme, tf, mc, app, theme_info)}"
            model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
            result = model.generate_content(gen_prompt)
            question_text = result.text.strip()
            st.session_state["response_text"] = question_text
            st.text_area("🧠 題目內容", question_text, height=400)
            pdf_path = generate_pdf(question_text)
            if pdf_path:
                with open(pdf_path, "rb") as f:
                    st.download_button("📥 下載題目 PDF", data=f, file_name=pdf_path, mime="application/pdf")

    # 題目詳解
    st.divider()
    st.subheader("📘 題目詳解")
    if st.button("📘 生成詳解 PDF"):
        with st.spinner("產生詳解中..."):
            sol_path = generate_solution_pdf(st.session_state["response_text"])
            with open(sol_path, "rb") as f:
                st.download_button("📥 下載詳解 PDF", data=f, file_name=sol_path, mime="application/pdf")

    # 錯題報表
    st.divider()
    st.subheader("📊 錯題分析報告")
    if st.button("📋 生成報表建議"):
        with st.spinner("分析中..."):
            feedback = generate_feedback(df, student)
            st.markdown("### 🔍 分析結果")
            st.write(feedback)