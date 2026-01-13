import os
import asyncio
import requests
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.genai as genai # 최신 라이브러리 권장이나 기존 호환 유지
import google.generativeai as genai_old
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

# 🎯 타겟 채팅방 키워드
TARGET_CHATS = [
    '주식', '뉴스', '부동산', '창고', '리서치', '투자', 
    '여의도', '렙', 'research', '부자', '데이터', '공부방', 
    '고수', '인사이트', '탐방', '지식', 'IR', '증권'
]

# 제미나이 설정 (컨텍스트 윈도우가 큰 2.0 Flash 사용 필수)
genai_old.configure(api_key=GEMINI_KEY)
model = genai_old.GenerativeModel('gemini-2.0-flash')

# --- [기능] 노션 통합 리포트 전송 ---
def send_to_notion(title, content, summary_blocks, date_str):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    # 노션 본문 블록 조립
    children = []
    
    # 1. 인트로
    children.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"text": {"content": "💡 오늘 텔레그램 채널들에서 가장 화제가 된 이슈들을 통합 분석했습니다."}}],
            "icon": {"emoji": "🕵️‍♂️"},
            "color": "gray_background"
        }
    })

    # 2. 본문 (AI가 생성한 분석 내용) - 단락별로 쪼개서 넣기
    # (Notion 블록 길이 제한 때문에 2000자 단위로 자르는 로직이 필요할 수 있으나, 일단 단순화)
    children.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"text": {"content": content[:2000]}}]}
    })

    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "제목": {"title": [{"text": {"content": title}}]},
            "방이름": {"select": {"name": "통합인사이트"}}, # 카테고리
            "날짜": {"date": {"start": date_str}},
            "요약": {"rich_text": [{"text": {"content": "텔레그램 통합 심층 분석 리포트"}}]} 
        },
        "children": children
    }

    try:
        requests.post(url, headers=headers, json=payload)
        print("   ✅ 노션 저장 성공!")
    except Exception as e:
        print(f"   ❌ 노션 에러: {e}")

# --- [메인] ---
async def main():
    print("🚀 텔레그램 통합 분석 봇 가동...")
    
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
    await client.connect()

    korea_now = datetime.utcnow() + timedelta(hours=9)
    today_str = korea_now.strftime("%Y-%m-%d")
    # 최근 24시간 데이터 수집
    time_limit = korea_now - timedelta(hours=24)

    # 1️⃣ 데이터 수집 단계 (모든 방 털기)
    all_conversations = ""
    collected_count = 0
    checked_channels = 0

    print("📥 채널 데이터 수집 중...")
    
    async for dialog in client.iter_dialogs():
        chat_title = dialog.name
        
        # 타겟 방 확인
        is_target = False
        for target in TARGET_CHATS:
            if target in chat_title:
                is_target = True
                break
        if not is_target: continue

        checked_channels += 1
        print(f"   Reading [{chat_title}]...", end=" ")
        
        msgs_in_channel = ""
        msg_count = 0
        
        try:
            # 방 하나당 최신 30개만 (너무 옛날 대화는 노이즈)
            async for msg in client.iter_messages(dialog, limit=30):
                if msg.date.replace(tzinfo=None) < time_limit.replace(tzinfo=None): break
                
                # 너무 짧은 잡담 제거, 링크만 있는 것 제거
                if msg.text and len(msg.text) > 30: 
                    # [채널명] 내용 형식으로 기록하여 출처 구분
                    msgs_in_channel += f"Source: {chat_title} | Content: {msg.text}\n"
                    msg_count += 1
        except:
            print("x (권한 없음)")
            continue
            
        if msg_count > 0:
            all_conversations += msgs_in_channel + "\n"
            collected_count += msg_count
            print(f"{msg_count}개 수집 완료")
        else:
            print("새 글 없음")

    print(f"\n📚 총 {checked_channels}개 채널에서 {collected_count}개 메시지 수집 완료.")

    if collected_count == 0:
        print("💤 분석할 데이터가 없습니다.")
        await client.disconnect()
        return

    # 2️⃣ 통합 심층 분석 단계 (AI에게 넘기기)
    print("\n🧠 AI 심층 분석 시작 (시간이 좀 걸립니다)...")
    
    prompt = f"""
    당신은 수석 투자 전략가입니다. 
    아래 텍스트는 여러 주식/경제 텔레그램 채널에서 수집한 지난 24시간의 대화 내용입니다.
    
    [요청 사항]
    이 방대한 데이터 속에서 '가장 중요한 핵심 테마(Key Themes)' 5가지를 도출하여 심층 리포트를 작성하십시오.
    단순 요약이 아니라, 여러 채널에서 교차 언급된 내용, 루머, 팩트, 시장 반응을 종합하여 인사이트를 제공해야 합니다.

    [분석 규칙]
    1. **중복 제거**: 같은 뉴스가 여러 방에 나왔다면 하나로 합치고, 얼마나 화제가 되었는지 언급할 것.
    2. **구조적 작성**:
       - **테마 1: [제목]**
         - 🔍 **현황**: 무슨 일이 있었는가? (팩트 위주)
         - 🗣️ **반응**: 시장 참여자들의 해석이나 우려 사항은? (루머, 심리)
         - 💡 **인사이트**: 투자자 입장에서 어떻게 해석해야 하는가?
       - (테마 2... 테마 5까지 반복)
    3. **잡담 배제**: "안녕하세요", "감사합니다" 같은 내용은 철저히 무시하십시오.
    4. **어조**: 전문적이고 객관적인 '보고서' 말투를 사용하십시오.

    [데이터]
    {all_conversations[:50000]} 
    """
    # 데이터가 너무 많으면 50,000자로 자름 (Gemini Flash는 더 많이도 가능하지만 안전하게)

    try:
        response = model.generate_content(prompt)
        analysis_result = response.text
        
        print("✅ 분석 완료!")
        
        # 3️⃣ 결과 전송 (텔레그램 + 노션)
        
        # (1) 텔레그램으로 나에게 보내기
        report_header = f"📊 **{today_str} 통합 마켓 인사이트**\n({checked_channels}개 채널 {collected_count}개 메시지 분석)\n\n"
        full_msg = report_header + analysis_result
        
        # 텔레그램은 4096자 제한이 있으므로 나눠서 보내기
        chunks = [full_msg[i:i+4000] for i in range(0, len(full_msg), 4000)]
        for chunk in chunks:
            await client.send_message('me', chunk)
        print("📬 텔레그램 전송 완료")

        # (2) 노션 저장
        send_to_notion(f"📊 [{today_str}] 마켓 통합 인사이트", analysis_result, [], today_str)

    except Exception as e:
        print(f"❌ 분석/전송 중 에러 발생: {e}")

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
