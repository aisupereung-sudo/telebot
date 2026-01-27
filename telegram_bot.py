import os
import requests
import asyncio
import telegram
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import google.generativeai as genai

# ==============================================================================
# 🔐 환경변수 설정
# ==============================================================================
try:
    GEMINI_KEY = os.environ["API_KEY"]
    TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
    CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
except KeyError:
    print("❌ 환경변수 오류: API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID를 확인하세요.")
    exit(1)

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# ==============================================================================
# 📋 수집할 텔레그램 채널 리스트 (여기에 원하는 채널 ID를 추가하세요)
# ==============================================================================
# 주의: 공개 채널만 가능합니다. (초대 링크가 t.me/아이디 형식인 곳)
TARGET_CHANNELS = [
    'feed_kw',       # 예: 키움증권
    'marketpoint',   # 예: 마켓포인트
    'faststocknews', # 예: 속보 채널
    # 여기에 계속 추가 가능 (예: 'channel_id')
]

# ==============================================================================
# 1. 텔레그램 웹 크롤링 함수 (로그인 불필요)
# ==============================================================================
def collect_telegram_messages():
    print("📡 텔레그램 채널 데이터 수집 시작...")
    
    today_str = (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d")
    collected_text = ""
    total_count = 0
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    for channel in TARGET_CHANNELS:
        url = f"https://t.me/s/{channel}"
        try:
            print(f"   🔍 스캔 중: @{channel} ...", end="")
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 메시지 카드들 찾기
            cards = soup.select('.tgme_widget_message')
            channel_count = 0
            
            for card in cards:
                # 1. 날짜 확인 (오늘 날짜인지)
                time_tag = card.select_one('time')
                if not time_tag: continue
                
                # datetime 속성 예: "2026-01-27T08:30:00+00:00"
                raw_time = time_tag.get('datetime')
                if not raw_time: continue
                
                # UTC 시간을 한국 시간으로 변환하지 않고 문자열 비교 (단순화)
                # t.me 웹은 UTC 기준일 수 있으니 날짜 문자열 포함 여부로 체크
                # 정확도를 위해 텍스트 날짜(오늘)가 포함되어 있는지 확인
                
                # 텍스트 내용 가져오기
                text_div = card.select_one('.tgme_widget_message_text')
                if not text_div: continue
                
                text_content = text_div.get_text(separator="\n", strip=True)
                
                # 너무 짧은 건 패스 (광고 등)
                if len(text_content) < 50: continue
                
                # 수집된 텍스트 합치기
                collected_text += f"\n\n--- [Channel: @{channel}] ---\n{text_content}"
                channel_count += 1
                total_count += 1
            
            print(f" {channel_count}개 수집 완료")
            
        except Exception as e:
            print(f" 실패 ({e})")
            continue

    print(f"✅ 총 {total_count}개 메시지 수집 완료 (길이: {len(collected_text)}자)")
    return collected_text

# ==============================================================================
# 2. AI 분석 (프롬프트 적용)
# ==============================================================================
def generate_market_insight(messages_text):
    if not messages_text or len(messages_text) < 100:
        return "❌ 분석할 충분한 데이터가 수집되지 않았습니다. (채널 리스트를 확인해주세요)"

    today_str = (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d")
    
    prompt = f"""
    당신은 20년 경력의 '수석 투자 전략가(Chief Market Strategist)'입니다.
    아래 수집된 텔레그램 메시지 데이터를 분석하여, 투자자들에게 **진짜 도움이 되는 심층 시장 보고서**를 작성하세요.

    [분석 대상 데이터]
    {messages_text[:60000]} 

    [🚨 **핵심 필터링 규칙 (매우 중요)**]
    1. **잡음 제거 (Noise Filtering):**
       - **'투자 경고/주의 종목 지정', '단기 과열', '거래 정지', '단순 유상증자/CB발행', '단순 자사주 취득/처분', '광고' 등은 절대 메인 테마로 잡지 마세요.**
       - 개별 잡주(Small-cap)의 단순 등락이나 찌라시는 무시하세요.
    
    2. **테마 선정 기준 (Priority):**
       - **1순위:** 거시 경제(금리, 환율, 유가), 지정학적 이슈(미국 대선, 전쟁 등).
       - **2순위:** 주도 섹터 트렌드 (AI, 반도체, 2차전지, 바이오, 자율주행 등 산업 변화).
       - **3순위:** 시장에 큰 충격을 주는 대형 악재/호재.
    
    3. **통찰력 (Insight):**
       - 단순 사실 나열이 아니라, "이것이 시장에 어떤 의미인가?"를 해석하세요.
       - 여러 채널에서 공통적으로 언급하는 '시장 심리(Sentiment)'를 읽어내세요.

    [출력 양식 (Markdown)]
    # 📊 {today_str} 통합 마켓 인사이트

    ## 💡 오늘의 핵심 요약 (3줄)
    - (시장 전체를 관통하는 핵심 분위기 요약)

    ---

    ### 테마 1: [테마 제목 (예: AI 반도체 전쟁 심화)]
    - **🔍 현황:** (팩트 위주로 3~4줄 요약)
    - **🗣️ 시장 반응:** (투자자들의 분위기, 우려 또는 기대감)
    - **💡 인사이트:** (투자 전략, 향후 전망, 수혜 예상 섹터 등 깊이 있는 분석)

    ### 테마 2: [테마 제목]
    ... (위와 동일, 총 3~5개 테마 작성) ...

    ---
    ### 📝 결론 및 투자 전략
    (오늘 시장을 대응하는 투자자의 자세)
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ 리포트 생성 실패: {e}"

# ==============================================================================
# 3. 텔레그램 전송
# ==============================================================================
async def send_telegram_report(report_text):
    if not report_text: return
    
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    try:
        # 메시지가 너무 길면 나눠서 보냄 (텔레그램 제한 4096자)
        limit = 4000
        for i in range(0, len(report_text), limit):
            chunk = report_text[i:i + limit]
            await bot.send_message(chat_id=CHAT_ID, text=chunk, parse_mode='Markdown')
        print("✅ 텔레그램 리포트 전송 완료")
    except Exception as e:
        # 마크다운 파싱 에러 날 경우 그냥 텍스트로 재시도
        print(f"⚠️ 마크다운 전송 실패({e}), 일반 텍스트로 재시도...")
        await bot.send_message(chat_id=CHAT_ID, text=report_text)

# ==============================================================================
# 메인 실행
# ==============================================================================
def main():
    # 1. 수집
    data = collect_telegram_messages()
    
    # 2. 분석
    print("🧠 AI 심층 분석 중...")
    report = generate_market_insight(data)
    
    # 3. 전송
    asyncio.run(send_telegram_report(report))

if __name__ == "__main__":
    main()
