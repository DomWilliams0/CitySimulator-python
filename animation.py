import logging
import random
import os
import copy

import pygame

import constants
import util


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
        :return:
        """
        self.nickname = path.split(os.sep)[-1][:-4] if not nickname else nickname
        self.sprites = [[] for _ in xrange(height)]
        self.sheet = pygame.image.load(path).convert_alpha()
        self.type = animation_type
        self.length = length

        HumanSpriteSheet.LOADED[self.nickname] = self
        logging.debug("Spritesheet loaded: [%s]" % self.nickname)

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
    logging.error("A random spritesheet of type %s could not be found!" % (util.get_enum_name(constants.EntityType, animation_type)))
    return None


def load_all():
    """
    Loads all spritesheets in the sprites directory
    """
    # raise NotImplementedError("Load them manually now, learn to glob another day")
    import os

    for root, dirs, files in os.walk(util.get_relative_path("sprites")):
        d = root.split(os.sep)[-1]
        for f in files:
            if f[-3:] != "png":
                continue
            path = os.path.join(root, f)

            # humans
            if d == "humans":
                HumanSpriteSheet(path, (128, 128), (32, 32), 4)

            if d == "vehicles":
                VehicleSpriteSheet(path, (128, 128), (32, 32), (64, 32), 4)
    logging.info("Loaded %d sprites" % len(BaseSpriteSheet.LOADED))


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


class VehicleSpriteSheet(BaseSpriteSheet):
    """
    Spritsheet for vehicles
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
                pixels = pygame.PixelArray(sprite)
                for x in xrange(sprite.get_width()):
                    for y in xrange(sprite.get_height()):
                        pix = sprite.unmap_rgb(pixels[x, y])
                        if pix[3] != 255 and pix[3] != 0:
                            mixed = (util.mix_colours([pix[3]] * 3, colour))
                            pixels[x, y] = sprite.map_rgb(mixed)


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
                self.turn(self.sequence_index, starting_index=1)  # todo make sure first frame in all vehicle animations are stationery
            sprite, self.current_frame = self.walk_gen.next()
        else:
            sprite = self.spritesheet.sprites[self.sequence_index][0]

        speed = self._get_speed()
        # if speed != self.last_speed and speed % 1 == 0:
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
        :param index: Sequence index ie Entity.{1}
        :param starting_index: Starting frame in sequence, can be -1 for current frame
        """
        self.sequence_index = index
        self.walk_gen = self.spritesheet.get_sequence(self, index, starting_index)

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
        self.was_horizontal = self._is_horizontal(entity.direction)
        self.last_direction = entity.direction

    def _is_horizontal(self, direction):
        """
        :return: True if the given direction is east/west, otherwise False
        """
        return direction in constants.Direction.HORIZONTALS

    def turn(self, index, starting_index=0, speed=-1):
        try:
            hor = self._is_horizontal(index)
            if hor != self.was_horizontal:
                if hor:
                    self.entity.aabb.width *= 2
                    self.entity.rect.width *= 2
                else:
                    self.entity.aabb.width /= 2
                    self.entity.rect.width /= 2

                    # can be exploited to move super fast :(
                    # if self.last_direction == constants.Direction.EAST:
                    # self.entity.aabb.x += self.entity.aabb.width

            self.was_horizontal = hor
            self.last_direction = self.entity.direction

        except AttributeError:
            pass
        HumanAnimator.turn(self, index, starting_index)

    def get_arrow_position(self):
        pos = HumanAnimator.get_arrow_position(self)
        if self.entity.direction == constants.Direction.EAST:
            pos = pos[0] + self.entity.aabb.width / 4, pos[1]

        return pos