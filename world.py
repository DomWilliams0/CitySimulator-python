from collections import OrderedDict
import random
import operator
import sys

import pygame

import ai
import constants
from building import Building
import util
from vec2d import Vec2d

WORLDS = []


class _WorldLayer:
    def __init__(self, world, name, default_fill=None, draw_above=False, solid_blanks=False):
        """
        :param world: The world this layer belongs to
        :param name: The name of this layer
        :param default_fill: What the grid should be filled with on creation
        :param draw_above: Should this layer be drawn over everything else
        :param solid_blanks: Should BLANK blocks be collidable
        """
        self.world = world
        self.name = name
        self.draw_above = draw_above
        self.solid_blanks = solid_blanks
        self._blocks = [[default_fill] * world.tile_width for _ in xrange(world.tile_height)]

    def __getitem__(self, item):
        return self._blocks[item]


class WorldRenderer:
    class _RenderLayer:
        def __init__(self, world, layer_func):
            """
            :param layer_func: Predicate for choosing all world layers that this holds for
            """
            self.world = world
            self.layers = [(n, l) for n, l in world.layers.items() if layer_func(n, l)]
            self.surface = pygame.Surface((world.pixel_width, world.pixel_height)).convert_alpha()
            self.surface.fill((0, 0, 0, 0))

        def render(self):
            constants.SCREEN.blit(self.surface, (-constants.SCREEN.camera.transform.x, -constants.SCREEN.camera.transform.y))

    def __init__(self, world):
        self.layers = []
        self.world = world
        self.layers.append(self._RenderLayer(world, lambda n, l: not l.draw_above and n != "rects"))
        self.layers.append(self._RenderLayer(world, lambda _, l: l.draw_above))

        # self.night = pygame.Surface(constants.WINDOW_SIZE).convert_alpha()
        # self.night.fill((5,5,60,160))

    def initial_render(self):
        """
        Renders each layer onto its respective surface
        """
        for rlayer in self.layers:
            w = rlayer.world
            for name, l in rlayer.layers:
                for x, y, block in w.iterate_blocks(0, 0, w.tile_width, w.tile_height, name):
                    if block:
                        constants.SCREEN.draw_block(block, (util.tile_to_pixel((x, y)), constants.TILE_DIMENSION), surface=rlayer.surface)

    def render_sandwich(self, sandwiched_draw_function, args):
        """
        Renders the base layer, runs the given function with the given args, then renders all remaining layers
        """
        self.layers[0].render()
        sandwiched_draw_function(*args)
        for i in xrange(1, len(self.layers)):
            self.layers[i].render()

    def render_block(self, block, pos, world_layer):
        """
        :param block: Block to render
        :param pos: Block position
        :param world_layer: World layer to render to
        """
        rlayer = self._find_rlayer(world_layer)
        constants.SCREEN.draw_block(block, (util.tile_to_pixel(pos), constants.TILE_DIMENSION), surface=rlayer.surface)

    def _find_rlayer(self, wlayer):
        """
        :return: The RenderLayer that matches the given name
        """
        for rl in self.layers:
            for n, _ in rl.layers:
                if n == wlayer:
                    return rl


class EntityGrid:
    """
    A grid of sets that hold the entities in those cells
    """

    def __init__(self, the_world, cell_size):
        """
        :param the_world: The world
        :param cell_size: The pixel size of each cell
        """
        self.width = the_world.pixel_width / cell_size
        self.height = the_world.pixel_height / cell_size

        self.cell_size = cell_size
        self.grid = [[set() for _ in xrange(self.width)] for _ in xrange(self.height)]
        self._last_positions = {}
        self._disabled = {}

    def get_cell_entities(self, position):
        """
        :param position: (x, y)
        :return: Set of entities in the grid cell at the given coordinates
        """
        return self.grid[position[1]][position[0]]

    def get_nearest_cell(self, position):
        new_pos = (map(lambda x: util.round_down_to_multiple(x, self.cell_size) / self.cell_size, position))
        new_pos = min(new_pos[0], self.width - 1), min(new_pos[1], self.height - 1)
        return new_pos

    def move(self, e):
        """
        Updates the grid_cell of the given entity
        """
        # disabled
        if e in self._disabled:
            return

        new_pos = self.get_nearest_cell(e.transform)
        cell = self.get_cell_entities(new_pos)
        cell.add(e)
        e.grid_cell = new_pos

        # move out of old position
        old_pos = self._last_positions.get(e)
        if old_pos and old_pos != new_pos:
            s = self.get_cell_entities(old_pos)
            s.remove(e)

        self._last_positions[e] = new_pos

    def set_enabled(self, entity, enabled):
        if not enabled:
            self._disabled[entity] = entity.grid_cell
            self.get_cell_entities(entity.grid_cell).remove(entity)
            entity.grid_cell = None
        else:
            entity.grid_cell = self._disabled[entity]
            self.get_cell_entities(entity.grid_cell).add(entity)
            del self._disabled[entity]
        entity.collisions_enabled = enabled

    def iterate_entities(self):
        """
        Iterates all entity pairs in the grid
        :return: (entity, other)
        """
        for row in self.grid:
            for s in row:
                for e in s:
                    for o in s:
                        if o.id < e.id:
                            yield e, o


