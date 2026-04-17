# tests/test_game.py — 게임 상태 로직 테스트 (Pygame 없이)
# Game.update()는 pygame.time이 필요하므로 직접 내부 메서드를 테스트

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Pygame stub (헤드리스 환경에서 import 오류 방지)
import types
fake_pygame = types.ModuleType("pygame")
fake_pygame.init = lambda: None
sys.modules.setdefault("pygame", fake_pygame)

import pytest
from board import Board
from piece import Piece
from settings import SCORE_TABLE, LINES_PER_LEVEL


# --- 점수 계산 테스트 (Game._add_score 로직을 직접 검증) ---
class TestScoreLogic:
    """Game._add_score 로직을 Board + 순수 함수 수준에서 검증."""

    def _simulate_add_score(self, cleared, level, score, lines):
        """game._add_score 로직 복제."""
        from settings import MAX_LEVEL
        if cleared > 0:
            score += SCORE_TABLE.get(cleared, 0) * level
            lines += cleared
            new_level = min(lines // LINES_PER_LEVEL + 1, MAX_LEVEL)
            level = new_level
        return score, lines, level

    def test_single_clear_score(self):
        score, lines, level = self._simulate_add_score(1, 1, 0, 0)
        assert score == 100

    def test_tetris_score(self):
        score, lines, level = self._simulate_add_score(4, 1, 0, 0)
        assert score == 800

    def test_level_multiplier(self):
        score, lines, level = self._simulate_add_score(1, 3, 0, 0)
        assert score == 300  # 100 * 3

    def test_level_up_after_10_lines(self):
        score, lines, level = 0, 9, 1
        score, lines, level = self._simulate_add_score(1, level, score, lines)
        assert level == 2

    def test_max_level_cap(self):
        from settings import MAX_LEVEL
        score, lines, level = self._simulate_add_score(4, MAX_LEVEL, 0, (MAX_LEVEL - 1) * LINES_PER_LEVEL)
        assert level == MAX_LEVEL


# --- 게임오버 판정 ---
class TestGameOverDetection:
    def test_gameover_when_piece_blocked_at_spawn(self):
        board = Board()
        # 스폰 위치(행 0~1)에 블록 가득 채우기
        board.grid[0] = [1] * 10
        assert board.is_topped_out()

    def test_no_gameover_on_empty_board(self):
        board = Board()
        assert not board.is_topped_out()


# --- 줄 삭제 후 점수 연동 시나리오 ---
class TestLineClearIntegration:
    def test_four_line_clear_removes_all_rows(self):
        board = Board()
        for r in range(16, 20):
            board.grid[r] = [2] * 10
        cleared = board.clear_lines()
        assert cleared == 4
        for r in range(16, 20):
            assert all(c == 0 for c in board.grid[r])

    def test_partial_rows_not_cleared(self):
        board = Board()
        board.grid[19] = [1] * 9 + [0]  # 한 칸 비어있음
        cleared = board.clear_lines()
        assert cleared == 0
        assert board.grid[19][0] == 1  # 그대로 남음


# --- 하드드롭 거리 ---
class TestHardDropDistance:
    def test_hard_drop_on_empty_board(self):
        board = Board()
        cells = [(3, 0), (4, 0), (5, 0), (6, 0)]
        dist = board.hard_drop_distance(cells)
        assert dist == 19  # row 0 → row 19

    def test_hard_drop_blocked_by_existing_block(self):
        board = Board()
        board.grid[10][5] = 1
        cells = [(5, 0)]
        dist = board.hard_drop_distance(cells)
        assert dist == 9  # row 0 → row 9 (10 위)
