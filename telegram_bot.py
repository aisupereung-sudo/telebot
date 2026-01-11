iimport os
import asyncio
import requests # 노션 통신용
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
from datetime import datetime, timedelta

# ==============================================================================
# 🔐 환경변수
# ==============================================================================
API_ID = os.environ["TG_API_ID"]
API_HASH = os.environ["TG_API_HASH"]
SESSION_STR = os.environ["TG_SESSION"]
GEMINI_KEY = os.environ["GEMINI_KEY"]
NOTION_KEY = os.environ["NOTION_KEY"]
NOTION_DB_ID = os.environ["NOTION_DB_ID"]

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
            # 요약 컬럼에도 살짝 보여주기
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
        if res.status_code == 200:
            print(f"   ✅ 노션 저장 완료!")
        else:
            print(f"   ❌ 노션 저장 실패: {res.text}")
    except Exception as e:
        print(f"   ❌ 노션 에러: {e}")

# --- [메인] ---
async def main():
    print("🚀 텔레그램 -> 노션 봇 가동...")
    
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
    await client.connect()

    # 한국 시간 설정
    korea_now = datetime.utcnow() + timedelta(hours=9)
    today_str = korea_now.strftime("%Y-%m-%d")
    
    # 24시간 전 데이터부터
    time_limit = korea_now - timedelta(hours=24)

    async for dialog in client.iter_dialogs():
        chat_title = dialog.name
        
        # 타겟 방 확인
        is_target = False
        for target in TARGET_CHATS:
            if target in chat_title:
                is_target = True
                break
        if not is_target: continue

        print(f"🔍 [{chat_title}] 읽는 중...", end=" ")
        
        messages_text = ""
        count = 0
        
        try:
            async for msg in client.iter_messages(dialog, limit=50):
                if msg.date.replace(tzinfo=None) < time_limit.replace(tzinfo=None): break
                if msg.text and len(msg.text) > 20: 
                    messages_text += f"- {msg.text}\n"
                    count += 1
        except:
            print("패스 (권한 없음)")
            continue
        
        if count == 0:
            print("패스 (새 글 없음)")
            continue
            
        print(f"{count}개 요약...", end=" ")

        try:
            # AI 요약
            prompt = f"""
            텔레그램 대화를 핵심만 3줄로 요약해.
            [방] {chat_title}
            [내용] {messages_text[:5000]}
            """
            response = model.generate_content(prompt)
            summary_text = response.text
            
            print("AI 완료! -> 노션 전송 중...", end=" ")
            
            # ⭐️ 노션으로 쏘기!
            # 제목: [날짜] 방이름 요약
            page_title = f"[{today_str}] {chat_title} 요약"
            send_to_notion(page_title, chat_title, summary_text, today_str)
            
        except Exception as e:
            print(f"에러: {e}")

    await client.disconnect()
    print("\n🎉 모든 작업 완료!")

if __name__ == '__main__':
    asyncio.run(main())