class BaseWorld:
    def __init__(self, width, height, half_block_boundaries=True):
        """
        :param half_block_boundaries: If an entity can't leave the boundaries, can they at least semi-leave for half their size?
        """
        self.tile_width = width
        self.tile_height = height
        self.pixel_width = width * constants.TILE_SIZE
        self.pixel_height = height * constants.TILE_SIZE

        self.layers = OrderedDict()
        self.interact_rects = []

        self.entity_grid = EntityGrid(self, constants.TILE_SIZE * 2)
        self.entities = []
        self.entity_buffer = {}
        self._spawns = {}

        self.half_block_boundaries = half_block_boundaries
        self.renderer = None

        self.nav_graph = None

        WORLDS.append(self)

    def post_load(self):
        """
        Finishes off the loading of the world
        """
        self.renderer = WorldRenderer(self)
        self.renderer.initial_render()

    def _reg_layer(self, name, draw_above=False, solid_blanks=False):
        """
        Registers a layer with the given name and properties
        """
        if name in self.layers:
            constants.LOGGER.warning("Layer '%s' already exists in the world" % name)
        else:
            self.layers[name] = _WorldLayer(self, name, draw_above=draw_above, solid_blanks=solid_blanks)

    def has_layer(self, layer):
        return layer in self.layers.keys()

    def get_block(self, x, y, layer):
        """
        Gets the block at the given coords in the given layer
        """
        return self.layers[layer][y][x]

    def match_block(self, x, y, predicate):
        """
        Returns the first uppermost block that matches the given predicate

        :param predicate: Function that takes (block, layer)
        :return: None if no suitable block found, otherwise the block
        """
        try:
            for layer_name, layer in reversed(self.layers.items()):
                if layer_name != "rects":
                    b = self.get_block(x, y, layer_name)
                    if b and predicate(b, layer):
                        return b
        except IndexError:
            pass

        return None

    def get_solid_block(self, x, y):
        """
        Finds any collidable/interactable blocks at the given coords and returns the uppermost
        :return: None if no collidable block found, otherwise the block
        """

        def predicate(b, layer):
            if BlockType.is_collidable(b.blocktype) or BlockType.is_interactable(b.blocktype):
                # blanks
                if b.blocktype == BlockType.BLANK:
                    if not layer.solid_blanks:
                        return False
                return True

        return self.match_block(x, y, predicate)

    def get_door_block(self, x, y):
        return self.match_block(x, y, lambda b, layer: b.blocktype == BlockType.SLIDING_DOOR or b.blocktype == BlockType.ENTRANCE_MAT)

    def set_block(self, x, y, block, layer, overwrite_collisions=True):
        """
        Sets the block at the given coords in the given layer.
        If it is collidable, its rect is inserted into the rects layer; otherwise None

        :param overwrite_collisions: Whether or not this new block should affect the collidability of the block
        """
        self.layers[layer][y][x] = block

        if BlockType.is_interactable(block.blocktype):
            self.interact_rects.append((util.tile_to_pixel((x, y)), constants.TILE_DIMENSION))

        if overwrite_collisions:
            if not self.layers[layer].draw_above and BlockType.is_collidable(block.blocktype):
                offset, collision_rect = Block.HELPER.get_collision_rect(block)
                pos = util.tile_to_pixel((x, y))
                pos = pos[0] + offset[0], pos[1] + offset[1]
                new_value = pos, collision_rect
                self.layers["rects"][y][x] = new_value

        if constants.SCREEN.camera:
            self.renderer.render_block(block, (x, y), layer)

    def set_block_type(self, x, y, blocktype, layer, overwrite_collisions=True):
        """
        Sets the shared instance of the given blocktype at the given coords in the given layer
        If it is collidable, its rect is inserted into the rects layer; otherwise None

        :param overwrite_collisions: Whether or not this new block should affect the collidability of the block
        """
        block = Block.HELPER.get_shared_instance(blocktype)
        self.set_block(x, y, block, layer, overwrite_collisions)

    def get_colliding_blocks(self, rect, interactables=False):
        """
        :param interactables: Check collisions with just interactive blocks, or solid blocks?
        :return: All rects from the rects layer that collide with the given rect
        """
        rects = []
        if not interactables:
            x1 = util.round_to_tile_size(rect.x) / constants.TILE_SIZE
            x2 = util.round_to_tile_size(rect.topright[0]) / constants.TILE_SIZE
            y1 = util.round_to_tile_size(rect.y) / constants.TILE_SIZE
            y2 = util.round_to_tile_size(rect.bottomleft[1]) / constants.TILE_SIZE
            rect_grid = self.layers["rects"]
            for y in xrange(y1 - 1, y2 + 1):
                for x in xrange(x1 - 1, x2 + 1):
                    try:
                        r = rect_grid[y][x]
                    except IndexError:
                        continue
                    if r and rect.colliderect(r):
                        rects.append(r)
        else:
            for interactable in self.interact_rects:
                if rect.colliderect(interactable):
                    rects.append(interactable)

        return rects

    def print_ascii(self, layer="terrain"):
        """
        Prints the given layer to the console; used for debugging
        """
        for y in xrange(self.tile_height):
            for x in xrange(self.tile_width):
                print(self.get_block(x, y, layer)),
            print

    def tick_entities(self, render, boundaries=None):
        """
        Ticks all entities
        :param boundaries Only render those in the given boundaries (format: x1, y1, x2, y2)
        """
        # sort by depth
        self.depth_sort_entities()

        # draw entities
        for e in self.entities:
            if e.dead:
                self._transfer_to_buffer(e, self, None)
                if constants.STATEMANAGER.controller.entity == self:
                    constants.STATEMANAGER.transfer_control(None)
            else:
                self.entity_grid.move(e)
                e.tick(render and e.is_visible(boundaries))

        # flush buffer
        for e, v in self.entity_buffer.items():
            if v < 0:
                self.entities.remove(e)
            else:
                self.entities.append(e)
        self.entity_buffer.clear()

    def depth_sort_entities(self):
        util.insert_sort(self.entities, lambda a, b: util.compare(a.transform.y, b.transform.y))

    def iterate_surrounding_grid_cells(self, grid_cell):
        """
        :return: A series of sets of entities in the surrounding grid cells
        """
        try:
            for i in (-1, 0, 1):
                for j in (-1, 0, 1):
                    coord = grid_cell[0] + i, grid_cell[1] + j
                    yield self.entity_grid.get_cell_entities(coord)
        except IndexError:
            pass

    def match_nearest_entity(self, position, grid_cell, predicate, range_sqrd=-1):
        min_distance_sqrd = sys.maxsize
        nearest_entity = None
        for grid_cell in self.iterate_surrounding_grid_cells(grid_cell):
            for e in grid_cell:
                if not predicate or predicate(e):
                    dist = util.distance_sqrd(e.transform, position)
                    if dist < min_distance_sqrd:
                        min_distance_sqrd = dist
                        nearest_entity = e
        return nearest_entity if range_sqrd > 0 and min_distance_sqrd <= range_sqrd else None

    def tick(self, render=True):
        """
        Ticks the world and all entities, removing all the dead

        :param render: Whether or not the world should be rendered after ticking
        """
        # find screen boundaries
        if render:
            camera = constants.SCREEN.camera
            pos = tuple(int(x / constants.TILE_SIZE) for x in camera.transform)
            x2 = camera.view_size[0] / constants.TILE_SIZE + pos[0] + 1
            y2 = camera.view_size[1] / constants.TILE_SIZE + pos[1] + 1
            if x2 >= self.tile_width:
                x2 = self.tile_width

            if y2 >= self.tile_height:
                y2 = self.tile_height

            x1 = max(0, pos[0] - 1)
            y1 = max(0, pos[1] - 1)

        entity_tick_args = (render, (x1, y1, x2, y2) if render else None)
        if render:
            self.renderer.render_sandwich(self.tick_entities, entity_tick_args)
        else:
            self.tick_entities(*entity_tick_args)

            # debug render collision rects
            # if render:
            # for x, y, r in self.iterate_blocks(layer="rects"):
            # if r:
            # constants.SCREEN.draw_rect(r, filled=False)

    def iterate_blocks(self, x1=0, y1=0, x2=-1, y2=-1, layer="terrain"):
        """
        Iterate through blocks in the given layer, optionally only in the specified area

        :return: Generator for blocks in the given layer
        """
        if x2 < 0:
            x2 = self.tile_width
        if y2 < 0:
            y2 = self.tile_height

        for x in xrange(x1, x2):
            for y in xrange(y1, y2):
                b = self.get_block(x, y, layer)
                if b:
                    yield (x, y, b)

    def iterate_rectangle(self, r, layer="terrain"):
        for x, y, b in self.iterate_blocks(r.x, r.y, r.x + r.width, r.y + r.height, layer):
            yield x, y, b

    def iterate_layers(self, x1, y1, x2, y2, rects=False, layer_func=None):
        """
        Iterates blocks in all layers in the specified area

        :param rects: Whether the rects layer should be included
        :param layer_func: Property function for layers to be included
        :return: Generator for all blocks in all layers
        """

        for layer in self.layers:
            if not rects and layer == "rects":
                continue
            blocks = self.layers[layer]
            if layer_func and not layer_func(blocks):
                continue

            for x in xrange(x1, x2):
                for y in xrange(y1, y2):
                    block = blocks[y][x]
                    if block:
                        yield (x, y, blocks[y][x])

    def is_in_range(self, tilex, tiley):
        """
        :return: Whether the given tile coords are inside the world
        """
        return 0 <= tilex < self.tile_width and 0 <= tiley < self.tile_height

    def is_point_blocked(self, tile_position, direction, distance=1):
        """
        :return: Whether there is a solid block blocking the way of the given position in the given direction
        """
        next_tile = util.add_direction(tile_position, direction, distance)
        if not self.is_in_range(*next_tile):
            return True

        block = self.get_solid_block(*util.intify(next_tile))
        return bool(block)

    def is_rect_blocked(self, rect, direction, distance):
        """
        :param distance: Distance in terms of tile spans
        :return: False if not blocked, otherwise a list of blocks that it collides with
        """
        moved_rect = util.Rect(rect)
        pos = util.add_direction(moved_rect.position(), direction, distance * constants.TILE_SIZE)
        moved_rect.x, moved_rect.y = pos

        collisions = self.get_colliding_blocks(moved_rect)
        if not collisions:
            return False
        return collisions

    def get_surrounding_blocks(self, pos, layer="terrain"):
        """
        Finds the 4 surrounding blocks around the given tile position
        :return: block, blockpos, relative coords ie (-1, 0)
        """
        for x, y in util.SURROUNDING_OFFSETS:
            posx, posy = x + pos[0], y + pos[1]
            if self.is_in_range(posx, posy):
                yield self.get_block(posx, posy, layer), (posx, posy), (x, y)

    def random_location(self, size=(0, 0)):
        """
        :return: A random location that will accommodate an entity of the given size
        """
        return Vec2d(random.randrange(self.pixel_width - size[0]), random.randrange(self.pixel_height - size[1]))

    def _transfer_to_buffer(self, entity, from_world, to_world):
        """
        :param entity: Entity to transfer
        :param from_world: The entity's current world
        :param to_world: The world to be transferred to: can be null
        """
        from_world.entity_buffer[entity] = -1
        if to_world:
            to_world.entity_buffer[entity] = 1
        entity.world = to_world

    def spawn_entity(self, entity, loc=None):
        """
        Adds the entity to the world

        :param loc: The spawn location; if None, the entity is not moved from their old position (possibly from an old world)
        """
        self._transfer_to_buffer(entity, entity.world, self)
        if loc:
            entity.move_entity(loc)

    def get_spawn(self, index, entitytype):
        """
        :return: The spawn at the given index and entitytype, with all the fiddly details: x, y, orientation, width, height
        """
        return self._spawns[entitytype][index]

    def get_spawn_location(self, index, entitytype):
        """
        :return: The (x, y) position of the spawn at the given index and entitytype
        """
        return self.get_spawn(index, entitytype)[0:2]

    def move_to_spawn(self, entity, index, vary=False):
        """
        :param index: Spawn index
        :param vary: Should the spawn position be fuzzed a bit
        """
        assert self == entity.world
        spawn = self.get_spawn(index, entity.entitytype)
        if vary:
            pos = (spawn[0] + random.randrange(spawn[3]), spawn[1] + random.randrange(spawn[4]))
            entity.move_entity(pos)

        else:
            tile_pos = util.pixel_to_tile(spawn[:2])

            # y coordinate is always +1
            tile_pos = tile_pos[0], tile_pos[1] - 1
            spawn_size = util.pixel_to_tile(spawn[-2:])

            tile = map(lambda (x, d): x + random.randrange(d), zip(tile_pos, spawn_size))
            entity.move_entity_to_tile(tuple(tile))

        entity.turn(spawn[2])

    def spawn_entity_at_spawn(self, entity, spawn_index, vary=True):
        """
        Convenience function for moving an entity to this world at the given spawn index
        """
        self.spawn_entity(entity)
        self.move_to_spawn(entity, spawn_index, vary)

    # noinspection PyUnresolvedReferences
    @classmethod
    def load_tmx(cls, filename):
        """
        :param filename: File name.tmx
        :return: The loaded world
        """
        from xml.etree import ElementTree

        constants.LOGGER.debug("Started loading world %s" % filename)
        constants.LOGGER.push_level()

        tree = ElementTree.parse(util.search_for_file(filename, "res/world"))
        root = tree.getroot()

        def iterate_objects(name):
            for layer in root.findall("objectgroup"):
                if layer.get("name") == name:
                    for child in layer:
                        properties = None
                        try:
                            l = [p.attrib for p in child[0]]
                            properties = {}
                            for d in l:
                                properties[d["name"]] = d["value"]
                        except IndexError:
                            pass

                        if properties:
                            yield child.attrib, properties
                        else:
                            yield child.attrib

        width = int(root.attrib["width"])
        height = int(root.attrib["height"])
        world = cls(width, height)
        char_to_id = lambda char: 0 if char == '0' else int(char) - 1

        # load terrain layers
        for terrain_layer in root.iter("layer"):
            data = terrain_layer.getchildren()[0].text
            layer_name = terrain_layer.attrib["name"]
            x = y = 0

            draw_above = not world.layers[layer_name].draw_above
            solid_blanks = world.layers[layer_name].solid_blanks

            for c in data.strip().split(','):
                # new row
                if c[0].isspace():
                    x = 0
                    y += 1
                    c = c[1:]

                if c.isdigit():
                    block_id = char_to_id(c)
                    real_id = block_id
                    block = Block.HELPER.get_shared_instance(block_id)

                    # rotated
                    if not block:
                        real_id, rot, hor, ver = Block.HELPER.get_rotation(block_id)

                        try:
                            old_surface = Block.HELPER.block_images[real_id]
                            surface = pygame.transform.flip(old_surface, hor, ver)
                            if rot:
                                surface = pygame.transform.rotate(surface, 90)
                        except KeyError:
                            raise StandardError("Unknown rotation of block id %d" % block_id)

                        # register rotated surface under new blockid
                        block = Block.HELPER.register_block(real_id, surface, render_id=block_id)

                    # each interactable instance must be unique
                    if BlockType.is_interactable(real_id):
                        block = Block.HELPER.create_new_instance(block)

                    # should blanks be collidable
                    if block_id == BlockType.BLANK:
                        colls = solid_blanks
                    else:
                        colls = draw_above

                    world.set_block(x, y, block, layer_name, colls)
                    x += 1

        tileset_res = constants.TILESET_RESOLUTION

        def get_coord(element, name):
            return int(element[name]) / tileset_res

        # load objects
        for o in iterate_objects("objects"):
            x = get_coord(o, "x")
            y = get_coord(o, "y")
            y -= 1  # different relative coord system
            world.set_block(x, y, Block.HELPER.get_shared_instance(char_to_id(o["gid"])), "objects")

        # load building zones
        for props in iterate_objects("_buildings"):
            r = props[0]
            x = get_coord(r, "x")
            y = get_coord(r, "y")
            width = int(r["width"]) / tileset_res
            height = int(r["height"]) / tileset_res
            name = props[1]["building"]

            building = Building(world, x, y, width, height, name)
            world.buildings.append(building)

        # add spawn points
        a = constants.TILE_SIZE / constants.TILESET_RESOLUTION
        for s, p in iterate_objects("_spawns"):
            x = get_coord(s, "x") * constants.TILE_SIZE
            y = (get_coord(s, "y") + 1) * constants.TILE_SIZE  # +1 to be INSIDE the spawn tile
            w = int(s["width"]) * a
            h = int(s["height"]) * a
            o = util.parse_orientation(p["orientation"])
            entitytype = constants.EntityType.parse_string(p["entitytype"])
            world.add_spawn(entitytype, x, y, o, w, h)

        # load roadmap
        # todo: add vehicle spawns automatically, only if they are on the edge of the map?
        for street_start in iterate_objects("_road"):
            x = get_coord(street_start, "x")
            y = get_coord(street_start, "y")
            world.roadmap.begin_discovery((x, y))

        # todo combine collision rects

        # finish up any other tasks
        world.post_load()

        constants.LOGGER.pop_level()
        constants.LOGGER.debug("Successfully loaded world %s" % filename)
        return world

    def add_spawn(self, entitytype, x, y, o=None, w=None, h=None):
        """
        :param entitytype: Spawn type
        :param x: X pos
        :param y: Y pos
        :param o: Orientation char
        :param w: Width
        :param h: Height
        """
        spawns = self._spawns.get(entitytype, [])
        spawns.append((x, y, util.parse_orientation(o), constants.TILE_SIZE if not w else w, constants.TILE_SIZE if not h else h))
        self._spawns[entitytype] = spawns


