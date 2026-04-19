import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import easyocr
import numpy as np
from PIL import Image

# --- KST 시간 함수 추가 ---
def get_kst_now():
    return datetime.utcnow() + timedelta(hours=9)

# --- 1. 초기 설정 ---
DB_FILE = 'attendance.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            name TEXT,
            date TEXT,
            time TEXT,
            status TEXT,
            UNIQUE(name, date)
        )
    ''')
    conn.commit()
    conn.close()

# --- 2. OCR ---
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['ko', 'en'])

def run_ocr(image):
    reader = load_ocr()
    result = reader.readtext(np.array(image), detail=0)
    full_text = " ".join(result)

    keywords = ["Success", "Accepted", "정답", "Pass", "통과"]
    return any(word.lower() in full_text.lower() for word in keywords)

# --- 3. UI ---
st.set_page_config(page_title="코테 스터디 출석부", layout="wide")
init_db()

st.title("SQL 쿼리 스터디 출석 대시보드")
st.sidebar.header("📆 출석 체크")

team_members = ["김예지", "손승안", "안재영", "오준석", "최다희"]
selected_name = st.sidebar.selectbox("내 이름 선택", team_members)
uploaded_file = st.sidebar.file_uploader("인증샷 업로드", type=['png', 'jpg', 'jpeg'])

# --- KST 기준 시간 ---
now = get_kst_now()
today = now.strftime("%Y-%m-%d")

# --- 제출 여부 체크 ---
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT * FROM attendance WHERE name=? AND date=?", (selected_name, today))
already_exists = c.fetchone()
conn.close()

if already_exists:
    st.sidebar.warning("오늘은 이미 출석 완료했습니다 ✅")

submit_btn = st.sidebar.button("데이터 분석 및 제출", disabled=bool(already_exists))

# --- 제출 처리 ---
if uploaded_file and submit_btn:
    img = Image.open(uploaded_file)

    with st.spinner("이미지 분석 중..."):
        success_found = run_ocr(img)

        if not success_found:
            st.sidebar.error("❌ 이미지 인식 불가. Teams로 접속해서 제출해주세요.")
        else:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()

            c.execute("SELECT * FROM attendance WHERE name=? AND date=?", (selected_name, today))
            already_exists = c.fetchone()

            if already_exists:
                st.sidebar.warning("이미 제출됨")
            else:
                c.execute(
                    "INSERT INTO attendance (name, date, time, status) VALUES (?, ?, ?, ?)",
                    (selected_name, today, now.strftime("%H:%M:%S"), "Y")
                )
                conn.commit()
                st.sidebar.success("출석 완료!")

            conn.close()

# --- 4. 대시보드 ---
conn = sqlite3.connect(DB_FILE)
df = pd.read_sql_query("SELECT * FROM attendance", conn)

col1, col2, col3 = st.columns(3)
today_count = len(df[df['date'] == today]) if not df.empty else 0

col1.metric("오늘 출석", f"{today_count} / {len(team_members)}")
col2.metric("총 제출", len(df))
col3.metric("현재 시간", now.strftime("%H:%M"))

st.markdown("---")

st.subheader("📋 최근 출석")
if not df.empty:
    display_df = df.sort_values(by=['date', 'time'], ascending=False).head(20)
    st.dataframe(display_df[['name', 'date', 'time', 'status']], use_container_width=True)

    st.subheader("📊 출석 통계")
    st.bar_chart(df['name'].value_counts())
else:
    st.info("데이터 없음")

conn.close()
