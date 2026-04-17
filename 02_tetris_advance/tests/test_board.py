# tests/test_board.py — 보드 로직 테스트 (Pygame 불필요)

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from board import Board


@pytest.fixture
def board():
    return Board()


# --- 충돌 검사 ---
class TestIsValid:
    def test_empty_board_center_is_valid(self, board):
        assert board.is_valid([(3, 0), (4, 0), (5, 0), (6, 0)])

    def test_out_of_left_wall(self, board):
        assert not board.is_valid([(-1, 5)])

    def test_out_of_right_wall(self, board):
        assert not board.is_valid([(10, 5)])

    def test_out_of_bottom(self, board):
        assert not board.is_valid([(5, 20)])

    def test_row_above_board_is_allowed(self, board):
        # 스폰 시 row < 0인 셀은 충돌 검사 제외 (is_valid 통과해야 함)
        assert board.is_valid([(3, -1), (4, -1)])

    def test_occupied_cell_is_invalid(self, board):
        board.grid[5][5] = 1
        assert not board.is_valid([(5, 5)])


# --- 줄 삭제 ---
class TestClearLines:
    def test_no_clear_when_partial_row(self, board):
        board.grid[19][0] = 1  # 한 칸만 채움
        cleared = board.clear_lines()
        assert cleared == 0

    def test_single_line_clear(self, board):
        board.grid[19] = [1] * 10
        cleared = board.clear_lines()
        assert cleared == 1
        # 맨 아래 행은 이제 빈 행이어야 함
        assert all(c == 0 for c in board.grid[19])

    def test_double_line_clear(self, board):
        board.grid[18] = [2] * 10
        board.grid[19] = [3] * 10
        cleared = board.clear_lines()
        assert cleared == 2

    def test_tetris_four_lines(self, board):
        for r in range(16, 20):
            board.grid[r] = [1] * 10
        cleared = board.clear_lines()
        assert cleared == 4

    def test_rows_shift_down_after_clear(self, board):
        # 19행만 꽉 채우고, 18행에 마커 블록
        board.grid[18][0] = 7
        board.grid[19] = [1] * 10
        board.clear_lines()
        # 18행의 마커가 19행으로 내려와야 함
        assert board.grid[19][0] == 7


# --- 게임오버 판정 ---
class TestToppedOut:
    def test_empty_board_not_topped(self, board):
        assert not board.is_topped_out()

    def test_block_in_row0_is_gameover(self, board):
        board.grid[0][4] = 1
        assert board.is_topped_out()


# --- 고스트 ---
class TestGhostCells:
    def test_ghost_lands_at_bottom(self, board):
        cells = [(3, 0), (4, 0), (5, 0), (6, 0)]  # I피스 가로
        ghost = board.ghost_cells(cells)
        # 고스트의 최대 row = 19
        assert max(r for _, r in ghost) == 19

    def test_ghost_stops_on_existing_block(self, board):
        board.grid[10][5] = 1
        cells = [(5, 0)]
        ghost = board.ghost_cells(cells)
        # 블록 바로 위 = row 9
        assert ghost[0] == (5, 9)


# --- 리셋 ---
class TestReset:
    def test_reset_clears_grid(self, board):
        board.grid[10][5] = 3
        board.reset()
        assert all(board.grid[r][c] == 0
                   for r in range(20) for c in range(10))
