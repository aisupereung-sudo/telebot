import os
import asyncio
import requests # 노션 통신용
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
from datetime import datetime, timedelta

# ==============================================================================
# 🔐 환경변수
# ==============================================================================
try:
    API_ID = os.environ["TG_API_ID"]
    API_HASH = os.environ["TG_API_HASH"]
    SESSION_STR = os.environ["TG_SESSION"]
    GEMINI_KEY = os.environ["GEMINI_KEY"]
    NOTION_KEY = os.environ["NOTION_KEY"]
    NOTION_DB_ID = os.environ["NOTION_DB_ID"]
except KeyError as e:
    print(f"❌ 환경변수 설정 오류: {e}")
    exit(1)

# 🎯 타겟 채팅방 설정
TARGET_CHATS = [
    '주식', '뉴스', '부동산', '창고', '리서치', '투자', 
    '여의도', '렙', 'research', '부자', '데이터', '공부방', 
    '고수', '인사이트', '탐방', '지식', 'IR', '증권'
]

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- [기능] 노션 전송 함수 ---
def send_to_notion(title, chat_name, summary, date_str):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    # 노션 블록(본문) 구성 - 2000자 제한 안전하게 자르기
    safe_summary = summary[:1900]
    
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "제목": {"title": [{"text": {"content": title}}]},
            "방이름": {"select": {"name": chat_name}},
            "날짜": {"date": {"start": date_str}},
            "요약": {"rich_text": [{"text": {"content": safe_summary[:100] + "..."}}]} 
        },
        "children": [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "💡 3줄 핵심 요약"}}]}
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": safe_summary}}]}
            }
        ]
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code != 200:
            print(f"   ❌ 노션 저장 실패: {res.text}")
    except Exception as e:
