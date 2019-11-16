from enum import Enum
from itertools import product
import logging
from operator import attrgetter
import random
import time
from typing import Sequence, Tuple

import pygame
from pygame.locals import QUIT, K_SPACE


logger = logging.getLogger(__name__)


DELAY = 1 / 30
START_POSITION = 0, 4


class Color(Enum):
    LINE_COLOR = (200, 200, 200)
    BACKGROUND = (50, 50, 50)
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    CYAN = (0, 255, 255)
    PURPLE = (128, 0, 128)
    YELLOW = (255, 255, 0)
    ORANGE = (255, 165, 0)


GRID_HEIGHT = 20
GRID_WIDTH = 10


class SingleBlock:
    def __init__(self, i, j, color):
        self.i = i
        self.j = j
        self.color = color

    def __repr__(self):
        return f"SingleBlock({self.i}, {self.j}, {self.color})"

    @property
    def coords(self):
        return self.i, self.j

    @coords.setter
    def coords(self, new_coords):
        self.i, self.j = new_coords

    def step_down(self):
        return SingleBlock(self.i + 1, self.j, self.color)

    def step_left(self):
        return SingleBlock(self.i, self.j - 1, self.color)

    def step_right(self):
        return SingleBlock(self.i, self.j + 1, self.color)


class Tetromino:
    """
    Base class for all tetrominos.
    Each tetromino needs a color and coordinates.
    """

    color: Color
    initial_coords: Sequence[Tuple[int, int]]
    center: Tuple[int, int]

    def __init__(self, i, j, other_positions):
        self.i = i
        self.j = j
        self._center_coords()
        self.blocks = [
            SingleBlock(self.i + i, self.j + j, self.color)
            for i, j in self.initial_coords
        ]
        self.other_positions = other_positions
        self.done = False

    def __repr__(self):
        return self.blocks.__repr__()

    def _center_coords(self):
        x, y = self.center
        self.initial_coords = [(xx - x, yy - y) for xx, yy in self.initial_coords]

    def step_down(self):
        new_blocks = [block.step_down() for block in self.blocks]

        if any(block.i >= GRID_HEIGHT for block in new_blocks):
            self.done = True
            return

        if any(block.coords in self.other_positions for block in new_blocks):
            self.done = True
            return

        self.i += 1
        self.blocks = new_blocks

    def step_left(self):
        new_blocks = [block.step_left() for block in self.blocks]

        if any(block.j < 0 for block in new_blocks):
            return

        if any(block.coords in self.other_positions for block in new_blocks):
            return

        self.j -= 1
        self.blocks = new_blocks

    def step_right(self):
        new_blocks = [block.step_right() for block in self.blocks]

        if any(block.j > GRID_WIDTH - 1 for block in new_blocks):
            return

        if any(block.coords in self.other_positions for block in new_blocks):
            return

        self.j += 1
        self.blocks = new_blocks

    def rotate_clockwise(self):
        logger.debug("Before rotation: %s", self)
        for block in self.blocks:
            ii = block.i - self.i
            jj = block.j - self.j
            block.coords = self.i + jj, self.j - ii

        self._check_boundaries()

    def rotate_anticlockwise(self):
        for block in self.blocks:
            ii = block.i - self.i
            jj = block.j - self.j
            block.coords = self.i - jj, self.j + ii

        self._check_boundaries()

    def _check_boundaries(self):
        min_j = min(block.j for block in self.blocks)

        if min_j < 0:
            for block in self.blocks:
                block.j -= min_j
            return

        max_j = max(block.j for block in self.blocks)

        if max_j > GRID_WIDTH - 1:
            for block in self.blocks:
                block.j -= 1 + max_j - GRID_WIDTH
            return

        max_i = max(block.i for block in self.blocks)

        if max_i > GRID_HEIGHT - 1:
            for block in self.blocks:
                block.i -= 1 + max_i - GRID_HEIGHT


# fmt: off
class LShaped(Tetromino):
    color = Color.BLUE
    initial_coords = (
        (0, 0),
        (1, 0),
        (2, 0),
        (2, 1)
    )
    center = (1, 0)


