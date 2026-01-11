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
        else:
            print(f"   ✅ 노션 저장 성공!")
    except Exception as e:
        print(f"   ❌ 노션 에러: {e}")

# --- [메인] ---
async def main():
    print("🚀 텔레그램 -> 노션/메시지 봇 가동...")
    
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
    await client.connect()

    # 한국 시간 설정
    korea_now = datetime.utcnow() + timedelta(hours=9)
    today_str = korea_now.strftime("%Y-%m-%d")
    
    # 24시간 전 데이터부터 (매일 돌리니까)
    time_limit = korea_now - timedelta(hours=24)

    # 텔레그램/깃허브용 리포트 텍스트
    full_report = f"# 📅 {today_str} 텔레그램 요약\n\n"
    has_update = False

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
            
            print("완료! -> 노션 저장...", end=" ")
            
            # 1. 노션 전송
            page_title = f"[{today_str}] {chat_title} 요약"
            send_to_notion(page_title, chat_title, summary_text, today_str)
            
            # 2. 통합 리포트 누적
            full_report += f"### 📢 {chat_title}\n{summary_text}\n\n---\n\n"
            has_update = True
            
        except Exception as e:
            print(f"에러: {e}")

    # ✅ 3. 나에게 텔레그램 메시지 보내기
    if has_update:
        try:
            if len(full_report) > 4000:
                await client.send_message('me', full_report[:4000] + "\n...(생략)")
            else:
                await client.send_message('me', full_report)
            print("📬 텔레그램 전송 완료!")
        except Exception as e:
            print(f"❌ 전송 실패: {e}")

    await client.disconnect()

    # ✅ 4. 깃허브 README 업데이트
    if has_update:
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(full_report)
        
        os.system("git config --global user.email 'bot@github.com'")
        os.system("git config --global user.name 'NewsBot'")
        os.system("git add README.md")
        os.system("git commit -m 'Update Telegram Report'")
        os.system("git push")
        print("\n🌐 깃허브 업데이트 완료!")
    else:
        print("\n💤 요약할 내용이 없습니다.")

if __name__ == '__main__':
    asyncio.run(main())
