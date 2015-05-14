import inspect

from ai import BaseController
from constants import *


def assert_equal(x, y):
    if x != y:
        line = inspect.currentframe().f_back.f_lineno
        raise AssertionError("Line %d: %r != %r" % (line, x, y))


def assert_true(x):
    assert_equal(x, True)


def assert_false(x):
    assert_equal(x, False)

# direction opposites
assert_equal(Direction.opposite(Direction.NORTH), Direction.SOUTH)
assert_equal(Direction.opposite(Direction.SOUTH), Direction.NORTH)
assert_equal(Direction.opposite(Direction.EAST), Direction.WEST)
assert_equal(Direction.opposite(Direction.WEST), Direction.EAST)

# direction/key relationships
assert_equal(BaseController._direction_to_key(Direction.NORTH), Input.UP)
assert_equal(BaseController._direction_to_key(Direction.SOUTH), Input.DOWN)
assert_equal(BaseController._direction_to_key(Direction.EAST), Input.RIGHT)
assert_equal(BaseController._direction_to_key(Direction.WEST), Input.LEFT)

assert_equal(BaseController._key_to_direction(Input.UP), Direction.NORTH)
assert_equal(BaseController._key_to_direction(Input.DOWN), Direction.SOUTH)
assert_equal(BaseController._key_to_direction(Input.RIGHT), Direction.EAST)
assert_equal(BaseController._key_to_direction(Input.LEFT), Direction.WEST)

# pedantic perpendiculars
assert_true(Direction.are_perpendicular(Direction.NORTH, Direction.EAST))
assert_true(Direction.are_perpendicular(Direction.NORTH, Direction.WEST))
assert_false(Direction.are_perpendicular(Direction.NORTH, Direction.NORTH))
assert_false(Direction.are_perpendicular(Direction.NORTH, Direction.SOUTH))
assert_true(Direction.are_perpendicular(Direction.SOUTH, Direction.EAST))
assert_true(Direction.are_perpendicular(Direction.SOUTH, Direction.WEST))
assert_false(Direction.are_perpendicular(Direction.SOUTH, Direction.NORTH))
assert_false(Direction.are_perpendicular(Direction.SOUTH, Direction.SOUTH))
assert_true(Direction.are_perpendicular(Direction.EAST, Direction.NORTH))
assert_true(Direction.are_perpendicular(Direction.EAST, Direction.SOUTH))
assert_false(Direction.are_perpendicular(Direction.EAST, Direction.EAST))
assert_false(Direction.are_perpendicular(Direction.EAST, Direction.WEST))
assert_true(Direction.are_perpendicular(Direction.WEST, Direction.NORTH))
assert_true(Direction.are_perpendicular(Direction.WEST, Direction.SOUTH))
assert_false(Direction.are_perpendicular(Direction.WEST, Direction.EAST))
assert_false(Direction.are_perpendicular(Direction.WEST, Direction.WEST))

assert_equal(set(Direction.perpendiculars(Direction.NORTH)), {Direction.EAST, Direction.WEST})
assert_equal(set(Direction.perpendiculars(Direction.EAST)), {Direction.NORTH, Direction.SOUTH})
assert_equal(set(Direction.perpendiculars(Direction.SOUTH)), {Direction.EAST, Direction.WEST})
assert_equal(set(Direction.perpendiculars(Direction.WEST)), {Direction.NORTH, Direction.SOUTH})

# adding directions to positions
source_pos = (4, 4)
distance = 3
assert_equal(util.add_direction(source_pos, Direction.NORTH, distance), [4, 1])
assert_equal(util.add_direction(source_pos, Direction.SOUTH, distance), [4, 7])
assert_equal(util.add_direction(source_pos, Direction.WEST, distance), [1, 4])
assert_equal(util.add_direction(source_pos, Direction.EAST, distance), [7, 4])

# expanding rectangles
rect = util.Rect(5, 5, 20, 20)
assert_equal(util.Rect(rect).expand(Direction.NORTH, 5).as_tuple(), (5, 0, 20, 25))
assert_equal(util.Rect(rect).expand(Direction.SOUTH, 5).as_tuple(), (5, 5, 20, 25))
assert_equal(util.Rect(rect).expand(Direction.EAST, 5).as_tuple(), (5, 5, 25, 20))
assert_equal(util.Rect(rect).expand(Direction.WEST, 5).as_tuple(), (0, 5, 25, 20))
assert_equal(util.Rect(rect).expand(Direction.NORTH, 20).expand(Direction.NORTH, -20).as_tuple(), rect.as_tuple())
assert_equal(util.Rect(rect).expand(Direction.SOUTH, 20).expand(Direction.SOUTH, -20).as_tuple(), rect.as_tuple())
assert_equal(util.Rect(rect).expand(Direction.EAST, 20).expand(Direction.EAST, -20).as_tuple(), rect.as_tuple())
assert_equal(util.Rect(rect).expand(Direction.WEST, 20).expand(Direction.WEST, -20).as_tuple(), rect.as_tuple())

# heap
heap = util.Heap(util.compare, 10)
for x in (5, 2, 8, 23, 7, 9):
    heap.add(x)
assert_equal(str(heap), str([23, 8, 9, 2, 7, 5]))
assert_equal(heap.pop(), 23)
assert_equal(str(heap), str([9, 8, 5, 2, 7]))
assert_false(heap.empty())

# colours
assert_equal(map(int, util.lerp_colours((0, 0, 0), (255, 255, 255), 0.5)), [127, 127, 127])
assert_equal(map(int, util.lerp_colours((255, 255, 255), (0, 0, 0), 0.5)), [127, 127, 127])

print("All passed!")