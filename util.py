import colorsys
from math import floor, sqrt
import os
import random
import operator
import re

import pygame
from pygame.rect import Rect as pygame_Rect

import constants
import world as world_module

SURROUNDING_OFFSETS = (0, -1), (-1, 0), (0, 1), (1, 0)
SURROUNDING_DIAGONAL_OFFSETS = (0, 0), (-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)
__FILE_SPLIT_PATTERN = re.compile(r"[\\//]")


def get_relative_path(path, directory="res"):
    """
    :param path: Relative path in given dir, separated by / or \
    :return: Absolute path to resource
    """

    split = __FILE_SPLIT_PATTERN.split(path)
    d = os.path.join(*__FILE_SPLIT_PATTERN.split(directory))
    return os.path.join(os.path.dirname(__file__), d, *split)


def search_for_file(filename, directory="res"):
    for root, dirnames, filenames in os.walk(directory):
        for filename in (f for f in filenames if f == filename):
            return os.path.join(root, filename)
    return None


def get_monitor_resolution():
    import Tkinter

    root = Tkinter.Tk()
    res = root.winfo_screenwidth(), root.winfo_screenheight()
    root.destroy()
    return res


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


def round_down_to_multiple(x, multiple):
    """
    :return: x rounded down to the nearest multiple of 'multiple'
    """
    return int(multiple * floor((float(x) / multiple)))


def round_to_tile(pixel_pos):
    """
    :return: The given pixel position rounded to the nearest tile boundary (still as a pixel position)
    """
    return tuple(map(lambda x: round_to_tile_size(x), pixel_pos))


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


def intify(x):
    """
    Casts all elements to int
    """
    return map(int, x)


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


def distance(p1, p2):
    return sqrt(distance_sqrd(p1, p2))


def midpoint(p1, p2):
    return map(lambda x, y: (x + y) / 2, p1, p2)


def clamp(value, min_value, max_value):
    if value < min_value:
        value = min_value
    elif value > max_value:
        value = max_value
    return value


def random_colour(alpha=255):
    """
    :return: A (hopefully) pretty random colour
    """
    high = random.randrange(127) + 127
    med = random.randrange(100) + 50
    low = random.randrange(50)
    c = [high, med, low]
    random.shuffle(c)
    c.append(alpha)
    return c


def mix_colours(c1, c2, new_alpha=-1):
    """
    :return: Mix of the given 2 colours
    """
    mixed = [(a + b) / 2 for a, b in zip(c1, c2)]

    # add alpha
    if len(mixed) == 3:
        mixed.append(255)

    if new_alpha > 0:
        mixed[3] = new_alpha

    return mixed


def rgb_from_string(s):
    return [int(c.strip()) for c in s.split(",")]


def blend_pixels(sprite, pixel_predicate, pixel_func):
    pixels = pygame.PixelArray(sprite)
    for x in xrange(sprite.get_width()):
        for y in xrange(sprite.get_height()):
            pix = sprite.unmap_rgb(pixels[x, y])
            if pixel_predicate(pix):
                pixels[x, y] = tuple(pixel_func(pix))
    del pixels


def convert_to_range(old_range, new_range, value):
    old_min, old_max = old_range
    new_min, new_max = new_range
    if value == old_min:
        return new_min
    return (float(value - old_min) / (old_max - old_min)) * (new_max - new_min) + new_min


def convert_colour(c, to_hsv):
    """
    :param c: Colour, either in 0-1 or 0-255
    :param to_hsv: True for rgb->hsv, False for hsv->rgb
    """
    if to_hsv:
        c = map(lambda x: convert_to_range((0, 255), (0, 1), x), c)

    func = colorsys.rgb_to_hsv if to_hsv else colorsys.hsv_to_rgb
    c = func(*c)

    if not to_hsv:
        c = map(lambda x: convert_to_range((0, 1), (0, 255), x), c)

    return c


