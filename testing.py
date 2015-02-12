from ai import BaseController
from constants import *

assert Direction.opposite(Direction.NORTH) == Direction.SOUTH
assert Direction.opposite(Direction.SOUTH) == Direction.NORTH
assert Direction.opposite(Direction.EAST) == Direction.WEST
assert Direction.opposite(Direction.WEST) == Direction.EAST

assert BaseController._direction_to_key(Direction.NORTH) == Input.UP
assert BaseController._direction_to_key(Direction.SOUTH) == Input.DOWN
assert BaseController._direction_to_key(Direction.EAST) == Input.RIGHT
assert BaseController._direction_to_key(Direction.WEST) == Input.LEFT

assert BaseController._key_to_direction(Input.UP) == Direction.NORTH
assert BaseController._key_to_direction(Input.DOWN) == Direction.SOUTH
assert BaseController._key_to_direction(Input.RIGHT) == Direction.EAST
assert BaseController._key_to_direction(Input.LEFT) == Direction.WEST

print("All passed!")