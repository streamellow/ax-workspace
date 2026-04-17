# renderer.py — 모든 draw 함수 (게임 로직 없음)

from __future__ import annotations
import pygame
from typing import List, Tuple, Optional

from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    BOARD_COLS, BOARD_ROWS, CELL_SIZE,
    BOARD_OFFSET_X, BOARD_OFFSET_Y,
    PIECE_COLORS, COLOR_BG, COLOR_BOARD_BG, COLOR_GRID,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_HIGHLIGHT,
    COLOR_GHOST, COLOR_BORDER, COLOR_PANEL_BG,
    FONT_SIZE_LARGE, FONT_SIZE_MEDIUM, FONT_SIZE_SMALL,
)
from piece import Piece, TETROMINOES, PIECE_COLOR_INDEX


class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_large = pygame.font.SysFont("consolas", FONT_SIZE_LARGE, bold=True)
        self.font_med = pygame.font.SysFont("consolas", FONT_SIZE_MEDIUM, bold=True)
        self.font_small = pygame.font.SysFont("consolas", FONT_SIZE_SMALL)

    # ── 공통 헬퍼 ────────────────────────────────────────────
    def _board_rect(self, col: int, row: int) -> pygame.Rect:
        x = BOARD_OFFSET_X + col * CELL_SIZE
        y = BOARD_OFFSET_Y + row * CELL_SIZE
        return pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)

    def _draw_cell(self, col: int, row: int, color: Tuple, ghost: bool = False):
        rect = self._board_rect(col, row)
        if ghost:
            s = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
            s.fill((*color, 80))
            self.screen.blit(s, rect.topleft)
            pygame.draw.rect(self.screen, color, rect, 1)
        else:
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, (0, 0, 0), rect, 1)
            # 하이라이트 (좌상단 밝기)
            bright = tuple(min(255, c + 60) for c in color)
            pygame.draw.line(self.screen, bright, rect.topleft, rect.topright, 2)
            pygame.draw.line(self.screen, bright, rect.topleft, rect.bottomleft, 2)

    def _text(self, text: str, font, color, x: int, y: int, center: bool = False):
        surf = font.render(text, True, color)
        rect = surf.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(surf, rect)

    # ── 배경 ──────────────────────────────────────────────────
    def draw_background(self):
        self.screen.fill(COLOR_BG)

    # ── 보드 배경 + 그리드 ────────────────────────────────────
    def draw_board_bg(self):
        board_w = BOARD_COLS * CELL_SIZE
        board_h = BOARD_ROWS * CELL_SIZE
        bg_rect = pygame.Rect(BOARD_OFFSET_X, BOARD_OFFSET_Y, board_w, board_h)
        pygame.draw.rect(self.screen, COLOR_BOARD_BG, bg_rect)
        pygame.draw.rect(self.screen, COLOR_BORDER, bg_rect, 2)
        # 그리드 라인
        for c in range(BOARD_COLS + 1):
            x = BOARD_OFFSET_X + c * CELL_SIZE
            pygame.draw.line(self.screen, COLOR_GRID,
                             (x, BOARD_OFFSET_Y), (x, BOARD_OFFSET_Y + board_h))
        for r in range(BOARD_ROWS + 1):
            y = BOARD_OFFSET_Y + r * CELL_SIZE
            pygame.draw.line(self.screen, COLOR_GRID,
                             (BOARD_OFFSET_X, y), (BOARD_OFFSET_X + board_w, y))

    # ── 보드 셀 ───────────────────────────────────────────────
    def draw_board_cells(self, grid):
        for r in range(BOARD_ROWS):
            for c in range(BOARD_COLS):
                if grid[r][c] != 0:
                    self._draw_cell(c, r, PIECE_COLORS[grid[r][c]])

    # ── 고스트 ────────────────────────────────────────────────
    def draw_ghost(self, ghost_cells: List[Tuple[int, int]], color_idx: int):
        color = PIECE_COLORS[color_idx]
        for col, row in ghost_cells:
            if row >= 0:
                self._draw_cell(col, row, color, ghost=True)

    # ── 현재 피스 ─────────────────────────────────────────────
    def draw_piece(self, cells: List[Tuple[int, int]], color_idx: int):
        color = PIECE_COLORS[color_idx]
        for col, row in cells:
            if row >= 0:
                self._draw_cell(col, row, color)

    # ── 사이드 패널 ───────────────────────────────────────────
    def draw_side_panel(self, score: int, highscore: int, level: int, lines: int,
                        next_pieces: List[str], hold_piece, hold_used: bool):
        panel_x = BOARD_OFFSET_X + BOARD_COLS * CELL_SIZE + 15
        panel_w = SCREEN_WIDTH - panel_x - 10
        self._draw_panel_section(panel_x, panel_w, score, highscore, level, lines,
                                 next_pieces, hold_piece, hold_used)

    def _draw_panel_section(self, px: int, pw: int,
                             score, highscore, level, lines,
                             next_pieces, hold_piece, hold_used):
        y = BOARD_OFFSET_Y

        # --- 점수 ---
        self._section_box(px, y, pw, 120, "SCORE")
        y += 28
        self._text(str(score), self.font_med, COLOR_HIGHLIGHT, px + 8, y)
        y += 32
        self._text("BEST", self.font_small, COLOR_TEXT_DIM, px + 8, y)
        y += 20
        self._text(str(highscore), self.font_small, COLOR_TEXT, px + 8, y)
        y += 30

        # --- 레벨 / 줄 ---
        self._section_box(px, y, pw, 70, "LEVEL / LINES")
        y += 26
        self._text(f"Lv {level}   {lines} L", self.font_small, COLOR_TEXT, px + 8, y)
        y += 48

        # --- 다음 블록 ---
        self._section_box(px, y, pw, 130, "NEXT")
        y += 26
        for name in next_pieces[:3]:
            self._draw_mini_piece(name, px + 8, y, scale=16)
            y += 34

        # --- 홀드 ---
        y += 6
        self._section_box(px, y, pw, 80, "HOLD")
        y += 26
        if hold_piece:
            alpha = 0.4 if hold_used else 1.0
            self._draw_mini_piece(hold_piece.name, px + 8, y, scale=16, dim=hold_used)
        else:
            self._text("—", self.font_small, COLOR_TEXT_DIM, px + 8, y)
        y += 60

        # --- 조작 키 안내 ---
        y = SCREEN_HEIGHT - 180
        keys = [
            ("← →", "이동"),
            ("↑ / Z", "회전"),
            ("↓", "소프트드롭"),
            ("Space", "하드드롭"),
            ("C", "홀드"),
            ("P / Esc", "일시정지"),
        ]
        self._text("KEYS", self.font_small, COLOR_TEXT_DIM, px + 8, y)
        y += 20
        for key, desc in keys:
            self._text(f"{key:<8}{desc}", self.font_small, COLOR_TEXT_DIM, px + 4, y)
            y += 18

    def _section_box(self, x: int, y: int, w: int, h: int, title: str):
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, COLOR_PANEL_BG, rect, border_radius=4)
        pygame.draw.rect(self.screen, COLOR_BORDER, rect, 1, border_radius=4)
        self._text(title, self.font_small, COLOR_TEXT_DIM, x + 6, y + 4)

    def _draw_mini_piece(self, name: str, x: int, y: int, scale: int = 16, dim: bool = False):
        shape = TETROMINOES[name][0]
        color = PIECE_COLORS[PIECE_COLOR_INDEX[name]]
        if dim:
            color = tuple(c // 3 for c in color)
        for dx, dy in shape:
            r = pygame.Rect(x + dx * scale, y + dy * scale, scale - 1, scale - 1)
            pygame.draw.rect(self.screen, color, r)

    # ── 오버레이 (반투명) ─────────────────────────────────────
    def _overlay(self, alpha: int = 160):
        s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        s.fill((0, 0, 0, alpha))
        self.screen.blit(s, (0, 0))

    # ── 메뉴 화면 ─────────────────────────────────────────────
    def draw_menu(self):
        self.draw_background()
        cx = SCREEN_WIDTH // 2
        self._text("TETRIS", self.font_large, COLOR_HIGHLIGHT, cx, 200, center=True)
        self._text("Press ENTER to Start", self.font_med, COLOR_TEXT, cx, 300, center=True)
        self._text("Press Q to Quit", self.font_small, COLOR_TEXT_DIM, cx, 360, center=True)
        self._draw_key_guide_full(cx, 440)

    def _draw_key_guide_full(self, cx: int, y: int):
        keys = [
            "← → : Move     ↑/Z : Rotate",
            "↓ : Soft Drop   Space : Hard Drop",
            "C : Hold        P/Esc : Pause",
        ]
        for line in keys:
            self._text(line, self.font_small, COLOR_TEXT_DIM, cx, y, center=True)
            y += 22

    # ── 일시정지 ──────────────────────────────────────────────
    def draw_pause(self):
        self._overlay(140)
        cx = SCREEN_WIDTH // 2
        self._text("PAUSED", self.font_large, COLOR_HIGHLIGHT, cx, SCREEN_HEIGHT // 2 - 40, center=True)
        self._text("Press P or Esc to Resume", self.font_small, COLOR_TEXT_DIM,
                   cx, SCREEN_HEIGHT // 2 + 20, center=True)

    # ── 게임오버 ──────────────────────────────────────────────
    def draw_gameover(self, score: int, highscore: int):
        self._overlay(170)
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2
        self._text("GAME OVER", self.font_large, (240, 60, 60), cx, cy - 80, center=True)
        self._text(f"Score: {score}", self.font_med, COLOR_TEXT, cx, cy, center=True)
        self._text(f"Best:  {highscore}", self.font_med, COLOR_HIGHLIGHT, cx, cy + 40, center=True)
        self._text("Enter: Restart   Q: Menu", self.font_small, COLOR_TEXT_DIM,
                   cx, cy + 100, center=True)