class World(BaseWorld):
    """
    Outside world
    """

    def __init__(self, width, height, half_block_boundaries=True):
        BaseWorld.__init__(self, width, height, half_block_boundaries)

        self._reg_layer("overterrain", draw_above=True)
        self._reg_layer("underterrain")
        self._reg_layer("terrain")
        self._reg_layer("objects")
        self._reg_layer("rects")

        self.buildings = []
        self.roadmap = RoadMap(self)

        _BlockHelper.init_helper()

    def post_load(self):
        BaseWorld.post_load(self)

        # load nav graph
        self.nav_graph = ai.NavigationGraph(self)
        self.nav_graph.generate_graph(BlockType.PAVEMENT, {BlockType.ROAD: 5, BlockType.SAND: 20})
        constants.LOGGER.debug("Generation navigation graph of %d nodes" % len(self.nav_graph.graph))

    def get_block(self, x, y, layer="terrain"):
        return BaseWorld.get_block(self, x, y, layer)

    def set_block(self, x, y, block, layer="terrain", overwrite_collisions=True):
        BaseWorld.set_block(self, x, y, block, layer, overwrite_collisions)

    def set_block_type(self, x, y, blocktype, layer="terrain", overwrite_collisions=True):
        BaseWorld.set_block_type(self, x, y, blocktype, layer, overwrite_collisions)

    def tick(self, render=True):
        BaseWorld.tick(self, render)

        # debug terrible rendering of lanes
        # if render:
        # for road in self.roadmap.roads:
        # i = 0
        # for r in road._bounds:
        #             pixel = util.Rect(r)
        #             colour = (255, 255, 0) if i > 1 else (0, 255, 255)
        #             i += 1
        #             for a in ('x', 'y', 'width', 'height'):
        #                 util.modify_attr(pixel, a, lambda x: x * constants.TILE_SIZE)
        #             constants.SCREEN.draw_rect(pixel, filled=False, colour=colour)
        #
        #     for node in self.roadmap.nodes.values():
        #         constants.SCREEN.draw_circle_in_tile(util.tile_to_pixel(node.point))

        # debug beautiful rendering of navigation graph
        if render:
            self.nav_graph.debug_render()


