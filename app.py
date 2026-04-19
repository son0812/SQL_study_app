import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
import easyocr
import numpy as np
from PIL import Image

# --- 1. 초기 설정 ---
DB_FILE = 'attendance.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    is_success = any(word.lower() in full_text.lower() for word in keywords)
    return is_success, full_text

# --- 3. UI ---
st.set_page_config(page_title="코테 스터디 출석부", layout="wide")
init_db()

st.title("SQL 쿼리 스터디 출석 대시보드")
st.sidebar.header("📆 출석 체크")

team_members = ["김예지", "손승안", "안재영", "오준석", "최다희"]
selected_name = st.sidebar.selectbox("내 이름 선택", team_members)
uploaded_file = st.sidebar.file_uploader("인증샷 업로드", type=['png', 'jpg', 'jpeg'])

# --- 제출 여부 체크 ---
today = datetime.now().strftime("%Y-%m-%d")
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
        success_found, detected_text = run_ocr(img)

        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # 최종 중복 체크
        c.execute("SELECT * FROM attendance WHERE name=? AND date=?", (selected_name, today))
        already_exists = c.fetchone()

        if already_exists:
            st.sidebar.warning("이미 제출됨")
        else:
            status = "Y" if success_found else "확인필요"

            c.execute(
                "INSERT INTO attendance (name, date, time, status) VALUES (?, ?, ?, ?)",
                (selected_name, today, now.strftime("%H:%M:%S"), status)
            )
            conn.commit()

            if success_found:
                st.sidebar.success("출석 완료!")
            else:
                st.sidebar.warning("확인 필요 (관리자 승인 대기)")

        conn.close()

# --- 4. 대시보드 ---
conn = sqlite3.connect(DB_FILE)
df = pd.read_sql_query("SELECT * FROM attendance", conn)

col1, col2, col3 = st.columns(3)
today_count = len(df[df['date'] == today]) if not df.empty else 0

col1.metric("오늘 출석", f"{today_count} / {len(team_members)}")
col2.metric("총 제출", len(df))
col3.metric("현재 시간", datetime.now().strftime("%H:%M"))

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

# --- 5. 관리자 승인 ---
st.markdown("---")
st.subheader("관리자 승인")

conn = sqlite3.connect(DB_FILE)
df_admin = pd.read_sql_query("SELECT * FROM attendance WHERE status='확인필요'", conn)

if not df_admin.empty:
    for idx, row in df_admin.iterrows():
        st.write(f"{row['name']} | {row['date']} | {row['time']}")

        if st.button(f"승인_{row['id']}"):
            c = conn.cursor()
            c.execute("UPDATE attendance SET status='Y' WHERE id=?", (row['id'],))
            conn.commit()
            st.success("승인 완료")
else:
    st.info("승인 대기 없음")

conn.close()
