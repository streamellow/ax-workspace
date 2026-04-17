# input_handler.py — 키 입력 → 게임 액션 매핑

from __future__ import annotations
import pygame
from settings import DAS_DELAY, DAS_INTERVAL, STATE_PLAYING, STATE_PAUSED, STATE_GAMEOVER, STATE_MENU


class InputHandler:
    """
    키 입력을 받아 Game 객체의 메서드를 호출한다.
    DAS(Delayed Auto Shift) 처리 포함.
    """

    def __init__(self):
        self._das_key: int | None = None   # 현재 DAS 진행 중인 키
        self._das_timer: int = 0            # ms
        self._das_active: bool = False      # DAS 연속이동 단계 진입 여부

    def handle_events(self, events, game) -> bool:
        """
        이벤트 처리.
        Returns: False이면 게임 종료 요청.
        """
        for event in events:
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                if not self._handle_keydown(event.key, game):
                    return False

            if event.type == pygame.KEYUP:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    if event.key == self._das_key:
                        self._das_key = None
                        self._das_active = False
        return True

    def _handle_keydown(self, key: int, game) -> bool:
        state = game.state

        # --- 전역 키 ---
        if key == pygame.K_q:
            if state in (STATE_MENU, STATE_GAMEOVER):
                return False  # 종료

        # --- 메뉴 ---
        if state == STATE_MENU:
            if key == pygame.K_RETURN:
                game.start()

        # --- 게임오버 ---
        elif state == STATE_GAMEOVER:
            if key == pygame.K_RETURN:
                game.restart()
            elif key == pygame.K_q:
                game.state = STATE_MENU

        # --- 일시정지 ---
        elif state == STATE_PAUSED:
            if key in (pygame.K_p, pygame.K_ESCAPE):
                game.toggle_pause()

        # --- 플레이 중 ---
        elif state == STATE_PLAYING:
            if key == pygame.K_LEFT:
                game.move_left()
                self._das_key = pygame.K_LEFT
                self._das_timer = 0
                self._das_active = False
            elif key == pygame.K_RIGHT:
                game.move_right()
                self._das_key = pygame.K_RIGHT
                self._das_timer = 0
                self._das_active = False
            elif key in (pygame.K_UP, pygame.K_x):
                game.rotate(1)
            elif key == pygame.K_z:
                game.rotate(-1)
            elif key == pygame.K_DOWN:
                game.soft_drop()
            elif key == pygame.K_SPACE:
                game.hard_drop()
            elif key == pygame.K_c:
                game.hold_piece()
            elif key in (pygame.K_p, pygame.K_ESCAPE):
                game.toggle_pause()

        return True

    def update_das(self, dt: int, game):
        """매 프레임 DAS 업데이트 (키 계속 누름 처리)."""
        if game.state != STATE_PLAYING or self._das_key is None:
            return
        self._das_timer += dt
        threshold = DAS_INTERVAL if self._das_active else DAS_DELAY
        if self._das_timer >= threshold:
            self._das_timer = 0
            self._das_active = True
            if self._das_key == pygame.K_LEFT:
                game.move_left()
            elif self._das_key == pygame.K_RIGHT:
                game.move_right()
