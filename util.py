import os
import random
import operator

from pygame.rect import Rect as pygame_Rect

import constants
import world as world_module


_SURROUNDING_OFFSETS = (0, -1), (-1, 0), (1, 0), (0, 1)


def get_relative_path(path):
    """
    :param path: Relative path in resources dir, separated by /
    :return: Absolute path to resource
    """
    split = path.split(os.sep)
    return os.path.join(os.path.dirname(__file__), "res", *split)


# todo doesn't search recursively
def get_resource_path(name):
    """
    Convenience function for searching for the given file name in 'res'
    """
    for root, dirs, files in os.walk(get_relative_path(".")):
        for f in files:
            if f.startswith(name):
                return os.path.join(root, f)
    raise IOError("Could not find '%s' in resources" % name)


def is_almost(a, b, limit=1):
    """
    :return: True if the difference between a and b is within the given limit
    """
    return abs(a - b) < limit


def round_to_tile_size(x):
    """
    :return: Coordinate rounded to tile size
    """
    return round_to_multiple(x, constants.TILE_SIZE)


def round_to_multiple(x, multiple):
    """
    :return: x rounded to the nearest multiple of 'multiple'
    """
    return int(multiple * round(float(x) / multiple))


def pixel_to_tile(pos):
    """
    :return: The given pixel position converted to the corresponding tile position
    """
    return pos[0] / constants.TILE_SIZE, pos[1] / constants.TILE_SIZE


def tile_to_pixel(pos):
    """
    :return: The given tile position converted to the corresponding pixel position
    """
    return pos[0] * constants.TILE_SIZE, pos[1] * constants.TILE_SIZE


def parse_orientation(char):
    """
    :param char: NESW, or R for random
    :return: The corresponding direction, otherwise south
    """
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
    """
    Prints debug info about the given position
    """
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
    """
    :return: Prettified class name of given object
    """
    return str(o.__class__).split(".")[1]


def distance_sqrd(p1, p2):
    """
    :return: Square distance between given points
    """
    return (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2


def mix_colours(c1, c2, ensure_alpha=True):
    """
    :param ensure_alpha: If True, ensures that the returned colour is RGBA
    :return: Mix of the given 2 colours
    """
    mixed = [(a + b) / 2 for a, b in zip(c1, c2)]
    if ensure_alpha and len(mixed) == 3:
        mixed.append(255)
    return mixed


def get_surrounding_offsets():
    """
    :return: 4 relative offsets
    """
    return _SURROUNDING_OFFSETS


def modify_attr(obj, attribute, func):
    """
    Modify current value of given attribute (ie +=)
    :param obj: Object
    :param attribute: Attribute name
    :param func: Function with single argument: old value of attribute
    """
    setattr(obj, attribute, func(getattr(obj, attribute)))


def get_enum_name(enum_cls, value):
    """
    Debug function
    :return: Enum name as string, instead of just an integer
    """
    for k, v in enum_cls.__dict__.items():
        if not k.startswith("_") and v == value:
            return k
    return None


def find_difference(pos1, pos2, absolute):
    """
    :param absolute:
    :return: If absolute, sorted absolute difference [0, 1] for example, otherwise the raw difference
    """
    diff = map(operator.sub, pos1, pos2)
    if absolute:
        return sorted(map(abs, diff))
    else:
        return diff


def add_direction(position, direction):
    """
    :return: Position modified by the given direction
    """
    delta = _SURROUNDING_OFFSETS[direction]
    return map(operator.add, position, delta)


class Rect:
    """
    Rectangle that supports floating point numbers
    """
    def __init__(self, *args):
        """
        :param args: ((x, y), (w, h)) or (x, y, w, h) or another Rect
        """
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
            if value < 0 and (key == 'width' or key == 'height'):
                if key[0] == 'w':
                    self.x += value
                else:
                    self.y += value
                value *= -1
            self.__dict__[key] = value

    def __getitem__(self, key):
        return (self.x, self.y, self.width, self.height)[key]

    def __len__(self):
        return 4

    def colliderect(self, r):
        r = self._tuple_from_arg(r)
        return self.x + self.width > r[0] and r[0] + r[2] > self.x and self.y + self.height > r[1] and r[1] + r[3] > self.y

    def collidepoint(self, p):
        return self.x <= p[0] < self.x + self.width and self.y <= p[1] < self.y + self.height

    def area(self):
        return self.width * self.height

    def inflate(self, x, y):
        """
        :return: Expands evenly by given amounts
        """
        self.x -= x / 2
        self.y -= y / 2
        self.width += x
        self.height += y

    def as_tuple(self):
        """
        :return: Tuple of x, y, width, height
        """
        return self.x, self.y, self.width, self.height

    def _tuple_from_arg(self, arg):
        l = len(arg)
        if l == 2:
            return arg[0][0], arg[0][1], arg[1][0], arg[1][1]
        elif l == 1 and isinstance(arg, Rect):
            return arg.as_tuple()
        else:
            return arg

    def __str__(self):
        return "Rect{(%.1f, %.1f), (%.1f, %.1f)}" % (self.x, self.y, self.width, self.height)

    __repr__ = __str__


class Stack:
    """
    Stack that makes keeping track of top element easy
    """
    def __init__(self, *initvalues):
        self._data = []
        self.top = None

        for v in initvalues:
            self.push(v)

    def __nonzero__(self):
        return bool(self._data)

    def pop(self):
        """
        :return: Current top value, None if empty
        """
        try:
            pop = self._data.pop()
        except IndexError:
            pop = None
        self._set_top()
        return pop

    def clear(self):
        """
        Pops all values
        """
        self._data = []
        self.top = None

    def remove_item(self, x):
        """
        Removes the given item from the stack if it exists in it, otherwise does nothing
        """
        try:
            self._data.remove(x)
            if x == self.top:
                self._set_top()
        except ValueError:
            pass

    def push(self, x):
        """
        Pushes the given value onto the top of the stack
        """
        self._data.append(x)
        self.top = x

    def __repr__(self):
        return str(self._data)

    def _set_top(self):
        try:
            self.top = self._data[-1]
        except IndexError:
            self.top = None


class TimeTicker:
    """
    Ticks independantly of framerate
    """
    def __init__(self, limit_or_range_range):
        """
        :param limit_or_range_range: Either constant seconds, or a (min, max) range for random times
        """

        def reset_gen():
            if isinstance(limit_or_range_range, tuple):
                while True:
                    yield random.uniform(*limit_or_range_range)
            else:
                while True:
                    yield limit_or_range_range

        self._reset = reset_gen()
        self.time = 0
        self.limit = 0
        self.reset()

    def tick(self):
        """
        If target time has been reached, the ticker is reset
        :return: True if the target time has been reached, otherwise false
        """
        self.time += constants.DELTA
        complete = self.time >= self.limit
        if complete:
            self.reset()
        return complete

    def reset(self):
        """
        Resets the ticker back to 0
        """
        self.time = 0
        self.limit = next(self._reset)


class Transform:
    """
    Simple x, y coordinate container
    """
    def __init__(self):
        self.x = 0.0
        self.y = 0.0

    def set(self, pos):
        """
        Sets the coordinates to the given position
        """
        self.x, self.y = pos

    def as_tuple(self):
        """
        :return: x, y
        """
        return self.x, self.y

    def __add__(self, other):
        self.x += other[0]
        self.y += other[1]
        return self

    def __iter__(self):
        yield self.x
        yield self.y

    def __repr__(self):
        return "Transform(%d, %d)" % (self.x, self.y)