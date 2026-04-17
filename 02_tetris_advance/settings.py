# settings.py — 전체 상수 정의 (매직 넘버 0)

# --- 화면 ---
SCREEN_WIDTH = 500
SCREEN_HEIGHT = 700
FPS = 60

# --- 보드 ---
BOARD_COLS = 10
BOARD_ROWS = 20
CELL_SIZE = 30

# --- 보드 위치 (화면 내 오프셋) ---
BOARD_OFFSET_X = 80
BOARD_OFFSET_Y = 50

# --- 색상 (R, G, B) ---
COLOR_BG = (15, 15, 25)
COLOR_BOARD_BG = (25, 25, 40)
COLOR_GRID = (40, 40, 60)
COLOR_TEXT = (220, 220, 240)
COLOR_TEXT_DIM = (120, 120, 150)
COLOR_HIGHLIGHT = (255, 220, 50)
COLOR_GHOST = (60, 60, 80)
COLOR_BORDER = (70, 70, 100)
COLOR_PANEL_BG = (20, 20, 35)

# 테트로미노 색상 (인덱스 0=빈칸)
PIECE_COLORS = [
    (0,   0,   0),    # 0: 빈칸
    (0,   240, 240),  # 1: I — 시안
    (240, 160, 0),    # 2: O — 오렌지 (노란색)
    (160, 0,   240),  # 3: T — 보라
    (0,   240, 0),    # 4: S — 초록
    (240, 0,   0),    # 5: Z — 빨강
    (0,   0,   240),  # 6: J — 파랑
    (240, 120, 0),    # 7: L — 주황
]

GHOST_ALPHA = 80  # 고스트 투명도 (0-255)

# --- 점수 ---
SCORE_TABLE = {1: 100, 2: 300, 3: 500, 4: 800}  # 줄 수 → 점수
SOFT_DROP_SCORE = 1   # 소프트드롭 1칸당
HARD_DROP_SCORE = 2   # 하드드롭 1칸당

# --- 레벨 ---
LINES_PER_LEVEL = 10  # 레벨업에 필요한 줄 수
MAX_LEVEL = 15

# --- 낙하 속도 (ms / 1칸) ---
# 레벨 1 = 800ms, 레벨 MAX = ~80ms
def fall_delay(level: int) -> int:
    return max(80, 800 - (level - 1) * 50)

# --- DAS (Delayed Auto Shift) ---
DAS_DELAY = 170   # ms: 키 누른 후 연속이동 시작까지 대기
DAS_INTERVAL = 50 # ms: 연속이동 간격

# --- 잠금 지연 ---
LOCK_DELAY = 500  # ms: 바닥 닿은 후 고정까지 대기

# --- 파일 경로 ---
HIGHSCORE_FILE = "highscore.txt"

# --- 폰트 크기 ---
FONT_SIZE_LARGE = 48
FONT_SIZE_MEDIUM = 28
FONT_SIZE_SMALL = 18

# --- 게임 상태 ---
STATE_MENU = "menu"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_GAMEOVER = "gameover"
