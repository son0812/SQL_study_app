import streamlit as st
import pandas as pd
import sqlite3
import os
import time
from datetime import datetime, timedelta
import easyocr
import numpy as np
from PIL import Image

# --- 1. 초기 설정 (DB 및 폴더) ---
DB_FILE = 'attendance.db'
IMG_DIR = 'uploaded_images'

if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS attendance 
                 (name TEXT, date TEXT, time TEXT, status TEXT, img_path TEXT)''')
    conn.commit()
    conn.close()

# --- 2. 핵심 기능 함수 ---
def cleanup_old_images(days=7):
    """7일 지난 이미지와 DB 기록 삭제"""
    now = time.time()
    for f in os.listdir(IMG_DIR):
        f_path = os.path.join(IMG_DIR, f)
        if os.stat(f_path).st_mtime < now - (days * 86400):
            os.remove(f_path)

@st.cache_resource
def load_ocr():
    """OCR 엔진 로드 (캐싱하여 속도 향상)"""
    return easyocr.Reader(['ko', 'en'])

def run_ocr(image):
    reader = load_ocr()
    result = reader.readtext(np.array(image), detail=0)
    full_text = " ".join(result)
    
    # 성공 키워드 체크
    keywords = ["Success", "Accepted", "정답", "Pass", "통과"]
    is_success = any(word.lower() in full_text.lower() for word in keywords)
    return is_success, full_text

# --- 3. UI 구성 ---
st.set_page_config(page_title="코테 스터디 출석부", layout="wide")
init_db()
cleanup_old_images() # 실행 시 자동 청소

st.title("🚀 코딩 테스트 출석 대시보드")
st.sidebar.header("📍 출석 체크")

# 팀원 명단 (여기에 팀원 이름을 넣으세요)
team_members = ["팀원A", "팀원B", "팀원C", "팀원D", "팀원E"]
selected_name = st.sidebar.selectbox("내 이름 선택", team_members)
uploaded_file = st.sidebar.file_uploader("인증샷 업로드 (LeetCode, Programmers 등)", type=['png', 'jpg', 'jpeg'])

if uploaded_file:
    img = Image.open(uploaded_file)
    st.sidebar.image(img, caption="업로드된 이미지", use_container_width=True)
    
    if st.sidebar.button("데이터 분석 및 제출"):
        with st.spinner('이미지를 분석 중입니다...'):
            success_found, detected_text = run_ocr(img)
            
            # 파일 저장
            file_name = f"{selected_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            img_path = os.path.join(IMG_DIR, file_name)
            img.save(img_path)
            
            # DB 저장
            now = datetime.now()
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            status = "Y" if success_found else "확인필요"
            c.execute("INSERT INTO attendance VALUES (?, ?, ?, ?, ?)",
                      (selected_name, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), status, img_path))
            conn.commit()
            conn.close()
            
            if success_found:
                st.sidebar.success(f"분석 결과: [성공 확인] - 출석 완료!")
            else:
                st.sidebar.warning(f"텍스트 인식 불명확: 관리자 확인이 필요할 수 있습니다.")

# --- 4. 대시보드 (Power BI 스타일) ---
conn = sqlite3.connect(DB_FILE)
df = pd.read_sql_query("SELECT * FROM attendance", conn)
conn.close()

# 상단 요약 지표
col1, col2, col3 = st.columns(3)
today_str = datetime.now().strftime("%Y-%m-%d")
today_count = len(df[df['date'] == today_str]) if not df.empty else 0

col1.metric("오늘 출석 인원", f"{today_count}명 / {len(team_members)}명")
col2.metric("이번 주 총 제출", len(df))
col3.metric("최근 업데이트", datetime.now().strftime("%H:%M"))

st.markdown("---")

# 실시간 출석 표
st.subheader("🗓️ 최근 출석 현황 (실시간)")
if not df.empty:
    # 표 형식 가공
    display_df = df.sort_values(by=['date', 'time'], ascending=False).head(20)
    st.dataframe(display_df[['name', 'date', 'time', 'status']], use_container_width=True)
    
    # 간단한 그래프 (인원별 통계)
    st.subheader("👤 팀원별 누적 출석")
    chart_data = df['name'].value_counts()
    st.bar_chart(chart_data)
else:
    st.info("아직 제출된 내역이 없습니다. 왼쪽 사이드바에서 첫 인증샷을 올려보세요!")