def lerp_colours(c1, c2, delta):
    """
    :param delta: 0 to 1
    """

    if delta <= 0.:
        return c1
    if delta >= 1.:
        return c2

    hsv0, hsv1 = map(lambda c: convert_colour(c, True), (c1, c2))

    zipped = zip(hsv0, hsv1)
    hsv = map(lambda (chan0, chan1): chan0 + (chan1 - chan0) * delta, zipped)

    return convert_colour(hsv, False)


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
    :return: If absolute, sorted absolute difference [0, 1] for example, otherwise the raw difference
    """
    diff = map(operator.sub, pos1, pos2)
    if absolute:
        return sorted(map(abs, diff))
    else:
        return diff


def add_direction(position, direction, distance_delta=1):
    """
    :return: Position modified by the given direction
    """
    delta = map(lambda x: x * distance_delta, SURROUNDING_OFFSETS[direction])
    return map(operator.add, position, delta)


def set_random_pop(s):
    """
    Pops a random element from the given set
    """
    index = random.randrange(0, len(s))
    i = 0
    for e in s:
        if i == index:
            s.remove(e)
            return e
        i += 1

    return None


def compare(a, b):
    if a == b:
        return 0
    return -1 if a < b else 1


def insert_sort(collection, compare):
    for i in xrange(1, len(collection)):
        j = i
        c = collection[j]
        while j > 0 > compare(c, collection[j - 1]):
            collection[j] = collection[j - 1]
            j -= 1
        collection[j] = c


class Rect:
    """
    Rectangle that supports floating point numbers
    """

    def __init__(self, *args):
        """
        :param args: ((x, y), (w, h)) or (x, y, w, h) or another Rect
        """
        l = len(args)
        if l == 2:
            if isinstance(args[0], tuple):  # ((,), (,))
                self._init(*self._tuple_from_arg(args))
            else:
                self._init(args[0], args[1], 0, 0)
        elif l == 4:  # (,,,)
            self._init(*args)
        elif l == 1:
            r = args[0]
            if isinstance(r, Rect):
                self._init(r.x, r.y, r.width, r.height)
            elif isinstance(r, pygame_Rect):
                self._init(*r)
            elif isinstance(r, str):
                self._init(*[int(x.strip()) for x in r.split(",")])
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
        elif key == 'centre':
            return self.x + self.width / 2, self.y + self.height / 2
        else:
            return self.__dict__[key]

    def __setattr__(self, key, value):
        if key == 'centre':
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

    def __nonzero__(self):
        return self.as_tuple() != (0, 0, 0, 0)

    def __iter__(self):
        for a in xrange(len(self)):
            yield self[a]

    def __dir__(self):
        return ['x', 'y', 'width', 'height']

    def colliderect(self, r):
        r = self._tuple_from_arg(r)
        return Rect.colliderect_tuples(self.as_tuple(), Rect._tuple_from_arg(r))

    @staticmethod
    def colliderect_tuples(tup0, tup1):
        return tup0[0] + tup0[2] > tup1[0] and tup1[0] + tup1[2] > tup0[0] and tup0[1] + tup0[3] > tup1[1] and tup1[1] + tup1[3] > tup0[1]

    def collidepoint(self, p):
        return self.x <= p[0] < self.x + self.width and self.y <= p[1] < self.y + self.height

    # @staticmethod
    # def get_collision_side(tup0, tup1):
    # """
    # experimental
    # """
    # w = 0.5 * (tup0[2] + tup1[2])
    # h = 0.5 * (tup0[3] + tup1[3])
    # centre = lambda tup: (tup[0] + tup[2] / 2, tup[1] + tup[3] / 2)
    # dx, dy = map(operator.sub, centre(tup0), centre(tup1))
    #
    # if abs(dx) <= w and abs(dy) <= h:
    # wy = w * dy
    # hx = h * dx
    #
    # if wy > hx:
    # if wy > -hx:
    # return "BOTTOM"
    # else:
    # return "LEFT"
    # else:
    # if wy > -hx:
    # return "RIGHT"
    # else:
    # return "TOP"

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
        return self

    def expand(self, direction, delta):
        """
        Expanding by a negative delta in the same direction reverses this operation

        :param direction: Direction to expand in
        :param delta: Amount to expand by
        """
        negative = constants.Direction.is_negative(direction)
        horizontal = constants.Direction.is_horizontal(direction)

        attr = 'width' if horizontal else 'height'

        modify_attr(self, attr, lambda old: old + delta)

        if negative:
            shift = 'x' if horizontal else 'y'
            modify_attr(self, shift, lambda old: old - delta)
        return self

    def to_pixel(self):
        r = Rect(self)
        r.x *= constants.TILE_SIZE
        r.y *= constants.TILE_SIZE
        r.width *= constants.TILE_SIZE
        r.height *= constants.TILE_SIZE
        return r

    def to_tile(self):
        r = Rect(self)
        r.x /= constants.TILE_SIZE
        r.y /= constants.TILE_SIZE
        r.width /= constants.TILE_SIZE
        r.height /= constants.TILE_SIZE
        return r

    def translate(self, xy):
        self.x += xy[0]
        self.y += xy[1]
        return self

    def as_tuple(self):
        """
        :return: Tuple of x, y, width, height
        """
        return self.x, self.y, self.width, self.height

    def as_half_tuple(self):
        """
        :return: Tuple of (x, y), (width, height)
        """
        return (self.x, self.y), (self.width, self.height)

    def size(self):
        """
        :return: Tuple of (width, height)
        """
        return self.width, self.height

    def position(self):
        """
        :return: Tuple of (x, y)
        """
        return self.x, self.y

    @staticmethod
    def _tuple_from_arg(arg):
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


