import pygame
import random

# Initialize pygame
pygame.init()

# Setup screen
WIDTH, HEIGHT = 300, 600
BLOCK_SIZE = 30

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Tetris")

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
COLORS = [
    (0, 255, 255),  # Cyan - I
    (255, 255, 0),  # Yellow - O
    (128, 0, 128),  # Purple - T
    (0, 255, 0),    # Green - S
    (255, 0, 0),    # Red - Z
    (0, 0, 255),    # Blue - J
    (255, 127, 0)   # Orange - L
]

# Tetromino shapes
SHAPES = [
    [[1, 1, 1, 1]], # I
    [[1, 1], [1, 1]], # O
    [[0, 1, 0], [1, 1, 1]], # T
    [[0, 1, 1], [1, 1, 0]], # S
    [[1, 1, 0], [0, 1, 1]], # Z
    [[1, 0, 0], [1, 1, 1]], # J
    [[0, 0, 1], [1, 1, 1]]  # L
]

class Tetromino:
    def __init__(self):
        self.type = random.randint(0, len(SHAPES) - 1)
        self.shape = SHAPES[self.type]
        self.color = COLORS[self.type]
        self.x = WIDTH // BLOCK_SIZE // 2 - len(self.shape[0]) // 2
        self.y = 0

    def rotate(self):
        self.shape = [list(row) for row in zip(*self.shape[::-1])]

class Tetris:
    def __init__(self):
        self.w = WIDTH // BLOCK_SIZE
        self.h = HEIGHT // BLOCK_SIZE
        self.grid = [[0 for _ in range(self.w)] for _ in range(self.h)]
        self.current_piece = Tetromino()
        self.game_over = False
        self.score = 0
        self.clock = pygame.time.Clock()

    def check_collision(self, dx=0, dy=0, shape=None):
        if shape is None:
            shape = self.current_piece.shape
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell:
                    nx = self.current_piece.x + x + dx
                    ny = self.current_piece.y + y + dy
                    if nx < 0 or nx >= self.w or ny >= self.h or (ny >= 0 and self.grid[ny][nx]):
                        return True
        return False

    def clear_lines(self):
        lines_cleared = 0
        for y in range(self.h - 1, -1, -1):
            if all(self.grid[y]):
                del self.grid[y]
                self.grid.insert(0, [0 for _ in range(self.w)])
                lines_cleared += 1
        self.score += lines_cleared ** 2 * 100

    def drop_piece(self):
        if not self.check_collision(dy=1):
            self.current_piece.y += 1
        else:
            for y, row in enumerate(self.current_piece.shape):
                for x, cell in enumerate(row):
                    if cell:
                        self.grid[self.current_piece.y + y][self.current_piece.x + x] = self.current_piece.color
            self.clear_lines()
            self.current_piece = Tetromino()
            if self.check_collision():
                self.game_over = True

    def draw(self, screen):
        screen.fill(BLACK)
        
        # Draw grid
        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                if cell:
                    pygame.draw.rect(screen, cell, (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE), 0)
                    pygame.draw.rect(screen, WHITE, (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE), 1)
        
        # Draw current piece
        for y, row in enumerate(self.current_piece.shape):
            for x, cell in enumerate(row):
                if cell:
                    pygame.draw.rect(screen, self.current_piece.color, ((self.current_piece.x + x) * BLOCK_SIZE, (self.current_piece.y + y) * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE), 0)
                    pygame.draw.rect(screen, WHITE, ((self.current_piece.x + x) * BLOCK_SIZE, (self.current_piece.y + y) * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE), 1)

        # Draw score
        font = pygame.font.SysFont('Arial', 25, True, False)
        text = font.render(f"Score: {self.score}", True, WHITE)
        screen.blit(text, [10, 10])

        if self.game_over:
            font = pygame.font.SysFont('Arial', 50, True, False)
            text = font.render("GAME OVER", True, WHITE)
            screen.blit(text, [WIDTH // 2 - text.get_width() // 2, HEIGHT // 2 - text.get_height() // 2])

        pygame.display.flip()

def main():
    game = Tetris()
    fall_time = 0
    
    running = True
    while running:
        dt = game.clock.tick(60)
        fall_time += dt
        
        if fall_time > 500: # 0.5 sec fall time
            if not game.game_over:
                game.drop_piece()
            fall_time = 0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and not game.game_over:
                if event.key == pygame.K_LEFT and not game.check_collision(dx=-1):
                    game.current_piece.x -= 1
                if event.key == pygame.K_RIGHT and not game.check_collision(dx=1):
                    game.current_piece.x += 1
                if event.key == pygame.K_DOWN:
                    game.drop_piece()
                if event.key == pygame.K_UP:
                    old_shape = [row[:] for row in game.current_piece.shape]
                    game.current_piece.rotate()
                    if game.check_collision():
                        game.current_piece.shape = old_shape
            
            # Restart game when space is pressed on Game Over
            if event.type == pygame.KEYDOWN and game.game_over:
                if event.key == pygame.K_SPACE:
                    game = Tetris()

        game.draw(screen)

    pygame.quit()

if __name__ == "__main__":
    main()
