import os
import asyncio
import requests
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

# 🎯 타겟 채팅방
TARGET_CHATS = [
    '주식', '뉴스', '부동산', '창고', '리서치', '투자', 
    '여의도', '렙', 'research', '부자', '데이터', '공부방', 
    '고수', '인사이트', '탐방', '지식', 'IR', '증권'
]

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# --- [기능] 노션 전송 (디자인 업그레이드 Ver) ---
def send_to_notion(title, chat_name, summary, original_text, date_str):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    # 노션 텍스트 길이 제한 안전장치 (2000자)
    safe_summary = summary[:1900]
    safe_original = original_text[:1900] + "\n...(내용이 길어서 생략됨)" if len(original_text) > 1900 else original_text

    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "제목": {"title": [{"text": {"content": title}}]},
            "방이름": {"select": {"name": chat_name}}, # '선택' 타입
            "날짜": {"date": {"start": date_str}},
            "요약": {"rich_text": [{"text": {"content": safe_summary[:100] + "..."}}]} 
        },
        "children": [
            # 1. 💡 요약 강조 박스 (Callout Block)
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{"text": {"content": safe_summary}}],
                    "icon": {"emoji": "💡"},
                    "color": "gray_background"
                }
            },
            # 2. 구분선
            {
                "object": "block",
                "type": "divider",
                "divider": {}
            },
            # 3. 📂 원본 대화 펼치기 (Toggle Block)
            {
                "object": "block",
                "type": "toggle",
                "toggle": {
                    "rich_text": [{"text": {"content": "💬 원본 대화 내용 보기 (클릭)"}}],
                    "children": [
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{"text": {"content": safe_original}}]
                            }
                        }
                    ]
                }
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
    print("🚀 텔레그램 -> 노션(디자인UP) 가동...")
    
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
    await client.connect()

    korea_now = datetime.utcnow() + timedelta(hours=9)
    today_str = korea_now.strftime("%Y-%m-%d")
    time_limit = korea_now - timedelta(hours=24)

    full_report = f"# 📅 {today_str} 텔레그램 요약\n\n"
    has_update = False

    async for dialog in client.iter_dialogs():
        chat_title = dialog.name
        
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
            # ✨ 프롬프트 강화: 더 깔끔하게 요약하도록 지시
            prompt = f"""
            너는 주식/경제 정보 요약 전문가야.
            아래 텔레그램 대화 내용을 분석해서 가장 중요한 인사이트를 정리해.
            
            [채팅방] {chat_title}
            [내용]
            {messages_text[:4000]}
            
            [요약 규칙]
            1. '잡담'은 모두 제거해.
            2. 핵심 주제 3가지를 글머리기호(•)를 써서 요약해.
            3. 문장은 간결하고 명확하게 끝맺어. (예: ~함, ~임)
            4. 전체 길이는 5~7줄 이내로.
            """
            response = model.generate_content(prompt)
            summary_text = response.text.strip()
            
            print("완료! -> 노션 저장...", end=" ")
            
            # 노션 전송 (원본 텍스트도 같이 보냄)
            page_title = f"[{today_str}] {chat_title}"
            send_to_notion(page_title, chat_title, summary_text, messages_text, today_str)
            
            full_report += f"### 📢 {chat_title}\n{summary_text}\n\n---\n\n"
            has_update = True
            
        except Exception as e:
            print(f"에러: {e}")

    # 텔레그램 전송
    if has_update:
        try:
            if len(full_report) > 4000:
                await client.send_message('me', full_report[:4000] + "\n...(생략)")
            else:
                await client.send_message('me', full_report)
            print("📬 텔레그램 전송 완료!")
        except: pass

    await client.disconnect()

    # 깃허브 저장
    if has_update:
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(full_report)
        os.system("git config --global user.email 'bot@github.com'")
        os.system("git config --global user.name 'NewsBot'")
        os.system("git add README.md")
        os.system("git commit -m 'Update Report'")
        os.system("git push")

if __name__ == '__main__':
    asyncio.run(main())
