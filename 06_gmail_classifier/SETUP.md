# Gmail 이메일 분류기 설정 가이드

## 1. 패키지 설치

```bash
pip install -r requirements.txt
```

## 2. Google Cloud Console 설정 (최초 1회)

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 (또는 기존 프로젝트 선택)
3. **API 및 서비스 > 라이브러리** 에서 **Gmail API** 활성화
4. **API 및 서비스 > 사용자 인증 정보** 클릭
5. **사용자 인증 정보 만들기 > OAuth 2.0 클라이언트 ID** 선택
6. 애플리케이션 유형: **데스크톱 앱**
7. 생성 후 **JSON 다운로드** → 파일명을 `credentials.json`으로 변경
8. `credentials.json`을 `06_gmail_classifier/` 폴더에 저장

> 처음 실행 시 브라우저가 열리며 Google 계정 로그인 및 권한 허용 요청이 나타납니다.  
> 허용하면 `token.json`이 자동 생성되어 이후에는 로그인 불필요.

## 3. Anthropic API 키 설정

```bash
# 환경 변수로 설정
export ANTHROPIC_API_KEY="your-api-key"

# 또는 Windows
set ANTHROPIC_API_KEY=your-api-key
```

## 4. Slack 알림 설정 (선택)

1. [Slack API](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. **Incoming Webhooks** 활성화 → **Add New Webhook to Workspace**
3. 알림 받을 채널 선택 후 Webhook URL 복사
4. `.env` 파일에 추가:

```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
```

> `.env`가 없으면 Streamlit 앱 사이드바의 Webhook URL 입력란에 직접 붙여넣어도 됩니다.

## 5. 실행

```bash
cd 06_gmail_classifier
python gmail_classifier.py
```

## 분류 카테고리

| 카테고리 | 설명 |
|---------|------|
| 업무/비즈니스 | 업무 관련, 미팅 초대, 프로젝트 이메일 |
| 뉴스레터/마케팅 | 구독 뉴스레터, 마케팅 이메일 |
| 금융/결제 | 결제 확인, 청구서, 은행 알림 |
| 소셜/알림 | SNS 알림, 앱 알림 |
| 개인 | 지인으로부터의 개인 이메일 |
| 스팸/광고 | 광고성 이메일 |
| 기타 | 위 카테고리에 해당하지 않는 이메일 |

## 가져올 이메일 수 조정

`gmail_classifier.py` 하단의 `main()` 함수에서 변경:

```python
max_results = 30  # 원하는 숫자로 변경 (최대 500)
```
