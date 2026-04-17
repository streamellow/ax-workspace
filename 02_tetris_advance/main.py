# main.py — 진입점: 게임 루프 조립

import pygame
import sys

from settings import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, STATE_MENU, STATE_PLAYING, STATE_PAUSED, STATE_GAMEOVER
from game import Game
from renderer import Renderer
from input_handler import InputHandler


def main():
    pygame.init()
    pygame.display.set_caption("Tetris Advanced")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()

    game = Game()
    renderer = Renderer(screen)
    handler = InputHandler()

    running = True
    while running:
        dt = clock.tick(FPS)  # ms

        # --- 입력 ---
        events = pygame.event.get()
        running = handler.handle_events(events, game)
        handler.update_das(dt, game)

        # --- 업데이트 ---
        game.update(dt)

        # --- 렌더링 ---
        if game.state == STATE_MENU:
            renderer.draw_menu()
        else:
            renderer.draw_background()
            renderer.draw_board_bg()
            renderer.draw_board_cells(game.board.grid)
            renderer.draw_ghost(game.ghost, game.current.color_idx)
            renderer.draw_piece(game.current.cells(), game.current.color_idx)
            renderer.draw_side_panel(
                score=game.score,
                highscore=game.highscore,
                level=game.level,
                lines=game.lines,
                next_pieces=game.next_pieces,
                hold_piece=game.hold,
                hold_used=game.hold_used,
            )
            if game.state == STATE_PAUSED:
                renderer.draw_pause()
            elif game.state == STATE_GAMEOVER:
                renderer.draw_gameover(game.score, game.highscore)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