class JShaped(Tetromino):
    color = Color.ORANGE
    initial_coords = (
        (0, 1),
        (1, 1),
        (2, 1),
        (2, 0)
    )
    center = (1, 1)


class SShaped(Tetromino):
    color = Color.GREEN
    initial_coords = (
        (0, 0),
        (1, 0),
        (1, 1),
        (2, 1)
    )
    center = (1, 0)


class TShaped(Tetromino):
    color = Color.PURPLE
    initial_coords = (
        (0, 1),
        (1, 0),
        (1, 1),
        (2, 1)
    )
    center = (1, 1)


class ZShaped(Tetromino):
    color = Color.RED
    initial_coords = (
        (0, 1),
        (1, 1),
        (1, 0),
        (2, 0)
    )
    center = (1, 1)


class IShaped(Tetromino):
    color = Color.CYAN
    initial_coords = (
        (0, 0),
        (1, 0),
        (2, 0),
        (3, 0)
    )
    center = (1, 0)


class Square(Tetromino):
    color = Color.YELLOW
    initial_coords = (
        (0, 0),
        (1, 0),
        (0, 1),
        (1, 1)
    )
# fmt: on


class Grid:
    def __init__(self, width, height):
        self.height = height
        self.width = width

        self.grid_height = GRID_HEIGHT
        self.grid_width = GRID_WIDTH

        self.pixel_width = self.width // self.grid_width
        self.pixel_height = self.height // self.grid_height

        self.blocks = []
        self.positions = set()
        self.active_tetromino = None

    @staticmethod
    def draw_background(screen):
        background = pygame.Surface(screen.get_size())
        background = background.convert()
        background.fill(Color.LINE_COLOR.value)
        screen.blit(background, (0, 0))

    def draw_grid(self, screen):
        pix_width = self.pixel_width
        pix_height = self.pixel_height
        for i, j in product(range(self.grid_height), range(self.grid_width)):
            rect = pygame.Rect(
                j * pix_width, i * pix_height, pix_width - 1, pix_height - 1
            )
            pygame.draw.rect(screen, Color.BACKGROUND.value, rect)

    def draw_tetrominos(self, screen):
        pix_width = self.pixel_width
        pix_height = self.pixel_height
        for block in [*self.active_tetromino.blocks, *self.blocks]:
            i, j = block.coords
            color = block.color
            rect = pygame.Rect(
                j * pix_width, i * pix_height, pix_width - 1, pix_height - 1
            )
            pygame.draw.rect(screen, color.value, rect)

    def update_blocks(self, new_blocks):
        self.blocks.extend(new_blocks)
        for block in new_blocks:
            self.positions.add(block.coords)


def main():
    pygame.display.init()
    screen = pygame.display.set_mode((300, 600))
    grid = Grid(300, 600)
    pygame.display.set_caption("Tetris")

    counter = 0
    game_over = False

    while not game_over:

        tetromino_class = random.choice(
            [SShaped, TShaped, ZShaped, LShaped, IShaped, JShaped]
        )
        active_tetromino = tetromino_class(*START_POSITION, grid.positions)
        grid.active_tetromino = active_tetromino

        while True:
            keys = pygame.key.get_pressed()

            for event in pygame.event.get():
                if event.type == QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_x:
                        active_tetromino.rotate_clockwise()
                    elif event.key == pygame.K_y:
                        active_tetromino.rotate_anticlockwise()
                    if event.key == pygame.K_LEFT:
                        active_tetromino.step_left()
                    if event.key == pygame.K_RIGHT:
                        active_tetromino.step_right()
                    if event.key == pygame.K_DOWN:
                        active_tetromino.step_down()

            grid.draw_background(screen)
            grid.draw_grid(screen)
            grid.draw_tetrominos(screen)

            pygame.display.flip()
            time.sleep(DELAY)

            if counter == 30:
                active_tetromino.step_down()
                counter = 0

            counter += 1

            if active_tetromino.done:
                grid.update_blocks(active_tetromino.blocks)

                if START_POSITION in grid.positions:
                    game_over = True
                break


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
