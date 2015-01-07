import os

import constants
import entity
import world as world_module
import random

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
    return constants.Direction.SOUTH # default
    
    
def debug_block(pos, world):
    print("----")
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
