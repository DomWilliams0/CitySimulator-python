import logging
import random

import pygame

import state
from vec2d import Vec2d
import world as world_module
import util


class GameScreen:
    """
    Handles all drawing to screen
    """

    def __init__(self):
        self._window = None
        self.camera = None
        self.font = None

    def create_window(self):
        """
        Creates the window once pygame has been initialised
        """
        self._window = pygame.display.set_mode(WINDOW_SIZE)
        pygame.display.set_caption("flibbid")
        self.font = pygame.font.SysFont("monospace", 20, bold=True)

        logging.basicConfig(level=logging.INFO)

    def set_camera_world(self, world):
        """
        Sets the main camera world
        :param world: The world to be tracked by the camera
        """
        self.camera = Camera(world)

    def fill(self, colour):
        """
        :param colour: The colour to fill the screen with
        """
        self._window.fill(colour)

    def draw_rect(self, rect, colour=(255, 0, 0), filled=True):
        """
        :param rect: The rectangle to draw
        :param colour: Optional colour, defaults to red
        :param filled: Outlined if False
        """
        dim = (rect[1][0], rect[1][1]) if len(rect) == 2 else (rect.width, rect.height)
        pygame.draw.rect(self._window, colour, (self.camera.apply_rect(rect), dim), 0 if filled else 2)

    def draw_sprite(self, sprite, loc):
        """
        Draws a sprite at the given world position
        """
        self._window.blit(sprite, self.camera.apply_rect(loc))

    def draw_block(self, block, loc, surface=None):
        image = world_module.Block.HELPER.block_images[block.render_id]
        s = surface if surface else self._window
        s.blit(image, loc)

    def draw_line(self, start, end, colour=(255, 20, 20)):
        """
        Draws a line between the given points
        """
        pygame.draw.line(self._window, colour, self.camera.apply(start), self.camera.apply(end), 1)

    def draw_circle(self, pos, colour=(0, 255, 100), radius=10, filled=True):
        """
        Draws a circle at the given position
        """
        camera_apply = tuple(map(int, self.camera.apply(pos)))
        pygame.draw.circle(self._window, colour, camera_apply, radius, 0 if filled else 2)

    def draw_circle_in_tile(self, pos, colour=(0, 255, 100), radius=10, filled=True):
        self.draw_circle((pos[0] + TILE_SIZE / 2, pos[1] + TILE_SIZE / 2), colour, radius, filled)

    def draw_fps(self, fps, offset=20):
        """
        Draws the given number at the bottom left of the screen, with the given offset
        """
        self.draw_string(str(int(fps)), (offset, WINDOW_SIZE[1] - offset))

    def draw_string(self, string, pos, colour=(255, 0, 0), absolute=True):
        surface = self.font.render(string, 1, colour)
        self._window.blit(surface, self.camera.apply(pos) if not absolute else pos)

    def blit(self, surface, pos=(0, 0)):
        """
        Blits the given surface onto the screen at the given position
        """
        self._window.blit(surface, pos)


class Camera:
    """
    Allows viewport scrolling
    """

    def __init__(self, world, target=None):
        self.view_size = WINDOW_SIZE
        self.pos = Vec2d(0, 0)
        self.velocity = Vec2d(0, 0)
        self.target = target

        self.world = None
        self.world_dimensions = None
        self.boundaries = None
        self.update_boundaries(world)

    def tick(self):
        """
        Gradually centres the target on screen, without leaving the world boundaries
        """
        if not self.target:
            return

        if self.target.world != self.world:
            return

        v = self._direction_to_target(self.target.rect.center)
        if v.get_length_sqrd() < TILE_SIZE_SQRD / 2:
            self.velocity.x, self.velocity.y = 0, 0
            return

        self.velocity = v * 4
        self.pos += self.velocity * DELTA

        self._check_boundaries()

    def _check_boundaries(self):
        self.pos[0] = max(self.boundaries[0], self.pos[0])
        self.pos[1] = max(self.boundaries[1], self.pos[1])
        self.pos[0] = min(self.boundaries[2], self.pos[0])
        self.pos[1] = min(self.boundaries[3], self.pos[1])

    def centre(self, target=None):
        """
        Centres the target entity immediately
        :param target If None, then the current target
        """
        if not target:
            if not self.target:
                return
            target = self.target

        self.pos += self._direction_to_target(target.rect.center)
        self.velocity = 0
        self._check_boundaries()

    def _direction_to_target(self, pos):
        camera_centre = Vec2d(self.pos[0] + self.view_size[0] / 2, self.pos[1] + self.view_size[1] / 2)
        target_centre = Vec2d(pos)
        return target_centre - camera_centre

    def apply_rect(self, rect):
        """
        Applies camera offset to a rectangle
        :param rect Either a util.Rect or a tuple ((x, y), (w, h))
        """
        if not isinstance(rect, util.Rect):
            rect = rect[0]
        else:
            rect = rect.x, rect.y
        return self.apply(rect)

    def apply(self, tup):
        return tup[0] - self.pos[0], tup[1] - self.pos[1]

    def update_boundaries(self, world):
        self.world = world
        self.world_dimensions = (self.world.pixel_width, self.world.pixel_height)
        self.boundaries = [0, 0,
                           self.world_dimensions[0] - self.view_size[0],
                           self.world_dimensions[1] - self.view_size[1]]

        if self.boundaries[2] < 0:
            x_off = -self.boundaries[2]
            self.boundaries[0] = -x_off
            self.boundaries[2] = x_off * 0.5 - TILE_SIZE
        if self.boundaries[3] < 0:
            y_off = -self.boundaries[3]
            self.boundaries[1] = -y_off / 2
            self.boundaries[3] = self.boundaries[1]

        self._check_boundaries()

    def __setattr__(self, key, value):
        self.__dict__[key] = value
        if key == "target":
            self.centre(value)


class Speed:
    SLOW = 80
    MEDIUM = 120
    FAST = 180
    MAX = 240

    VEHICLE_MIN = 200
    VEHICLE_MAX = 400

    WTF_DEBUG = 800

    VALUES = [SLOW, MEDIUM, FAST]

    @staticmethod
    def random():
        return random.choice(Speed.VALUES)


class Direction:
    SOUTH = 0
    WEST = 1
    EAST = 2
    NORTH = 3

    VALUES = [SOUTH, WEST, EAST, NORTH]
    HORIZONTALS = [WEST, EAST]
    VERTICALS = [SOUTH, NORTH]

    @staticmethod
    def random():
        return random.choice(Direction.VALUES)

    @staticmethod
    def opposite(direction):
        if direction in Direction.HORIZONTALS:
            return Direction.EAST if direction == Direction.WEST else Direction.WEST
        else:
            return Direction.SOUTH if direction == Direction.NORTH else Direction.NORTH


class EntityType:
    HUMAN = 0
    VEHICLE = 1
    ALL = 2

    @staticmethod
    def parse_string(s):
        s = s.upper()
        for prop, val in EntityType.__dict__.items():
            if s == prop and isinstance(val, int):
                return val
        return EntityType.ALL


STATEMANAGER = state.StateManager()
SCREEN = GameScreen()
DELTA = 0
FPS = 0
WINDOW_SIZE = (640, 640)
WINDOW_CENTRE = (WINDOW_SIZE[0] / 2, WINDOW_SIZE[1] / 2)

TILESET_RESOLUTION = 16
TILE_SIZE = 32
DIMENSION = (TILE_SIZE, TILE_SIZE)
TILE_SIZE_SQRD = TILE_SIZE ** 2
