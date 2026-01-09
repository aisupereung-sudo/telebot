import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
from datetime import datetime, timedelta

# 환경변수
API_ID = os.environ["TG_API_ID"]
API_HASH = os.environ["TG_API_HASH"]
SESSION_STR = os.environ["TG_SESSION"]
GEMINI_KEY = os.environ["GEMINI_KEY"]

# 🎯 타겟 채팅방 설정 (따옴표 수정 완료 + 보기 좋게 줄바꿈)
TARGET_CHATS = [
    '주식', '뉴스', '부동산', '창고', '리서치', '투자', 
    '여의도', '렙', 'research', '부자', '데이터', '공부방', 
    '고수', '인사이트', '탐방', '지식', 'IR', '증권'
] 

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

async def main():
    print("🚀 텔레그램 요약 봇 가동...")
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        print("❌ 로그인 실패! 세션 스트링을 확인하세요.")
        return

    # 한국 시간 기준
    korea_now = datetime.utcnow() + timedelta(hours=9)
    # 24시간 전 데이터부터 수집
    time_limit = korea_now - timedelta(hours=24)

    # 📝 웹사이트(README) 헤더
    summary_report = f"# 📅 {korea_now.strftime('%Y-%m-%d')} 텔레그램 요약 브리핑\n"
    summary_report += f"> 업데이트 시간: {korea_now.strftime('%H:%M:%S')}\n\n"
    
    has_update = False

    async for dialog in client.iter_dialogs():
        chat_title = dialog.name
        
        # 설정한 단어가 포함된 방인지 확인
        is_target = False
        for target in TARGET_CHATS:
            if target in chat_title:
                is_target = True
                break
        
        if not is_target: continue

        print(f"🔍 [{chat_title}] 수집 중...", end=" ")
        
        messages_text = ""
        count = 0
        # 메시지 수집 (최근 50개 or 24시간 이내)
        async for msg in client.iter_messages(dialog, limit=50):
            if msg.date.replace(tzinfo=None) < time_limit.replace(tzinfo=None): break
            if msg.text and len(msg.text) > 10: # 너무 짧은 인사말은 제외
                messages_text += f"- {msg.text}\n"
                count += 1
        
        if count == 0:
            print("패스 (새 글 없음)")
            continue
            
        print(f"{count}개 요약 중...", end=" ")

        try:
            prompt = f"""
            너는 유능한 정보 비서야. 아래 텔레그램 대화 내용을 핵심만 요약해.
            
            [채팅방] {chat_title}
            [내용]
            {messages_text[:8000]}
            
            [지시사항]
            1. 잡담, 인사, 광고는 다 빼고 '영양가 있는 정보'만 남겨.
            2. 주식/투자/뉴스 관련 내용이면 종목명이나 핵심 이슈를 강조해.
            3. 내용은 3~5줄로 간결하게 요약해.
            
            [형식]
            ### 📢 {chat_title}
            - 핵심1
            - 핵심2
            """
            response = model.generate_content(prompt)
            summary = response.text
            
            summary_report += f"{summary}\n\n---\n\n"
            has_update = True
            print("완료! ✅")
        except Exception as e:
            print(f"에러: {e}")

    await client.disconnect()

    # ⭐️ README.md 업데이트 및 깃허브 업로드
    if has_update:
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(summary_report)
        
        os.system("git config --global user.email 'bot@github.com'")
        os.system("git config --global user.name 'NewsBot'")
        os.system("git add README.md")
        os.system("git commit -m 'Update Telegram Report'")
        os.system("git push")
        
        print("\n🌐 깃허브 메인 화면 업데이트 완료!")
    else:
        print("\n💤 업데이트할 내용이 없습니다.")

if __name__ == '__main__':
    asyncio.run(main())
