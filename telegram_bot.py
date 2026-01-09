import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
from datetime import datetime, timedelta

# ==============================================================================
# 🔐 환경변수 로딩
# ==============================================================================
API_ID = os.environ["TG_API_ID"]
API_HASH = os.environ["TG_API_HASH"]
SESSION_STR = os.environ["TG_SESSION"]
GEMINI_KEY = os.environ["GEMINI_KEY"]

# ==============================================================================
# 🎯 [설정] 요약하고 싶은 방 이름 (정확히 입력하거나, 부분 포함도 가능)
# 예: ['사무실', '비트코인 정보방', '가족방'] 
# 비워두면(['']) 너무 많아서 에러날 수 있으니 꼭 지정하세요!
# ==============================================================================
TARGET_CHATS = ['주식', '뉴스', '부동산'] 

# 제미나이 설정
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.0-flash') # 속도 빠른 모델

async def main():
    print("🚀 텔레그램 요약 봇 가동...")
    
    # 텔레그램 접속
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        print("❌ 로그인 실패! 세션 스트링을 다시 발급받으세요.")
        return

    # 오늘 날짜 (한국 시간 기준 어제~오늘 대화 수집)
    korea_now = datetime.utcnow() + timedelta(hours=9)
    time_limit = korea_now - timedelta(hours=24) # 24시간 전까지

    summary_report = f"📅 **{korea_now.strftime('%Y-%m-%d')} 텔레그램 요약 브리핑**\n\n"
    has_update = False

    # 모든 대화방 목록 가져오기
    async for dialog in client.iter_dialogs():
        chat_title = dialog.name
        
        # 설정한 단어가 포함된 방만 골라내기
        is_target = False
        for target in TARGET_CHATS:
            if target in chat_title:
                is_target = True
                break
        
        if not is_target:
            continue

        print(f"🔍 [{chat_title}] 대화 수집 중...", end=" ")
        
        # 메시지 긁어오기 (최근 100개 or 24시간 이내)
        messages_text = ""
        count = 0
        async for msg in client.iter_messages(dialog, limit=100):
            if msg.date.replace(tzinfo=None) < time_limit.replace(tzinfo=None):
                break # 24시간 지났으면 스톱
            
            if msg.text:
                # 누가 말했는지보다 내용이 중요하므로 내용만 수집
                messages_text += f"- {msg.text}\n"
                count += 1
        
        if count == 0:
            print("새 글 없음 (패스)")
            continue
            
        print(f"{count}개 수집 완료! 요약 중...", end=" ")

        # 제미나이에게 요약 요청
        try:
            prompt = f"""
            너는 비서야. 아래 텔레그램 채팅방 대화 내용을 읽고 핵심 정보를 3줄로 요약해.
            잡담은 빼고 영양가 있는 정보(뉴스, 일정, 수치) 위주로 정리해.
            
            [채팅방 이름] {chat_title}
            [대화 내용]
            {messages_text[:10000]} 
            
            [형식]
            **[{chat_title}]**
            1. 핵심1
            2. 핵심2
            3. 핵심3
            """
            response = model.generate_content(prompt)
            summary = response.text
            
            summary_report += f"{summary}\n------------------\n"
            has_update = True
            print("완료! ✅")
            
        except Exception as e:
            print(f"에러: {e}")

    # 나에게(Saved Messages)로 결과 전송
    if has_update:
        # 메시지가 너무 길면 나눠서 보내기 (텔레그램 제한 4096자)
        if len(summary_report) > 4000:
            parts = [summary_report[i:i+4000] for i in range(0, len(summary_report), 4000)]
            for part in parts:
                await client.send_message('me', part)
        else:
            await client.send_message('me', summary_report)
        print("\n📬 요약본 전송 완료! (텔레그램 '저장한 메시지' 확인)")
    else:
        print("\n💤 요약할 새로운 대화가 없습니다.")

    await client.disconnect()

# 실행
if __name__ == '__main__':
    asyncio.run(main())
