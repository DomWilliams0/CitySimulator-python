import logging
import random
import operator

import pygame

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

        # set icon
        icon = pygame.image.load(util.get_resource_path("icon.png")).convert_alpha()
        pygame.display.set_icon(icon)

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

    def draw_sprite(self, sprite, loc, area=None):
        """
        Draws a sprite at the given world position
        """
        self._window.blit(sprite, self.camera.apply_rect(loc), area)

    def draw_sprite_from_pos(self, sprite, loc, area=None):
        self._window.blit(sprite, self.camera.apply(loc), area)

    def draw_block(self, block, loc, surface=None):
        """
        Draws a block to the given loc on the given surface (the window if None)
        """
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
        """
        Centres the circle in the given tile position
        """
        self.draw_circle((pos[0] + TILE_SIZE / 2, pos[1] + TILE_SIZE / 2), colour, radius, filled)

    def draw_fps(self, fps, offset=20):
        """
        Draws the given number at the bottom left of the screen, with the given offset
        """
        self.draw_string(str(int(fps)), (offset, WINDOW_SIZE[1] - offset))

    def draw_string(self, string, pos, colour=(255, 0, 0), absolute=True):
        """
        Draws the given string to the screen

        :param absolute: If False, it is drawn in the world, otherwise on the screen
        """
        surface = self.font.render(string, 1, colour)
        self._window.blit(surface, self.camera.apply(pos) if not absolute else pos)

    def blit(self, surface, pos=(0, 0), area=None):
        """
        Blits the given surface onto the screen at the given position
        """
        self._window.blit(surface, pos, area)

    def shake_camera(self, time=0.2, force=5):
        if self.camera:
            self.camera.shaker.shake(time, force)


class Camera:
    """
    Allows viewport scrolling
    """

    class Shaker:
        def __init__(self, camera):
            self.transform = camera.transform
            self.active = False
            self._gen = None

        def shake(self, time, force):
            if self.active:
                return

            self.active = True
            self._gen = self._create_gen(force, time)

        def _create_gen(self, force, time):
            count = int(time / DELTA)
            offsets = [(random.uniform(-force, force), random.uniform(-force, force)) for _ in xrange(count)]
            camera_pos = self.transform.as_tuple()

            for o in offsets:
                time -= DELTA
                if time < 0:
                    break
                yield map(operator.add, o, camera_pos)
            yield camera_pos

        def tick(self):
            if not self.active:
                return

            pos = next(self._gen, 0)

            if pos == 0:
                self._gen = None
                self.active = False

            else:
                self.transform.set(pos)

    def __init__(self, world, speed=2, target_entity=None):
        self.view_size = WINDOW_SIZE
        self.transform = util.Transform()
        self.velocity = Vec2d(0, 0)
        self.speed = speed
        self._target_entity = target_entity
        self._target_position = None
        self.shaker = Camera.Shaker(self)

        self.world = None
        self.world_dimensions = None
        self.boundaries = None
        self.update_boundaries(world)

    def tick(self):
        """
        Gradually centres the target on screen, without leaving the world boundaries
        """
        if self.shaker.active:
            self.shaker.tick()
            return

        # update target position
        self._update_target_position()

        if not self._target_position:
            return

        v = self._direction_to_target(self._target_position)

        if v.get_length_sqrd() < TILE_SIZE_SQRD / 2:
            return

        self.velocity = self.speed * v
        self.move_camera()

    def _update_target_position(self):
        """
        Updates target position to the currently tracked entity's position
        """
        if self._target_entity:
            self._target_position = self._target_entity.transform.as_tuple()

    def move_camera(self):
        """
        Called per frame, and updates the camera's position
        """
        self.transform += self.velocity * DELTA
        self._check_boundaries()

    def is_visible(self, position):
        return self.transform.x <= position[0] < self.transform.x + self.view_size[0] and \
               self.transform.y <= position[1] < self.transform.y + self.view_size[1]

    def _check_boundaries(self):
        """
        Makes sure the camera does not move outside of the world's boundaries
        """
        self.transform.x = max(self.boundaries[0], self.transform.x)
        self.transform.y = max(self.boundaries[1], self.transform.y)
        self.transform.x = min(self.boundaries[2], self.transform.x)
        self.transform.y = min(self.boundaries[3], self.transform.y)

    def centre(self, target_position=None):
        """
        Centres the target position immediately

        :param target_position: If None, then the current target
        """

        if not target_position:
            self._update_target_position()
            if not self._target_position:
                return
            target_position = self._target_position

        self.transform += self._direction_to_target(target_position)
        self.velocity.zero()
        self._check_boundaries()

    def _direction_to_target(self, pos):
        """
        :return: Vector from centre to given position
        """
        camera_centre = Vec2d(self.transform.x + self.view_size[0] / 2, self.transform.y + self.view_size[1] / 2)
        target_centre = Vec2d(pos)
        return target_centre - camera_centre

    def apply_rect(self, rect):
        """
        Applies camera offset to a rectangle

        :param rect: The rectangle to draw
        """
        # :param rect: Either a util.Rect or a tuple ((x, y), (w, h))
        if not isinstance(rect, util.Rect):
            rect = rect[0]
        else:
            rect = rect.x, rect.y
        return self.apply(rect)

    def apply(self, tup):
        """
        :return: Point with camera offset applied
        """
        return tup[0] - self.transform.x, tup[1] - self.transform.y

    def update_boundaries(self, world):
        """
        Updates the boundaries to that of the given world
        """
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
            if isinstance(value, tuple):
                self._target_position = value
                self._target_entity = None
            else:
                self._target_entity = value
                self._target_world = value.world if value is not None else None
                self._target_position = None