class BuildingWorld(BaseWorld):
    def __init__(self, width, height):
        BaseWorld.__init__(self, width, height, half_block_boundaries=False)
        self._reg_layer("underterrain")
        self._reg_layer("terrain", solid_blanks=True)
        self._reg_layer("objects")
        self._reg_layer("rects")


# noinspection PyShadowingNames
# todo this is horrible, I think a rethink and re-everything would be a good idea
# the graph search should use the same as pedestrians, using ai.NavigationGraph
class RoadMap:
    """
    Manages all roads/intersections
    """

    class Road:
        _LAST_ID = 0

        def __init__(self, roadmap, line, road_direction, road_length, oneway=False):
            """
            :param line: Road line of tiles
            """
            self.id = RoadMap.Road._LAST_ID
            RoadMap.Road._LAST_ID += 1

            self.roadmap = roadmap
            self.oneway = oneway
            self.vertical_road = road_direction[0] == 0
            self.road_direction = road_direction
            self.direction = -1 if road_direction[1 if self.vertical_road else 0] < 0 else 1
            self.width = len(line)
            self.line = line
            self.end_line = line
            self.length = 0
            self.is_spawn = False
            self._bounds = []

            self.set_road_length(road_length)

        def set_road_length(self, road_length):
            """
            Sets the length of the road to the given length
            """
            self.length = road_length
            self.line = map(lambda x: tuple(x), self.line)  # tupled
            self.end_line = self.roadmap.move_line(self.line, road_length, self.road_direction)

            # find if this road contains the end of the world
            all_points = self.line[:]
            all_points.extend(map(operator.add, x, (y * road_length for y in self.road_direction)) for x in self.line)
            self.is_spawn = False
            for tx, ty in all_points:
                if tx == 0 or ty == 0 or tx == self.roadmap.world.tile_width - 1 or ty == self.roadmap.world.tile_height - 1:
                    self.is_spawn = True
                    break

            if self.vertical_road:
                attrs = 'width', 'x'
            else:
                attrs = 'height', 'y'

            # create one spanning rectangle
            rect = util.Rect(min(self.line), (1, 1))
            util.modify_attr(rect, attrs[0], lambda x: len(self.line))

            start_bounds = [rect]

            # split into 2 lanes
            if not self.oneway:
                util.modify_attr(rect, attrs[0], lambda x: float(x) / 2)

                other = util.Rect(rect)
                util.modify_attr(other, attrs[1], lambda x: x + getattr(other, attrs[0]))

                start_bounds.append(other)

            # find end boundaries
            end_bounds = []
            axis = 'y' if self.vertical_road else 'x'

            for i, r in enumerate(start_bounds):
                r = util.Rect(r)
                util.modify_attr(r, axis,
                                 lambda x: x + (road_length * self.direction))

                end_bounds.append(r)

            # todo: sort start and end bounds into lanes
            if self.direction < 0:
                start_bounds = start_bounds[::-1]
                end_bounds = end_bounds[::-1]

            self._bounds = []
            self._bounds.extend(start_bounds)
            self._bounds.extend(end_bounds)

        def left_lane_start(self):
            return self._bounds[0]

        def right_lane_start(self):
            return self._bounds[0 if self.oneway else 1]

        def left_lane_end(self):
            return self._bounds[2]

        def right_lane_end(self):
            return self._bounds[1 if self.oneway else 3]

    class Intersection:
        def __init__(self, roads):
            self.roads = [[None] * 4]
            print("intersection", roads)

    def __init__(self, world):
        self.world = world
        self.nodes = {}
        self.roads = []
        # self.intersections = []

    # todo: take a list of startpos, then wrap all this into a loop through them
    def begin_discovery(self, startpos):
        """
        Recursively finds all roads connected to the given start position
        """
        stack = util.Stack(startpos)
        road_regions = []
        connected_roads = []
        # intersections = []

        while stack:
            pos = stack.pop()

            # pre-calculated from found fork
            precalc = len(pos) == 3
            start_line = None
            if precalc:
                road_width, width_direction, road_direction = len(pos[0]), pos[1], pos[2]
                start_line = pos[0]
                pos = tuple(start_line[0])
            else:
                # find road width and direction (for unconnected roads)
                road_width, width_direction, road_direction = self._find_road_width(pos)

            # roads not found
            if not road_direction or not width_direction:
                continue

            # find the end of this road, and any forks on the way
            road, (end_line, forks) = self._traverse_road(pos, road_width, width_direction, road_direction, start_line)

            # print road.id, pos, road_direction

            self.roads.append(road)

            # extend region to cover whole road, to prevent duplicate roads (and infinite recursion)
            rect = util.Rect(pos, (0, 0))
            rlength = (road.length + (1 if road.direction > 0 else 0)) * road.direction
            rwidth = road.width
            order = 'width', 'height'
            for i in xrange(2):
                setattr(rect, order[(i + (1 if road.vertical_road else 0)) % 2], rwidth if i == 1 else rlength)

            # filter forks, to remove repetitions and find road widths/directions
            forks = self._filter_forks(forks, road_regions)

            # find intersections, and shorten roads if necessary
            # intersection_positions = self._find_intersections(road, forks, road_regions)
            # if intersection_positions:
            # intersections.extend(intersection_positions)

            connected_roads.append((pos, forks))
            for f in forks:
                stack.push(f)
            road_regions.append(rect)

        # debug
        self.temp_regions = road_regions

        # build intersections
        # self._construct_intersections(intersections)

        # connect nodes
        self._build_graph(connected_roads)

        # precalculate paths between spawns todo
        # dict: spawn: otherspawn
        # otherspawn: reversed ^

        # roads need to know about their ends, and lanes

    def _find_road_width(self, startpos, max_road_width=8):
        """
        :return: The road width at the given position
        """

        def _recurse(world, pos, offset, current_width, max_road_width):
            tile = map(operator.add, pos, offset)
            block = world.get_block(*tile)  # guaranteed to be in range
            if block.blocktype == BlockType.ROAD and current_width < max_road_width:
                return _recurse(world, tile, offset, current_width + 1, max_road_width)
            else:
                return current_width

        min_width = max_road_width
        max_width = 0
        width_direction = road_direction = None
        for b, pos, offset in self.world.get_surrounding_blocks(startpos):
            btype = b.blocktype
            if btype == BlockType.ROAD:
                width = _recurse(self.world, startpos, offset, 1, max_road_width)
                if 0 < width < min_width:  # does not allow 1 wide roads
                    min_width = width
                    width_direction = offset

                if width > max_width:
                    max_width = width
                    road_direction = offset

        return min_width, width_direction, road_direction

    def move_line(self, line, amount, road_direction):
        """
        :param line: Line of tiles
        :param amount: Amount to move
        :param road_direction: Direction in which to move
        :return: Moved line of tiles
        """
        return tuple(map(lambda pos: tuple(map(operator.add, pos, (i * amount for i in road_direction))), line))

    def valid_road_line(self, moved_line):
        """
        :return: Whether the given tile line is in the world and contains all road blocks
        """
        for tilex, tiley in moved_line:
            if not self.world.is_in_range(tilex, tiley) or self.world.get_block(tilex, tiley).blocktype != BlockType.ROAD:
                return False
        return True

    def _add_fork(self, road_regions, fork_list, line, width_direction, road_direction):
        """
        Registers a fork

        :param fork_list: List to add the processed fork to
        :param line: Fork tile line
        :param width_direction: Direction of the fork span
        :param road_direction: Fork direction
        """

        # not a valid position
        if not self.valid_road_line(line):
            return

        # check if already processed
        for rect in road_regions:
            for tile in line:
                if rect.collidepoint(tile):
                    return
        fork_list.append((line, width_direction, road_direction))

    def _traverse_road(self, startpos, width, width_direction, road_direction, start_line):
        """
        :return: Road object for this road,
                    line at the end of the road,
                    list of (many consecutive) fork positions
        """

        def get_line_ends(line, width_direction):
            key = lambda x: (x[0], x[1]) if width_direction[0] != 0 else (x[1], x[0])
            s = sorted(line, key=key)
            return [tuple(map(operator.sub, s[0], width_direction)), tuple(map(operator.add, s[-1], width_direction))]

        def _recurse(world, line, road_direction, forks):
            # move line forward
            moved_line = self.move_line(line, 1, road_direction)

            # find forks
            ends = get_line_ends(moved_line, width_direction)
            for e in ends:
                if world.is_in_range(*e) and world.get_block(*e).blocktype == BlockType.ROAD:
                    which_end = -1 if min(ends) == e else 1
                    forks.append((which_end, e))

            # verify the road line is still valid
            if not self.valid_road_line(moved_line):
                return line, forks

            return _recurse(world, moved_line, road_direction, forks)

        # generates the line of coords for the road
        if start_line is None:
            line = map(lambda x: map(operator.add, x, startpos), [map(lambda x: x * i, width_direction) for i in xrange(width)])
        else:
            line = start_line

        forks = []
        recurse = _recurse(self.world, line, road_direction, forks)
        road = RoadMap.Road(self, line, road_direction, util.find_difference(line[0], recurse[0][0], True)[1])
        return road, recurse

    def _filter_forks(self, forks, processed_road_regions):
        """
        :return: Fork line, width direction, road direction
        """

        def add_fork(line, width_direction, which_end, fork_list):
            try:
                if abs(current[0][0] - current[1][0]) != 0:
                    road_direction = (0, 1)
                else:
                    road_direction = (1, 0)
            except IndexError:
                return

            if which_end < 0:
                road_direction = map(lambda x: x * -1, road_direction)

            self._add_fork(processed_road_regions, fork_list, line, width_direction, road_direction)

        # no forks
        if not forks:
            return forks
        forks = sorted(forks)

        # split into consecutive forks
        consecutive_forks = []
        current = []
        last = None
        last_diff = None
        last_which_end = None

        for which_end, f in map(tuple, forks):
            diff = util.find_difference(f, last, True) if last else 0
            if last is None or diff == [0, 1]:
                current.append(f)
                if last:
                    last_diff = util.find_difference(f, last, False)
            else:
                # calculate directions for this fork
                add_fork(current, last_diff, last_which_end, consecutive_forks)
                current = [f]
            last = f
            last_which_end = which_end

        add_fork(current, last_diff, last_which_end, consecutive_forks)
        return consecutive_forks

    def _find_intersections(self, road, forks, road_regions):

        extra_forks = []
        intersection_positions = []
        for fork, wdir, fdir in forks:
            for other, _, odir in forks:
                if fork <= other or len(fork) != len(other):
                    continue

                # not facing opposite directions
                if abs(max(fdir)) == abs(max(odir)):
                    continue

                # they don't vary on a single axis
                diff = map(operator.sub, fork[0], other[0])
                if min(diff) != 0:
                    continue

                # shorten road
                index = 1 if road.vertical_road else 0
                road_begin = road.line[0][index]
                intersection_begin = fork[0][index]
                road.set_road_length(intersection_begin - road_begin - 1)

                # add road opposite to list of forks
                new_fork = self.move_line(road.line, road.length + len(fork) + 1, road.road_direction)
                self._add_fork(road_regions, extra_forks, new_fork, wdir, road.road_direction)

                # add intersection
                intersection_positions.append((fork, other, road.end_line, new_fork))

        forks.extend(extra_forks)
        return intersection_positions

    def _construct_intersections(self, intersections):
        print(len(intersections))
        for road_lines in intersections:
            for line in road_lines:
                print(line)
            print

    class Node:
        """
        Graph search node
        """

        def __init__(self, point, node_id):
            self.point = point
            self.id = node_id
            self.edges = set()

        def __repr__(self):
            return "Node %d" % self.id

    def _build_graph(self, connected_roads):
        """
        Builds a search graph out of all the discovered roads
        """

        def add_edge(node, other):
            from itertools import permutations

            for a, b in permutations((node, other)):
                a.edges.add(b)

        def find_node_from_points(points):
            for point in points:
                for n in self.nodes.values():
                    if point == n.point:
                        return n

        self.nodes = {}
        node_id = 0

        # create nodes
        for point, _ in connected_roads:
            self.nodes[node_id] = RoadMap.Node(point, node_id)
            node_id += 1

        # link nodes
        for nid, (point, all_forks) in enumerate(connected_roads):

            # no forks
            if not all_forks:
                continue

            node = self.nodes[nid]
            for fork_points, _, _ in all_forks:
                add_edge(node, find_node_from_points(fork_points))

        # convert node edges to list: order must be kept now
        for n in self.nodes.values():
            n.edges = sorted(list(n.edges))


