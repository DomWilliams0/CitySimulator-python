import random

import constants
import entity
import event
import util
import world as world_module


class Building:
    def __init__(self, world, x, y, width, height, name):
        """
        :param name: World file, without extension
        """
        self.world = world
        self.rect = util.Rect(x, y, width, height)
        self.doors = []
        self.windows = {}
        self.inside = world_module.BuildingWorld.load_tmx(name + ".tmx")

        # find entrance mats inside
        for bx, by, b in self.inside.iterate_blocks():
            if b.blocktype == world_module.BlockType.ENTRANCE_MAT:
                b.building = self
                pixel_pos = util.tile_to_pixel((bx + 1, by))
                self.doors.append([pixel_pos])
                self.inside.add_spawn(constants.EntityType.HUMAN, *pixel_pos)

        # find doors in terrain layer
        d = 0
        for bx, by, b in self.iterate_blocks():
            if b.blocktype == world_module.BlockType.SLIDING_DOOR:
                b.building = self
                for j in xrange(d, d + 2):
                    self.doors[j].append(util.tile_to_pixel((bx, by)))
                d += 2

        if d != len(self.doors):
            raise StandardError("Mismatching entrances: %d doors but %d exit mats" % (d, len(self.doors)))

        # find windows in overterrain layer
        for bx, by, b in self.iterate_blocks(layer="overterrain"):
            if b.blocktype == world_module.BlockType.BUILDING_WINDOW_OFF or b.blocktype == world_module.BlockType.BUILDING_WINDOW_ON:
                # power = b.blocktype == world_module.BlockType.BUILDING_WINDOW_ON
                power = random.random() < 0.5
                self.set_window((bx, by), power)

    def iterate_blocks(self, layer="terrain"):
        """
        :return: Generator for all terrain tiles in the building space
        """
        br = self.rect.bottomright
        for b in self.world.iterate_blocks(self.rect.x, self.rect.y, *br, layer=layer):
            yield b

    def _closest_door_index(self, position, entering):
        """
        :param entering: True if entering, otherwise exiting
        :return: The closest door spawn index
        """
        return min(enumerate(util.distance_sqrd(l[1 if entering else 0], position) for l in self.doors), key=lambda x: x[1])[0]

    def get_closest_exit(self, position):
        """
        :return: The appropriate outside world position, relating to the given inside pixel coordinate
        """
        index = self._closest_door_index(position, False)
        return self.doors[index][1]

    def enter(self, human):
        """
        Places the given human in the building.
        If they are already inside, nothing happens
        """
        if human not in self.inside.entities:
            human.visible = False

            self.inside.spawn_entity_at_spawn(human, self._closest_door_index(human.transform, True), vary=False)
            human.turn(entity.constants.Direction.NORTH)

            event.call_human_building_movement(human, self, True)

    def exit(self, human):
        """
        Makes the given human leave the building.
        If they are not inside, nothing happens
        """
        try:
            door = self.get_closest_exit(human.transform)
            self.world.spawn_entity(human)

            # vary exit point slightly so everyone doesn't appear in the same place when leaving       
            human.move_entity((door[0] + random.randrange(constants.TILE_SIZE), door[1] + constants.TILE_SIZE * 1.5 + random.randrange(constants.TILE_SIZE / 4)))
            human.turn(entity.constants.Direction.SOUTH)

            event.call_human_building_movement(human, self, False)

        except ValueError:
            pass

    def set_window(self, pos, new_status):  # todo state*, surely?
        """
        Turns on/off the window at the given position
        """
        self.windows[pos] = new_status
        new_blocktype = world_module.BlockType.BUILDING_WINDOW_ON if new_status else world_module.BlockType.BUILDING_WINDOW_OFF
        self.world.set_block_type(pos[0], pos[1], new_blocktype, layer="overterrain")

    def get_window(self, pos):
        """
        :return: Whether or not the window at the given position is switched on
        """
        return self.windows[pos]
