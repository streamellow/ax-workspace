# game.py — 게임 상태 관리 (점수·레벨·홀드·고스트·상태머신)

from __future__ import annotations
import pygame
from typing import Optional, List, Tuple

from settings import (
    SCORE_TABLE, SOFT_DROP_SCORE, HARD_DROP_SCORE,
    LINES_PER_LEVEL, MAX_LEVEL, fall_delay,
    LOCK_DELAY, STATE_MENU, STATE_PLAYING, STATE_PAUSED, STATE_GAMEOVER,
)
from board import Board
from piece import Piece, PieceBag
from highscore import load_highscore, save_highscore


class Game:
    """
    테트리스 게임의 전체 상태를 관리한다.
    Pygame 이벤트/시간에 의존하되 렌더링은 담당하지 않는다.
    """

    def __init__(self):
        self.board = Board()
        self.bag = PieceBag()
        self.highscore = load_highscore()
        self.state = STATE_MENU
        self._init_round()

    # --- 라운드 초기화 ---
    def _init_round(self):
        self.board.reset()
        self.bag = PieceBag()
        self.score = 0
        self.lines = 0
        self.level = 1
        self.current: Piece = self.bag.next()
        self.hold: Optional[Piece] = None
        self.hold_used = False          # 한 턴에 홀드는 1회
        self._fall_timer = 0            # ms 누적
        self._lock_timer: Optional[int] = None  # None이면 잠금 미진행
        self._lock_resets = 0
        self.game_over = False

    # --- 공개 상태 접근 ---
    @property
    def next_pieces(self) -> List[str]:
        """다음 3개 피스 이름."""
        return self.bag.peek(3)

    @property
    def ghost(self) -> List[Tuple[int, int]]:
        return self.board.ghost_cells(self.current.cells())

    # --- 게임 시작 / 재시작 ---
    def start(self):
        self._init_round()
        self.state = STATE_PLAYING

    def restart(self):
        self.start()

    # --- 일시정지 토글 ---
    def toggle_pause(self):
        if self.state == STATE_PLAYING:
            self.state = STATE_PAUSED
        elif self.state == STATE_PAUSED:
            self.state = STATE_PLAYING

    # --- 메인 업데이트 (dt: ms) ---
    def update(self, dt: int):
        if self.state != STATE_PLAYING:
            return

        # 자동 낙하
        self._fall_timer += dt
        if self._fall_timer >= fall_delay(self.level):
            self._fall_timer = 0
            self._try_move(0, 1, auto=True)

        # 잠금 타이머
        if self._lock_timer is not None:
            self._lock_timer += dt
            if self._lock_timer >= LOCK_DELAY:
                self._lock_piece()

    # --- 이동 ---
    def move_left(self):
        self._try_move(-1, 0)

    def move_right(self):
        self._try_move(1, 0)

    def soft_drop(self):
        moved = self._try_move(0, 1)
        if moved:
            self.score += SOFT_DROP_SCORE
            self._fall_timer = 0

    def hard_drop(self):
        dist = self.board.hard_drop_distance(self.current.cells())
        self.current.row += dist
        self.score += dist * HARD_DROP_SCORE
        self._lock_piece()

    # --- 회전 (SRS 월킥 간소화: ±1 오프셋 시도) ---
    def rotate(self, direction: int = 1):
        if self.state != STATE_PLAYING:
            return
        candidate = self.current.rotated_cells(direction)
        # 기본 위치 시도
        if self.board.is_valid(candidate):
            self.current.rotate(direction)
            self._reset_lock()
            return
        # 월킥: 좌우 ±1, ±2 시도
        for dx in [1, -1, 2, -2]:
            shifted = [(c + dx, r) for c, r in candidate]
            if self.board.is_valid(shifted):
                self.current.rotate(direction)
                self.current.col += dx
                self._reset_lock()
                return
        # 위로 1칸 시도 (I 피스 특수 케이스)
        for dx in [0, 1, -1]:
            shifted = [(c + dx, r - 1) for c, r in candidate]
            if self.board.is_valid(shifted):
                self.current.rotate(direction)
                self.current.col += dx
                self.current.row -= 1
                self._reset_lock()
                return

    # --- 홀드 ---
    def hold_piece(self):
        if self.state != STATE_PLAYING or self.hold_used:
            return
        if self.hold is None:
            self.hold = Piece(self.current.name)
            self._spawn_next()
        else:
            self.hold, self.current = (
                Piece(self.current.name),
                Piece(self.hold.name, col=3, row=0),
            )
        self.hold_used = True
        self._lock_timer = None

    # --- 내부 헬퍼 ---
    def _try_move(self, dx: int, dy: int, auto: bool = False) -> bool:
        """이동을 시도하고, 성공 여부를 반환한다."""
        p = self.current
        candidate = [(c + dx, r + dy) for c, r in p.cells()]
        if self.board.is_valid(candidate):
            p.col += dx
            p.row += dy
            if dy != 0:
                self._reset_lock()  # 아래로 이동하면 잠금 리셋
            return True
        else:
            if dy > 0:
                # 아래 이동 실패 = 바닥 또는 블록에 닿음 → 잠금 시작
                if self._lock_timer is None:
                    self._lock_timer = 0
            return False

    def _reset_lock(self):
        """잠금 타이머를 리셋한다 (최대 15회)."""
        if self._lock_timer is not None and self._lock_resets < 15:
            self._lock_timer = 0
            self._lock_resets += 1

    def _lock_piece(self):
        """현재 피스를 보드에 고정하고 다음 피스를 스폰."""
        self.board.lock(self.current.cells(), self.current.color_idx)
        cleared = self.board.clear_lines()
        self._add_score(cleared)
        self._lock_timer = None
        self._lock_resets = 0
        self._spawn_next()
        # 게임오버 판정
        if not self.board.is_valid(self.current.cells()):
            self._end_game()

    def _spawn_next(self):
        self.current = self.bag.next()
        self.hold_used = False

    def _add_score(self, cleared: int):
        if cleared > 0:
            self.score += SCORE_TABLE.get(cleared, 0) * self.level
            self.lines += cleared
            new_level = min(self.lines // LINES_PER_LEVEL + 1, MAX_LEVEL)
            self.level = new_level

    def _end_game(self):
        self.state = STATE_GAMEOVER
        if self.score > self.highscore:
            self.highscore = self.score
            save_highscore(self.highscore)
