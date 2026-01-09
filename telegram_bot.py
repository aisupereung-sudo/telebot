import os
import asyncio
import sys # 에러 출력을 위해 추가
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
from datetime import datetime, timedelta

print("🔍 [진단 시작] 환경변수 점검 중...")

# 1. 환경변수(Secrets) 체크 (여기서 에러나면 Secrets 오타입니다)
try:
    API_ID = os.environ["TG_API_ID"]
    API_HASH = os.environ["TG_API_HASH"]
    SESSION_STR = os.environ["TG_SESSION"]
    GEMINI_KEY = os.environ["GEMINI_KEY"]
    print("✅ 모든 환경변수(키) 확인 완료!")
except KeyError as e:
    print(f"❌ [치명적 에러] 환경변수가 없습니다: {e}")
    print("👉 깃허브 Settings > Secrets 에 가서 이름이 정확한지 확인하세요!")
    sys.exit(1)

# 타겟 채팅방
TARGET_CHATS = [
    '주식', '뉴스', '부동산', '창고', '리서치', '투자', 
    '여의도', '렙', 'research', '부자', '데이터', '공부방', 
    '고수', '인사이트', '탐방', '지식', 'IR', '증권'
]

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

async def main():
    print("🚀 [텔레그램 접속] 서버 연결 시도 중...")
    
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
    
    try:
        await client.connect()
    except Exception as e:
        print(f"❌ [접속 실패] 마스터 키(Session String) 문제일 가능성이 높습니다.\n에러내용: {e}")
        return

    if not await client.is_user_authorized():
        print("❌ [로그인 실패] 세션이 만료되었습니다. 마스터 키를 다시 발급받으세요.")
        return
    
    print("✅ 텔레그램 로그인 성공!")

    # 한국 시간
    korea_now = datetime.utcnow() + timedelta(hours=9)
    time_limit = korea_now - timedelta(hours=24)

    summary_report = f"# 📅 {korea_now.strftime('%Y-%m-%d')} 텔레그램 요약 브리핑\n"
    summary_report += f"> 업데이트 시간: {korea_now.strftime('%H:%M:%S')}\n\n"
    
    has_update = False

    print("📡 대화방 스캔 시작...")
    
    try:
        async for dialog in client.iter_dialogs():
            chat_title = dialog.name
            
            is_target = False
            for target in TARGET_CHATS:
                if target in chat_title:
                    is_target = True
                    break
            
            if not is_target: continue

            print(f"   🔎 발견: [{chat_title}] -> 메시지 읽는 중...", end=" ")
            
            messages_text = ""
            count = 0
            
            # 메시지 읽기 권한 에러 방지용 try-except
            try:
                async for msg in client.iter_messages(dialog, limit=50):
                    if msg.date.replace(tzinfo=None) < time_limit.replace(tzinfo=None): break
                    if msg.text and len(msg.text) > 10:
                        messages_text += f"- {msg.text}\n"
                        count += 1
            except Exception as e:
                print(f"패스 (읽기 권한 없음: {e})")
                continue
            
            if count == 0:
                print("패스 (새 글 없음)")
                continue
                
            print(f"{count}개 요약 중...", end=" ")

            try:
                prompt = f"""
                텔레그램 대화 내용을 핵심만 3줄로 요약해.
                [채팅방] {chat_title}
                [내용] {messages_text[:8000]}
                """
                response = model.generate_content(prompt)
                summary_report += f"### 📢 {chat_title}\n{response.text}\n\n---\n\n"
                has_update = True
                print("완료! ✅")
            except Exception as e:
                print(f"AI 에러: {e}")

    except Exception as e:
        print(f"❌ [스캔 중 에러] {e}")

    await client.disconnect()

    # 파일 저장 및 업로드
    if has_update:
        print("💾 결과 파일(README.md) 저장 중...")
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(summary_report)
        
        print("🌐 깃허브에 업로드(Push) 시도 중...")
        # os.system은 에러를 숨기기 때문에 subprocess로 변경하거나 로직 보완
        # 간단하게 에러 확인을 위해 try-catch 대신 결과 코드 확인
        
        exit_code = os.system("git config --global user.email 'bot@github.com'")
        os.system("git config --global user.name 'NewsBot'")
        os.system("git add README.md")
        os.system("git commit -m 'Update Telegram Report'")
        push_code = os.system("git push")
        
        if push_code != 0:
            print("❌ [업로드 실패] 깃허브 '쓰기 권한(Write permissions)'이 없는 것 같습니다.")
            print("👉 Settings > Actions > General > Workflow permissions 에서 'Read and write permissions'를 체크하세요!")
            sys.exit(1)
        
        print("🎉 모든 작업 완료!")
    else:
        print("💤 요약할 내용이 없어서 종료합니다.")

if __name__ == '__main__':
    asyncio.run(main())
