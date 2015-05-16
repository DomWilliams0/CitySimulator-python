import random
import os
import copy

import pygame

import constants
import util

HUMAN_DIMENSION = (32, 32)
VEHICLE_DIMENSION = (64, 32)


def clone(sheet):
    """
    Clones the given spritesheet (and all frame surfaces of all sequences)
    """

    sheet_copy = copy.deepcopy(sheet)
    for seqi in xrange(len(sheet.sprites)):
        sequence = sheet.sprites[seqi]
        for spritei in xrange(len(sequence)):
            sprite = sequence[spritei]
            sprite_copy = sprite.copy()
            sheet_copy.sprites[seqi][spritei] = sprite_copy

    sheet_copy.sheet = sheet.sheet.copy()
    return sheet_copy


class BaseSpriteSheet:
    """
    Base sprite sheet that contains animation sequences
    """
    LOADED = {}

    def __init__(self, path, height, length, animation_type, nickname=None):
        """
        :param path: File path
        :param height: Height of spritesheet, and hence number of sequences
        :param length: The frame count of each sequence
        :param animation_type: EntityType of animation
        :param nickname: Optional nickname, otherwise the (trimmed) filename
        """
        self.nickname = path.split(os.sep)[-1][:-4] if not nickname else nickname
        self.sprites = [[] for _ in xrange(height)]
        self.sheet = pygame.image.load(path).convert_alpha()
        self.type = animation_type
        self.length = length

        HumanSpriteSheet.LOADED[self.nickname] = self
        constants.LOGGER.debug("Loaded spritesheet %s" % self.nickname)

    def _load_sprites(self, sheet_dimensions, sprite_dimensions, row_count, start_y):
        """
        Loads the sprites into sequences

        :param sheet_dimensions: The dimensions of the spritesheet
        :param sprite_dimensions: The dimensions of each frame
        :param row_count: The number of rows to load
        :param start_y: The row to begin at
        """
        height = sheet_dimensions[1] / sprite_dimensions[1]

        rows = 0
        rect = util.Rect((0, start_y * sprite_dimensions[1]), sprite_dimensions)

        for y in xrange(start_y, height):
            for _ in xrange(self.length):
                sprite = pygame.Surface(sprite_dimensions, 0, self.sheet).convert_alpha()
                sprite.blit(self.sheet, (0, 0), rect.as_tuple())
                self.sprites[y].append(sprite)
                rect.x += sprite_dimensions[0]

            rows += 1
            if rows == row_count:
                return
            rect.y += sprite_dimensions[1]
            rect.x = 0

    def get_sequence(self, animator, index, starting_index=0):
        """
        :param animator: The animator
        :param index: Animation sequence index
        :param starting_index: Starting frame in sequence
        :return: A generator function that loops the animation
        """
        sequence = self.sprites[index]
        i = starting_index
        delta = 0
        seq_len = len(sequence)
        while True:
            if i == seq_len:
                i = 0
            yield sequence[i], i
            delta += constants.DELTA
            if delta >= animator.animation_step:
                delta = 0
                i += 1

    def _rearrange_directional_sprites(self):
        """
        Rearranges animations given in SWEN to NWSE, to remain consistent with Direction
        """
        good_order = (3, 1, 0, 2)
        self.sprites = [self.sprites[i] for i in good_order]


def get(nickname):
    """
    If the spritesheet is already loaded, returns its instance, otherwise None
    """
    return BaseSpriteSheet.LOADED.get(nickname)


def get_random(animation_type=None):
    """
    :param animation_type: If None, all types are chosen from
    :return: Random spritesheet of the given entitytype
    """
    timeout = len(BaseSpriteSheet.LOADED) * 100
    for _ in xrange(timeout):
        x = random.choice(BaseSpriteSheet.LOADED.values())
        if x.type == animation_type or animation_type is None:
            return x
    constants.LOGGER.error("A random spritesheet of type %s could not be found!" % (util.get_enum_name(constants.EntityType, animation_type)))
    return None


def load(entitytype, filepath):
    if entitytype == constants.EntityType.HUMAN:
        HumanSpriteSheet(filepath, (128, 128), HUMAN_DIMENSION, 4)

    elif entitytype == constants.EntityType.VEHICLE:
        VehicleSpriteSheet(filepath, (128, 128), HUMAN_DIMENSION, VEHICLE_DIMENSION, 4)

    else:
        raise IOError("Could not load spritesheet at '%s'" % filepath)


class HumanSpriteSheet(BaseSpriteSheet):
    """
    Spritesheet for humans
    """

    def __init__(self, path, sheet_dimensions, sprite_dimensions, length):
        """
        :param path: Absolute path
        :param sheet_dimensions: The pixel dimensions of the spritesheet ie (128, 128)
        :param sprite_dimensions: The pixel dimensions of each sprite ie (32, 32)z
        """
        BaseSpriteSheet.__init__(self, path, 4, length, constants.EntityType.HUMAN)
        self._load_sprites(sheet_dimensions, sprite_dimensions, -1, 0)
        self._rearrange_directional_sprites()

        def scale_dimensions(surface, scale):
            return int(surface.get_width() * scale), int(surface.get_height() * scale)

        blue = (51, 148, 213)
        self.small_freeze_frames = [pygame.transform.scale(s[0], scale_dimensions(s[0], constants.PASSENGER_SCALE)) for s in self.sprites]
        for s in self.small_freeze_frames:
            util.blend_pixels(s, lambda p: p[3] > 0, lambda p: util.mix_colours(p, blue))


