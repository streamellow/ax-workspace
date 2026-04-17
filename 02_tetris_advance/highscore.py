# highscore.py — 최고점수 파일 I/O

import os
from settings import HIGHSCORE_FILE


def load_highscore() -> int:
    if not os.path.exists(HIGHSCORE_FILE):
        return 0
    try:
        with open(HIGHSCORE_FILE, "r") as f:
            return int(f.read().strip())
    except (ValueError, IOError):
        return 0


def save_highscore(score: int):
    try:
        with open(HIGHSCORE_FILE, "w") as f:
            f.write(str(score))
    except IOError:
        pass  # 저장 실패해도 게임은 계속
