import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
from datetime import datetime, timedelta

# 환경변수 로딩
API_ID = os.environ["TG_API_ID"]
API_HASH = os.environ["TG_API_HASH"]
SESSION_STR = os.environ["TG_SESSION"]
GEMINI_KEY = os.environ["GEMINI_KEY"]

# 🎯 타겟 채팅방
TARGET_CHATS = [
    '주식', '뉴스', '부동산', '창고', '리서치', '투자', 
    '여의도', '렙', 'research', '부자', '데이터', '공부방', 
    '고수', '인사이트', '탐방', '지식', 'IR', '증권'
]

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

async def main():
    print("🚀 텔레그램 요약 봇 가동 (전송+저장 모드)...")
    
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
    await client.connect()

    # 한국 시간 설정
    korea_now = datetime.utcnow() + timedelta(hours=9)
    time_limit = korea_now - timedelta(hours=24)

    # 보고서 헤더
    summary_report = f"# 📅 {korea_now.strftime('%Y-%m-%d')} 텔레그램 요약 브리핑\n"
    summary_report += f"> 업데이트: {korea_now.strftime('%H:%M:%S')}\n\n"
    
    has_update = False

    async for dialog in client.iter_dialogs():
        chat_title = dialog.name
        
        # 타겟 방인지 확인
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
                if msg.text and len(msg.text) > 20: # 너무 짧은 건 패스
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
            prompt = f"""
            텔레그램 대화를 핵심만 3줄로 요약해.
            [방] {chat_title}
            [내용] {messages_text[:5000]}
            """
            response = model.generate_content(prompt)
            
            # 결과 텍스트 누적
            summary_report += f"### 📢 {chat_title}\n{response.text}\n\n---\n\n"
            has_update = True
            print("완료! ✅")
        except Exception as e:
            print(f"AI 에러: {e}")

    # ✅ 1. 나에게 텔레그램 보내기 (폰으로 알림!)
    if has_update:
        try:
            # 내용이 너무 길면 잘라서 보내기 (텔레그램 제한)
            if len(summary_report) > 4000:
                await client.send_message('me', summary_report[:4000] + "\n\n(내용이 길어서 잘렸습니다. 깃허브에서 확인하세요!)")
            else:
                await client.send_message('me', summary_report)
            print("\n📬 텔레그램 전송 완료!")
        except Exception as e:
            print(f"\n❌ 전송 실패: {e}")

    await client.disconnect()

    # ✅ 2. 깃허브 웹사이트(README) 업데이트
    if has_update:
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(summary_report)
        
        os.system("git config --global user.email 'bot@github.com'")
        os.system("git config --global user.name 'NewsBot'")
        os.system("git add README.md")
        os.system("git commit -m 'Update Report'")
        os.system("git push")
        print("🌐 깃허브 업데이트 완료!")
    else:
        print("\n💤 요약할 새로운 내용이 없습니다.")

if __name__ == '__main__':
    asyncio.run(main())
