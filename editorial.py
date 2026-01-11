import os
import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import google.generativeai as genai

# ==============================================================================
# 🔐 환경변수 (기존과 동일하게 사용)
# ==============================================================================
try:
    API_KEY = os.environ["GEMINI_KEY"]    # 제미나이 키
    NOTION_KEY = os.environ["NOTION_KEY"] # 노션 시크릿 키
    NOTION_DB_ID = os.environ["NOTION_DB_ID"] # 노션 DB ID
except KeyError:
    # 로컬 테스트용 (삭제 가능)
    API_KEY = "내_제미나이_키"
    NOTION_KEY = "내_노션_키"
    NOTION_DB_ID = "내_DB_ID"

# 제미나이 설정
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# ==============================================================================
# 1. 노션 전송 함수
# ==============================================================================
def send_to_notion(title, press, summary, link, date_str):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    safe_summary = summary[:1900] # 길이 제한

    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "제목": {"title": [{"text": {"content": title}}]},
            "방이름": {"select": {"name": "사설/칼럼"}}, # 카테고리 고정
            "날짜": {"date": {"start": date_str}},
            "요약": {"rich_text": [{"text": {"content": safe_summary[:100] + "..."}}]},
            # 링크 속성이 노션 DB에 없다면 아래 줄은 지우거나 에러날 수 있음
            # "링크": {"url": link} 
        },
        "children": [
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{"text": {"content": f"📰 {press} 사설 요약"}}],
                    "icon": {"emoji": "✒️"},
                    "color": "gray_background"
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": safe_summary}}]}
            },
            {
                "object": "block",
                "type": "bookmark",
                "bookmark": {"url": link}
            }
        ]
    }
    
    try:
        requests.post(url, headers=headers, json=payload)
        print("   ✅ 노션 저장 성공!")
    except Exception as e:
        print(f"   ❌ 노션 실패: {e}")

# ==============================================================================
# 2. 사설 본문 스크래핑 & 요약
# ==============================================================================
def process_article(url, title, press, date_str):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 네이버 뉴스 본문 위치 찾기
        content_area = soup.select_one('#dic_area') or soup.select_one('#newsct_article')
        
        if not content_area:
            print("   패스 (본문 못 찾음)")
            return

        body_text = content_area.get_text(strip=True)
        if len(body_text) < 200: return # 너무 짧으면 패스

        # AI 요약
        print(f"   🤖 AI 요약 중...", end=" ")
        prompt = f"""
        너는 베테랑 논설위원이야. 아래 사설을 읽고 핵심 논지와 주장을 3줄로 요약해.
        
        [제목] {title}
        [언론사] {press}
        [본문] {body_text[:5000]}
        
        [형식]
        1. (핵심 이슈)
        2. (논조/주장)
        3. (시사점)
        """
        response = model.generate_content(prompt)
        summary = response.text
        
        # 노션 전송
        send_to_notion(title, press, summary, url, date_str)

    except Exception as e:
        print(f"에러: {e}")

# ==============================================================================
# 3. 메인 로직 (네이버 오피니언 홈 긁기)
# ==============================================================================
def main():
    print("🔥 [네이버 사설] 수집 시작...")
    
    # 네이버 오피니언 > 사설 리스트 (PC 버전 구형 페이지가 긁기 좋음)
    # sid1=110 (오피니언)
    target_url = "https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=110"
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(target_url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    articles = soup.select('.list_body.newsflash_body li')
    
    today_str = (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d")
    count = 0
    
    for art in articles:
        if count >= 5: break # 하루 5개만 (너무 많으면 읽기 힘드니까)
        
        try:
            link_tag = art.select_one('a')
            if not link_tag: continue
            
            link = link_tag['href']
            title = link_tag.get_text(strip=True)
            
            # 언론사 정보 (span class="writing")
            press_tag = art.select_one('.writing')
            press = press_tag.get_text(strip=True) if press_tag else "Unknown"
            
            # 🎯 필터링: '사설' 이나 '칼럼' 이라는 단어가 있거나, 주요 경제지인 경우
            keywords = ['사설', '칼럼', '시론', '데스크']
            major_press = ['매일경제', '한국경제', '조선일보', '중앙일보']
            
            is_target = False
            # 1. 제목에 사설/칼럼 포함
            if any(k in title for k in keywords): is_target = True
            # 2. 또는 주요 언론사
            if press in major_press: is_target = True
            
            if not is_target: continue

            print(f"🔍 [{press}] {title}")
            process_article(link, title, press, today_str)
            count += 1
            
        except Exception as e:
            continue

    print(f"\n🎉 총 {count}개 사설 요약 완료!")

if __name__ == "__main__":
    main()
