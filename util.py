import os
import random

from pygame.rect import Rect as pygame_Rect

import constants
import world as world_module


def get_relative_path(path):
    """
    :param path: Relative path in resources dir, separated by /
    :return: Absolute path to resource
    """
    split = path.split(os.sep)
    return os.path.join(os.path.dirname(__file__), "res", *split)


def _find_resource(name):
    for root, dirs, files in os.walk(get_relative_path(".")):
        for f in files:
            if f.startswith(name):
                return os.path.join(root, f)
    raise IOError("Could not find '%s' in resources" % name)


def get_resource_path(name):
    """
    Convenience function for searching for the given file name in 'res'
    """
    return _find_resource(name)


def is_almost(a, b, limit=1):
    return abs(a - b) < limit


def run_once(f):
    """
    Decorator to make sure the function is run only once
    """

    def func(*args, **kwargs):
        if not func.has_run:
            func.has_run = True
            return f(*args, **kwargs)

    func.has_run = False
    return func


def round_to_tile_size(x):
    return round_to_multiple(x, constants.TILE_SIZE)


def round_to_multiple(x, multiple):
    return int(multiple * round(float(x) / multiple))


def pixel_to_tile(pos):
    return pos[0] / constants.TILE_SIZE, pos[1] / constants.TILE_SIZE


def tile_to_pixel(pos):
    return pos[0] * constants.TILE_SIZE, pos[1] * constants.TILE_SIZE


def parse_orientation(char):
    if char == "N":
        return constants.Direction.NORTH
    if char == "E":
        return constants.Direction.EAST
    if char == "W":
        return constants.Direction.WEST
    if char == "S":
        return constants.Direction.SOUTH
    if char == "R":
        return constants.Direction.random()
    return constants.Direction.SOUTH  # default


def debug_block(pos, world):
    print("----")
    pos = map(int, pos)
    print pos, world.get_solid_block(*pixel_to_tile(pos))
    for l in world.layers.values():
        block = world.get_block(*pixel_to_tile(pos), layer=l.name)
        if not block:
            continue

        if l.name == "rects":
            s = str(block)
        else:
            s = "%s : %s : %s : %s" % (world_module.BlockType.get_type_name(block.blocktype).ljust(10), str(block), get_class(block), hex(id(block)))
        print("%s -> %s" % (l.name.ljust(12), s))
    print("----")


def get_class(o):
    return str(o.__class__).split(".")[1]


def distance_sqrd(p1, p2):
    return (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2


def mix_colours(c1, c2, ensure_alpha=True):
    mixed = [(a + b) / 2 for a, b in zip(c1, c2)]
    if ensure_alpha and len(mixed) == 3:
        mixed.append(255)
    return mixed


def random_colour(alpha=255):
    return random.randrange(127) + 127, random.randrange(127) + 127, random.randrange(127) + 127, alpha


class Rect:
    def __init__(self, *args):
        l = len(args)
        if l == 2 and isinstance(args[0], tuple):  # ((,), (,))
            self._init(*self._tuple_from_arg(args))
        elif l == 4:  # (,,,)
            self._init(*args)
        elif l == 1:
            r = args[0]
            if isinstance(r, Rect):
                self._init(r.x, r.y, r.width, r.height)
            elif isinstance(r, pygame_Rect):
                self._init(*r)
        else:
            raise TypeError("Invalid argument")

    def _init(self, x, y, w, h):
        self.x = x
        self.y = y
        self.width = w
        self.height = h

    def __getattr__(self, key):
        if key == 'topleft':
            return self.x, self.y
        elif key == 'bottomleft':
            return self.x, self.y + self.height
        elif key == 'topright':
            return self.x + self.width, self.y
        elif key == 'bottomright':
            return self.x + self.width, self.y + self.height
        elif key == 'right':
            return self.x + self.width
        elif key == 'midtop':
            return self.x + self.width / 2, self.y
        elif key == 'center':
            return self.x + self.width / 2, self.y + self.height / 2
        else:
            return self.__dict__[key]

    def __setattr__(self, key, value):
        if key == 'center':
            self.x = value[0] - self.width / 2
            self.y = value[1] - self.height / 2
        else:
            self.__dict__[key] = value

    def __getitem__(self, key):
        return (self.x, self.y, self.width, self.height)[key]

    def __len__(self):
        return 4

    def add_vector(self, vec2d):
        setattr(self, "center", (self.center[0] + vec2d.x, self.center[1] + vec2d.y))

    def colliderect(self, r):
        r = self._tuple_from_arg(r)
        return self.x + self.width > r[0] and r[0] + r[2] > self.x and self.y + self.height > r[1] and r[1] + r[3] > self.y

    def inflate(self, x, y):
        self.x -= x / 2
        self.y -= y / 2
        self.width += x
        self.height += y

    def to_tuple(self):
        return self.x, self.y, self.width, self.height

    def _tuple_from_arg(self, arg):
        l = len(arg)
        if l == 2:
            return arg[0][0], arg[0][1], arg[1][0], arg[1][1]
        elif l == 1 and isinstance(arg, Rect):
            return arg.to_tuple()
        else:
            return arg

    def __str__(self):
        return "Rect{(%.1f, %.1f), (%.1f, %.1f)}" % (self.x, self.y, self.width, self.height)


class Stack:
    def __init__(self):
        self._data = []
        self.top = None

    def pop(self):
        pop = self._data.pop()
        self._set_top()
        return pop

    def remove_item(self, x):
        self._data.remove(x)
        if x == self.top:
            self._set_top()

    def push(self, x):
        self._data.append(x)
        self.top = x

    def __repr__(self):
        return str(self._data)

    def _set_top(self):
        try:
            self.top = self._data[-1]
        except IndexError:
            self.top = None
