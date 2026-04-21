import imaplib
import email
from email.header import decode_header
import os
from collections import defaultdict
from dotenv import load_dotenv
from openai import OpenAI

# .env 파일 로드 (현재 디렉토리의 .env 파일에 있는 환경변수 로드)
load_dotenv()

# --- 설정 (Settings) ---
# 구글 계정 설정: 구글 앱 비밀번호 발급 필요
EMAIL_ACCOUNT = "your_email@gmail.com"
EMAIL_PASSWORD = "your_app_password" # 16자리 앱 비밀번호 입력

# OpenAI 클라이언트 초기화 (.env의 OPENAI_API_KEY 자동 사용)
client = OpenAI()

def get_body(msg):
    """이메일 본문을 추출하는 헬퍼 함수"""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get('Content-Disposition'))
            # 첨부파일이 아닌 일반 텍스트만 추출
            if ctype == 'text/plain' and 'attachment' not in cdispo:
                try:
                    return part.get_payload(decode=True).decode()
                except:
                    pass
    else:
        try:
            return msg.get_payload(decode=True).decode()
        except:
            pass
    return ""

def fetch_emails(limit=10):
    """IMAP을 사용하여 최근 이메일을 가져옵니다."""
    try:
        # IMAP 서버 연결
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select("inbox")

        # 받은편지함의 모든 이메일 검색
        status, messages = mail.search(None, "ALL")
        email_ids = messages[0].split()
        
        # 최근 이메일 ID만 지정된 개수만큼 슬라이싱
        latest_email_ids = email_ids[-limit:]
        
        email_data = []

        for e_id in latest_email_ids:
            res, msg = mail.fetch(e_id, "(RFC822)")
            for response in msg:
                if isinstance(response, tuple):
                    msg = email.message_from_bytes(response[1])
                    
                    # 제목 디코딩
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8", "ignore")
                        
                    # 본문 추출
                    body = get_body(msg)
                    
                    email_data.append({
                        "subject": subject,
                        "body": body[:1000] # LLM 토큰 절약을 위해 서두 1000자만 추출
                    })

        mail.logout()
        return email_data

    except Exception as e:
        print(f"❌ 이메일 가져오기 실패: {e}")
        return []

def classify_and_summarize(emails):
    """OpenAI API를 사용하여 이메일을 분류하고 요약합니다."""
    if not emails:
        print("분석할 이메일이 없습니다.")
        return

    categories = defaultdict(list)
    
    print("🤖 AI 모델로 이메일 분석 중...\n")
    for mail in emails:
        prompt = f"""
        다음 이메일의 내용을 확인하고, 가장 적절한 카테고리로 분류한 후 주요 내용을 1~2줄로 요약해.
        
        [선택 가능한 카테고리]
        - 업무
        - 프로모션
        - 뉴스레터
        - 청구서
        - 소셜
        - 기타
        
        결과는 반드시 다음 형태 그대로 출력해 주세요:
        카테고리: [선택한 카테고리]
        요약: [요약 내용]
        
        ---
        이메일 제목: {mail['subject']}
        이메일 내용: {mail['body']}
        """
        
        try:
            # gpt-3.5-turbo 또는 gpt-4o-mini 모델을 사용하여 비용 효율적으로 분석
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 이메일을 분석하고 간결하게 요약해주는 똑똑한 비서입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            result = response.choices[0].message.content.strip().split('\n')
            
            category = "기타"
            summary = "요약 실패"
            
            # 파싱
            for line in result:
                if line.startswith("카테고리:"):
                    category = line.split(":", 1)[1].strip()
                elif line.startswith("요약:"):
                    summary = line.split(":", 1)[1].strip()
            
            categories[category].append({
                "subject": mail['subject'],
                "summary": summary
            })
            
        except Exception as e:
            print(f"[{mail['subject']}] 분석 실패: {e}")

    # 최종 결과 출력
    print("=" * 50)
    print("📧 이메일 분류 및 요약 리포트")
    print("=" * 50)
    
    for category, items in categories.items():
        print(f"\n📁 [{category}] - 총 {len(items)}건")
        for idx, item in enumerate(items, 1):
            print(f"  {idx}. 제목: {item['subject']}")
            print(f"     └ 요약: {item['summary']}")

if __name__ == "__main__":
    if EMAIL_ACCOUNT == "your_email@gmail.com":
        print("🚨 스크립트 실행 전 설정이 필요합니다!")
        print("1. 스크립트 파일 안의 EMAIL_ACCOUNT 와 EMAIL_PASSWORD 값을 수정해주세요.")
        print("2. Google 계정 설정에서 '앱 비밀번호' 16자리를 발급받아 EMAIL_PASSWORD에 넣어야 합니다.")
        print("   (구글 계정 관리 -> 보안 -> 2단계 인증 활성화 -> 앱 비밀번호)")
    else:
        print("📥 구글 이메일 접속 중...")
        emails = fetch_emails(limit=10) # 10개만 테스트
        if emails:
            classify_and_summarize(emails)