class _BlockHelper:
    """
    Manages the tileset, and shared Block instances
    """

    @staticmethod
    def init_helper():
        """
        Loads the tileset and initialises the helper
        """
        if not Block.HELPER:
            Block.HELPER = _BlockHelper()
            Block.HELPER.load_tileset()
            constants.LOGGER.info("Loaded tileset")

    def __init__(self):
        self.shared_blocks = {}
        self.block_images = {}

    def load_tileset(self):
        tileset_surface = pygame.image.load(util.get_relative_path("tileset.png", "res/world")).convert_alpha()

        rect = util.Rect(0, 0, constants.TILESET_RESOLUTION, constants.TILESET_RESOLUTION)
        width = tileset_surface.get_width()

        def move_along():
            if rect.right == width:
                rect.x = 0
                rect.y += constants.TILESET_RESOLUTION
            else:
                rect.x += constants.TILESET_RESOLUTION

        all_types = BlockType.iterate()
        maximum = all_types[-1][1]
        for blocktype in xrange(maximum + 1):

            # move along until a valid tile is found
            if not [bt for bt in all_types if bt[1] == blocktype]:
                move_along()
                continue

            # blit and scale block sprite to tile size
            surface = pygame.Surface(constants.TILE_DIMENSION).convert_alpha()
            temp_tile = pygame.Surface((constants.TILESET_RESOLUTION, constants.TILESET_RESOLUTION), 0, tileset_surface)
            temp_tile.blit(tileset_surface, (0, 0), rect.as_tuple())

            pygame.transform.scale(temp_tile, constants.TILE_DIMENSION, surface)

            self.register_block(blocktype, surface)

            move_along()

    def register_block(self, blocktype, surface, render_id=None):
        """
        Registers the given blocktype with the given surface
        :return: The newly created block
        """
        cls = BlockType.get_class_from_type(blocktype)
        block = cls(blocktype, render_id)
        self.shared_blocks[block.render_id] = block
        self.block_images[block.render_id] = surface
        return block

    def get_shared_instance(self, blocktype):
        """
        :return: The shared instance of the given blocktype, or None if not found
        """
        return self.shared_blocks.get(blocktype)

    def create_new_instance(self, block):
        """
        :return: A new instance of the given block
        """
        # block = self.get_shared_instance(blocktype)
        new_block = Block.clone(block)
        self.block_images[new_block.render_id] = self.block_images[block.render_id]
        return new_block

    def get_collision_rect(self, block):
        """
        :return: The collision rectangle of the given block (for custom collision box sizes)
        """
        offset = (0, 0)
        rect = constants.TILE_DIMENSION
        blockid, rot, hor, ver = self.get_rotation(block.render_id)

        # todo register modifications in a dictionary, to avoid if if if for other blocktypes
        if blockid == BlockType.BUILDING_EDGE:
            rect = int(rect[0] * 0.8), rect[1]
            if not hor:
                offset = (int(rect[0] * 0.2) + 1, 0)

        return offset, rect

    def get_rotation(self, block_id):
        """
        :return: Real block id, rotated, horizontally, vertically
        """
        rotation = 0x01 << 29
        vertical = 0x02 << 29
        horizontal = 0x04 << 29

        rot = block_id & rotation != 0
        hor = block_id & horizontal != 0
        ver = block_id & vertical != 0
        real_id = block_id

        if rot:
            real_id ^= rotation
        if hor:
            real_id ^= horizontal
        if ver:
            real_id ^= vertical
        return real_id, rot, hor, ver