class VehicleSpriteSheet(BaseSpriteSheet):
    """
    Spritesheet for vehicles
    """

    def __init__(self, path, sheet_dimensions, starting_dimensions, ending_dimensions, length):
        """
        :param path: Absolute path
        :param sheet_dimensions: The pixel dimensions of the spritesheet ie (128, 128)
        :param starting_dimensions: Beginning sprite dimensions
        :param ending_dimensions: Ending sprite dimensions (in other sequences)
        """
        BaseSpriteSheet.__init__(self, path, 4, length, constants.EntityType.VEHICLE)
        self._load_sprites(sheet_dimensions, starting_dimensions, 1, 0)
        self._load_sprites(sheet_dimensions, ending_dimensions, 2, 1)
        self._load_sprites(sheet_dimensions, starting_dimensions, 1, 3)
        self._rearrange_directional_sprites()

    def set_colour(self, colour):
        """
        Sets the car's colour to the given colour
        """
        for seq in self.sprites:
            for sprite in seq:
                util.blend_pixels(sprite, lambda p: all(map(lambda p: p == 127, p[:3])), lambda p: util.mix_colours([p[3]] * 3, colour))


class HumanAnimator:
    """
    Handles drawing and animation of an entity
    """

    def __init__(self, entity, spritesheet):
        self.entity = entity
        self.spritesheet = spritesheet

        self.animation_step = 0
        self.sequence_index = 0
        self.walk_gen = None
        self.current_frame = 0
        self.turn(0)

        self.was_moving = self.entity.is_moving()
        self.last_speed = self._get_speed()

    def _get_speed(self):
        """
        :return: absolute (non-directional) speed of the entity
        """
        v = self.entity.velocity
        if v[0] != 0:
            return abs(v[0])
        return abs(v[1])

    def tick(self):
        """
        Advances animation and draws to screen
        """
        sprite = self._next_sprite()
        self._render(sprite)

    def _next_sprite(self):
        """
        :return: The next sprite in the current animation sequence
        """
        moving = self.entity.is_moving()
        if moving:
            if not self.was_moving:
                self.turn(self.sequence_index, starting_index=1)
            sprite, self.current_frame = self.walk_gen.next()
        else:
            sprite = self.spritesheet.sprites[self.sequence_index][0]

        speed = self._get_speed()
        if speed != self.last_speed:
            self.last_speed = speed
            self.animation_step = 18.0 / speed if speed else 0

        self.was_moving = moving
        return sprite

    def _render(self, sprite):
        """
        Renders the given sprite to the screen
        """
        constants.SCREEN.draw_sprite(sprite, self.entity.rect)

    def turn(self, index, starting_index=0):
        """
        Updates animation generator

        :param index: Sequence index
        :param starting_index: Starting frame in sequence
        """
        self.sequence_index = index
        self.walk_gen = self.spritesheet.get_sequence(self, index, starting_index)
        # self.current_frame = starting_index

    def halt(self):
        self.current_frame = 0

    def get_arrow_position(self):
        """
        :return: The position at which to render the player controller arrow
        """
        return self.entity.aabb.x + (self.entity.aabb.width / 4.0), self.entity.aabb.y - self.entity.aabb.height * 1.8


class VehicleAnimator(HumanAnimator):
    """
    Animator for vehicles
    """

    def __init__(self, entity, spritesheet):
        HumanAnimator.__init__(self, entity, spritesheet)
        self.was_horizontal = constants.Direction.is_horizontal(entity.direction)
        self.last_direction = entity.direction

    def turn(self, index, starting_index=0, speed=-1):
        try:
            hor = constants.Direction.is_horizontal(index)

            # adjust aabb
            direction = self.entity.direction
            if hor != self.was_horizontal:
                if hor:
                    self.entity.aabb.width *= 2
                    self.entity.rect.width *= 2
                else:
                    self.entity.aabb.width /= 2
                    self.entity.rect.width /= 2

                if self.last_direction == constants.Direction.EAST:
                    self.entity.aabb.x += self.entity.aabb.width
                elif direction == constants.Direction.EAST:
                    self.entity.aabb.x -= self.entity.aabb.width / 2

            self.was_horizontal = hor
            self.last_direction = direction

        except AttributeError:
            pass
        HumanAnimator.turn(self, index, starting_index)

    def get_arrow_position(self):
        pos = HumanAnimator.get_arrow_position(self)
        if self.entity.direction == constants.Direction.EAST:
            pos = pos[0] + self.entity.aabb.width / 4, pos[1]

        return pos