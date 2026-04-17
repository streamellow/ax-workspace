# ax-workspace

AX (AI Experience) 학습 프로젝트 모음입니다.

## 프로젝트 구성

| 폴더 | 설명 |
|------|------|
| `01_tetris/` | Python 기본 테트리스 게임 |
| `02_tetris_advance/` | 테트리스 고급 버전 (모듈 분리, 테스트 포함) |
| `03_ax_curriculum_chatbot/` | AX 커리큘럼 챗봇 (OpenAI API 활용) |
| `Data/` | 참고 데이터 (PDF 등) |

## 환경 설정

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 환경변수 설정
cp .env.example .env
# .env 파일에 실제 API 키 입력
```