class BlockType:
    """
    Blocktype enum
    """
    BLANK = 0

    GRASS = 1
    DIRT = 2
    ROAD = 3
    PAVEMENT = 4
    SAND = 5
    WATER = 6
    COBBLESTONE = 7

    TREE = 8
    FENCE = 9

    SLIDING_DOOR = 10
    BUILDING_WALL = 11
    BUILDING_WINDOW_ON = 12
    BUILDING_WINDOW_OFF = 13
    BUILDING_ROOF = 14
    BUILDING_EDGE = 15
    BUILDING_ROOF_CORNER = 16

    WOODEN_FLOOR = 17
    ENTRANCE_MAT = 18
    RUG = 19
    RUG_CORNER = 20
    RUG_EDGE = 21

    COLLIDABLES = {WATER, TREE, FENCE, BUILDING_ROOF, BUILDING_WALL, BUILDING_WINDOW_OFF, BUILDING_WINDOW_ON, BUILDING_EDGE, BLANK}
    INTERACTABLES = {SLIDING_DOOR, ENTRANCE_MAT}
    UNSAFE = {ROAD}

    @staticmethod
    def is_collidable(blocktype):
        return blocktype in BlockType.COLLIDABLES

    @staticmethod
    def is_interactable(blocktype):
        return blocktype in BlockType.INTERACTABLES

    @staticmethod
    def is_unsafe(blocktype):
        return blocktype in BlockType.UNSAFE

    @staticmethod
    def iterate():
        """
        Iterates through all BlockTypes, sorted by id
        :return: List of tuples ie [(EMPTY, 0), (ROAD, 1), ... ]
        """
        return sorted([x for x in BlockType.__dict__.items() if isinstance(x[1], int)], key=operator.itemgetter(1))

    @staticmethod
    def get_type_name(blocktype):
        """
        Debug function for getting the name of the given blocktype
        """
        for b in BlockType.__dict__.items():
            if b[1] == blocktype:
                return b[0]

    @staticmethod
    def get_class_from_type(blocktype):
        if BlockType.is_interactable(blocktype):
            if blocktype == BlockType.SLIDING_DOOR:
                return InteractableDoorBlock
            if blocktype == BlockType.ENTRANCE_MAT:
                return InteractableExitDoormatBlock

            return InteractableBlock

        if BlockType.is_collidable(blocktype):
            return CollidableBlock

        return Block


