# board.py — 보드 상태 + 충돌 + 줄 삭제

from __future__ import annotations
from typing import List, Tuple
from settings import BOARD_COLS, BOARD_ROWS


class Board:
    """
    20행 × 10열의 게임 보드.
    grid[row][col] = 색상 인덱스 (0=빈칸).
    """

    def __init__(self):
        self.grid: List[List[int]] = self._empty_grid()

    # --- 내부 ---
    def _empty_grid(self) -> List[List[int]]:
        return [[0] * BOARD_COLS for _ in range(BOARD_ROWS)]

    # --- 충돌 검사 ---
    def is_valid(self, cells: List[Tuple[int, int]]) -> bool:
        """주어진 셀 좌표 목록이 보드 내에 있고 빈칸인지 확인."""
        for col, row in cells:
            if col < 0 or col >= BOARD_COLS:
                return False
            if row >= BOARD_ROWS:
                return False
            if row >= 0 and self.grid[row][col] != 0:
                return False
        return True

    # --- 피스 고정 ---
    def lock(self, cells: List[Tuple[int, int]], color_idx: int):
        """피스를 보드에 고정한다."""
        for col, row in cells:
            if 0 <= row < BOARD_ROWS and 0 <= col < BOARD_COLS:
                self.grid[row][col] = color_idx

    # --- 줄 삭제 ---
    def clear_lines(self) -> int:
        """꽉 찬 줄을 삭제하고, 삭제된 줄 수를 반환한다."""
        full_rows = [r for r in range(BOARD_ROWS) if all(self.grid[r])]
        for r in full_rows:
            del self.grid[r]
            self.grid.insert(0, [0] * BOARD_COLS)
        return len(full_rows)

    # --- 게임오버 판정 ---
    def is_topped_out(self) -> bool:
        """행 0에 블록이 있으면 게임오버."""
        return any(self.grid[0][c] != 0 for c in range(BOARD_COLS))

    # --- 리셋 ---
    def reset(self):
        self.grid = self._empty_grid()

    # --- 고스트 위치 계산 ---
    def ghost_cells(self, cells: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """현재 피스 셀을 최대한 아래로 내린 위치를 반환."""
        drop = 0
        while True:
            shifted = [(c, r + drop + 1) for c, r in cells]
            if not self.is_valid(shifted):
                break
            drop += 1
        return [(c, r + drop) for c, r in cells]

    # --- 하드드롭 거리 계산 ---
    def hard_drop_distance(self, cells: List[Tuple[int, int]]) -> int:
        drop = 0
        while True:
            shifted = [(c, r + drop + 1) for c, r in cells]
            if not self.is_valid(shifted):
                break
            drop += 1
        return drop