class Heap:
    def __init__(self, compare, size):
        self._comparison = compare
        self._heap = [None] * (size + 1)
        self._n = 1
        self._max = size

    def empty(self):
        return self._n == 1

    def add(self, x):
        if self._n == self._max:
            raise StandardError("Heap is full")

        self._heap[self._n] = x
        self._bubble_up(self._n)
        self._n += 1

    def pop(self):
        self._n -= 1
        self._swap(1, self._n)
        value = self._heap[self._n]
        self._heap[self._n] = None

        self._bubble_down(1)

        return value

    def _bubble_up(self, i):
        if i == 1:
            return

        parent = self._parent(i)
        if self._compare(i, parent) > 0:
            self._swap(i, parent)
            self._bubble_up(parent)

    def _bubble_down(self, i):
        left = self._left(i)
        right = self._right(i)

        # no children
        if left >= self._n:
            return

        # just left
        elif right >= self._n:
            if self._compare(i, left) < 0:
                self._swap(i, left)
                self._bubble_down(left)

        # two children, choose the biggest
        else:
            # left
            if self._compare(i, left) < 0 and self._compare(right, left) < 0:
                self._swap(i, left)
                self._bubble_down(left)

            # right
            elif self._compare(i, right) < 0 and self._compare(left, right) < 0:
                self._swap(i, right)
                self._bubble_down(right)

    def _compare(self, a, b):
        return self._comparison(self._heap[a], self._heap[b])

    def _swap(self, a, b):
        self._heap[a], self._heap[b] = self._heap[b], self._heap[a]

    def _left(self, i):
        return i * 2

    def _right(self, i):
        return (i * 2) + 1

    def _parent(self, i):
        return i / 2

    def __repr__(self):
        return self._heap[1:self._n].__repr__()

    def __iter__(self):
        for i in xrange(1, self._n + 1):
            yield self._heap[i]


class TimeTicker:
    """
    Ticks independently of framerate
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

    def __getitem__(self, item):
        return (self.x, self.y)[item]

    def __repr__(self):
        return "Transform(%d, %d)" % (self.x, self.y)