class Block:
    HELPER = None

    def __init__(self, blocktype, render_id=None):
        self.blocktype = blocktype
        self.render_id = render_id if render_id else blocktype

    def __str__(self):
        return "[%s:%s]" % (self.blocktype, self.render_id)

    @staticmethod
    def clone(block):
        cls = BlockType.get_class_from_type(block.blocktype)
        b = cls(block.blocktype, block.render_id)
        return b


class CollidableBlock(Block):
    def __init__(self, blocktype, render_id=None):
        Block.__init__(self, blocktype, render_id)
        self.collision_type = 0


class InteractableBlock(Block):
    def __init__(self, blocktype, render_id=None):
        Block.__init__(self, blocktype, render_id)

    def interact(self, human, x, y):
        pass


class InteractableCameraBlock(InteractableBlock):
    def interact_camera(self, x, y):
        pass


class InteractableDoorBlock(InteractableBlock):
    def __init__(self, blocktype, render_id=None):
        InteractableBlock.__init__(self, blocktype, render_id)
        self.building = None

    def interact(self, human, x, y):
        self.building.enter(human)

    def interact_camera(self, x, y):
        pass


class InteractableExitDoormatBlock(InteractableBlock):
    def __init__(self, blocktype, render_id=None):
        InteractableBlock.__init__(self, blocktype, render_id)
        self.building = None

    def interact(self, human, x, y):
        c = human.rect.centre
        dy = c[1] - y
        if 0 < dy <= constants.TILE_SIZE / 2:
            self.building.exit(human)

    def interact_camera(self, x, y):
        pass
