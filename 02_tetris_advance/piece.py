# piece.py — 테트로미노 정의 + SRS 회전

from __future__ import annotations
import random
from typing import List, Tuple

# --- 테트로미노 형태 정의 (4x4 그리드, 0=빈, 1=블록) ---
# 각 피스는 4가지 회전 상태를 갖는다
TETROMINOES = {
    "I": [
        [(0,0),(1,0),(2,0),(3,0)],
        [(2,0),(2,1),(2,2),(2,3)],
        [(0,2),(1,2),(2,2),(3,2)],
        [(1,0),(1,1),(1,2),(1,3)],
    ],
    "O": [
        [(1,0),(2,0),(1,1),(2,1)],
        [(1,0),(2,0),(1,1),(2,1)],
        [(1,0),(2,0),(1,1),(2,1)],
        [(1,0),(2,0),(1,1),(2,1)],
    ],
    "T": [
        [(1,0),(0,1),(1,1),(2,1)],
        [(1,0),(1,1),(2,1),(1,2)],
        [(0,1),(1,1),(2,1),(1,2)],
        [(1,0),(0,1),(1,1),(1,2)],
    ],
    "S": [
        [(1,0),(2,0),(0,1),(1,1)],
        [(1,0),(1,1),(2,1),(2,2)],
        [(1,1),(2,1),(0,2),(1,2)],
        [(0,0),(0,1),(1,1),(1,2)],
    ],
    "Z": [
        [(0,0),(1,0),(1,1),(2,1)],
        [(2,0),(1,1),(2,1),(1,2)],
        [(0,1),(1,1),(1,2),(2,2)],
        [(1,0),(0,1),(1,1),(0,2)],
    ],
    "J": [
        [(0,0),(0,1),(1,1),(2,1)],
        [(1,0),(2,0),(1,1),(1,2)],
        [(0,1),(1,1),(2,1),(2,2)],
        [(1,0),(1,1),(0,2),(1,2)],
    ],
    "L": [
        [(2,0),(0,1),(1,1),(2,1)],
        [(1,0),(1,1),(1,2),(2,2)],
        [(0,1),(1,1),(2,1),(0,2)],
        [(0,0),(1,0),(1,1),(1,2)],
    ],
}

PIECE_NAMES = list(TETROMINOES.keys())

# 피스 이름 → 색상 인덱스
PIECE_COLOR_INDEX = {
    "I": 1, "O": 2, "T": 3,
    "S": 4, "Z": 5, "J": 6, "L": 7,
}


class Piece:
    """단일 테트로미노 인스턴스."""

    def __init__(self, name: str, col: int = 3, row: int = 0):
        self.name = name
        self.color_idx = PIECE_COLOR_INDEX[name]
        self.rotation = 0
        self.col = col  # 보드 내 좌상단 기준 열
        self.row = row  # 보드 내 좌상단 기준 행

    # --- 현재 회전 상태의 셀 좌표 (보드 절대 좌표) ---
    def cells(self) -> List[Tuple[int, int]]:
        """[(board_col, board_row), ...] 반환."""
        shape = TETROMINOES[self.name][self.rotation]
        return [(self.col + dx, self.row + dy) for dx, dy in shape]

    # --- 회전 (불변 — 새 rotation 인덱스만 반환) ---
    def rotated_cells(self, direction: int = 1) -> List[Tuple[int, int]]:
        """direction: +1=시계, -1=반시계. 실제 self.rotation은 변경하지 않는다."""
        new_rot = (self.rotation + direction) % 4
        shape = TETROMINOES[self.name][new_rot]
        return [(self.col + dx, self.row + dy) for dx, dy in shape]

    def rotate(self, direction: int = 1):
        self.rotation = (self.rotation + direction) % 4

    # --- 복사 ---
    def copy(self) -> "Piece":
        p = Piece(self.name, self.col, self.row)
        p.rotation = self.rotation
        return p


class PieceBag:
    """7-bag 랜덤 생성기: 7종을 한 세트로 섞어 순서 보장."""

    def __init__(self):
        self._bag: List[str] = []

    def _refill(self):
        bag = list(PIECE_NAMES)
        random.shuffle(bag)
        self._bag.extend(bag)

    def next(self) -> Piece:
        if len(self._bag) < 1:
            self._refill()
        name = self._bag.pop(0)
        # 스폰 위치: 열 3, 행 0
        return Piece(name, col=3, row=0)

    def peek(self, n: int = 1) -> List[str]:
        """다음 n개의 피스 이름을 미리 본다 (소비하지 않음)."""
        while len(self._bag) < n:
            self._refill()
        return [self._bag[i] for i in range(n)]