class Speed:
    VEHICLE_MIN = 200
    VEHICLE_MAX = 400
    VEHICLE_DAMAGE = VEHICLE_MIN / 2
    VEHICLE_KILL = VEHICLE_MAX / 2

    HUMAN_MIN = 80
    HUMAN_FAST = 100
    HUMAN_MAX = 180

    CAMERA_MIN = 220
    CAMERA_FAST = 450

    WTF_DEBUG = 800


class Direction:
    NORTH = 0
    WEST = 1
    SOUTH = 2
    EAST = 3

    VALUES = [NORTH, WEST, SOUTH, EAST]

    @staticmethod
    def random():
        """
        :return: Random direction
        """
        return random.choice(Direction.VALUES)

    @staticmethod
    def opposite(direction):
        """
        :return: Opposite of given direction
        """
        return (direction + 2) % 4

    @staticmethod
    def are_perpendicular(d1, d2):
        return abs(d1 - d2) % 2 != 0

    @staticmethod
    def perpendiculars(direction):
        yield (direction - 1) % 4
        yield (direction + 1) % 4

    @staticmethod
    def is_horizontal(direction):
        return direction in (Direction.EAST, Direction.WEST)

    @staticmethod
    def is_vertical(direction):
        return direction in (Direction.NORTH, Direction.SOUTH)

    @staticmethod
    def delta_to_direction(delta, vertical):
        """
        :param delta: integer
        :param vertical: True if in y axis, otherwise False
        """
        if vertical:
            return Direction.SOUTH if delta > 0 else Direction.NORTH
        else:
            return Direction.EAST if delta > 0 else Direction.WEST

    @staticmethod
    def is_negative(direction):
        return direction == Direction.NORTH or direction == Direction.WEST


class EntityType:
    HUMAN = 0
    VEHICLE = 1
    ALL = 2

    @staticmethod
    def parse_string(s):
        """
        :return: EntityType referred to by given string
        """
        s = s.upper()
        for prop, val in EntityType.__dict__.items():
            if s == prop and isinstance(val, int):
                return val
        return EntityType.ALL


class Input:
    UP = pygame.K_w
    LEFT = pygame.K_a
    DOWN = pygame.K_s
    RIGHT = pygame.K_d
    BOOST = pygame.K_LSHIFT

    BRAKE = pygame.K_SPACE

    INTERACT = pygame.K_e
    RELEASE_CONTROL = pygame.K_TAB
    QUIT = pygame.K_ESCAPE

    DIRECTIONAL_KEYS = [UP, LEFT, DOWN, RIGHT]


STATEMANAGER = None
RUNNING = True
SCREEN = GameScreen()
DELTA = 0
LAST_DELTA = 0
WINDOW_SIZE = (640, 640)
WINDOW_CENTRE = (WINDOW_SIZE[0] / 2, WINDOW_SIZE[1] / 2)

TILESET_RESOLUTION = 16
TILE_SIZE = 32
TILE_DIMENSION = (TILE_SIZE, TILE_SIZE)
TILE_SIZE_SQRD = TILE_SIZE ** 2
HALF_TILE_SIZE = TILE_SIZE / 2, TILE_SIZE / 2

PASSENGER_SCALE = 0.6