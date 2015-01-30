from collections import OrderedDict
import random

import pygame

import constants
import entity
import util
from vec2d import Vec2d


_KEYS = [pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d]
_VERTICAL_KEYS = [_KEYS[0], _KEYS[2]]


class BaseController:
    def __init__(self, the_entity, speed=None):
        self.entity = the_entity
        self.speed = constants.Speed.SLOW if speed is None else speed
        self.boost_speed = constants.Speed.FAST if self.speed < constants.Speed.FAST else constants.Speed.MAX
        self.boost = False
        self.wasd = OrderedDict()

        for k in _KEYS:
            self.wasd[k] = False

        self._behaviours = util.Stack()

    def add_behaviour(self, b):
        self._behaviours.push(b)

    def remove_current_behaviour(self):
        self._behaviours.pop()

    def set_suppressed_behaviours(self, suppress):
        if suppress and self._behaviours.top is not None:
            self.add_behaviour(None)
        elif not suppress and self._behaviours.top is None:
            self.remove_current_behaviour()


    def tick(self):
        if self._behaviours.top:
            self._behaviours.top.tick()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN or event.type == pygame.KEYUP:
            self.handle(event.type == pygame.KEYDOWN, event.key)

    def handle(self, keydown, key):
        if key == pygame.K_LSHIFT:
            self.boost = not self.boost
            self._move_entity()

        elif key in self.wasd.keys():
            self.wasd[key] = keydown
            self._move_entity()

    def halt(self):
        for k, _ in self.wasd.items():
            self.wasd[k] = False

    def __setattr__(self, key, value):
        if key == "entity" and value:
            value.controller = self
        self.__dict__[key] = value

    def _get_direction(self, vertical):
        n = self._key_from_index(0 if vertical else 1)
        p = self._key_from_index(2 if vertical else 3)
        return 0 if n == p else -1 if n else 1

    def _get_speed(self):
        return self.boost_speed if self.boost else self.speed

    def _move_entity(self):
        speed = self._get_speed()
        self.entity.velocity.x = self._get_direction(False) * speed
        self.entity.velocity.y = self._get_direction(True) * speed

    def _key_from_index(self, i):
        return self.wasd[_KEYS[i]]

    def _direction_from_key(self, key):
        if key in _VERTICAL_KEYS:
            return constants.Direction.NORTH if key == _KEYS[0] else constants.Direction.SOUTH
        else:
            return constants.Direction.WEST if key == _KEYS[1] else constants.Direction.WEST


class HumanController(BaseController):
    """
    Used for other player input, such as inventory
    """

    def handle(self, keydown, key):
        BaseController.handle(self, keydown, key)

        # debug keys
        try:
            if keydown:
                if key == pygame.K_SPACE:
                    self.speed = random.choice(constants.Speed.VALUES)
                    self._move_entity()

                if key == pygame.K_j:
                    util.debug_block(self.entity.rect.center, self.entity.world)

                if key == pygame.K_n:
                    for b in self.entity.world.buildings:
                        for w in b.windows.keys():
                            b.set_window(w, random.random() < 0.5)
                if key == pygame.K_g:
                    h = entity.Human(self.entity.world)
                    h.wander()
                    h.move_entity(*self.entity.rect.center)

                if key == pygame.K_h:
                    v = entity.Vehicle(self.entity.world)
                    v.move_entity(*self.entity.rect.center)
        except AttributeError:
            pass


class VehicleController(BaseController):
    def __init__(self, vehicle):
        BaseController.__init__(self, vehicle, constants.Speed.VEHICLE_MIN)

        self._keystack = util.Stack()
        self._lasttop = None

        self._brake_force = 1
        assert 0 <= self._brake_force <= 1
        self.braking = True

        self.current_speed = 0
        self.acceleration = 1.03
        self.max_speed = constants.Speed.VEHICLE_MAX

        self.last_pos = self.entity.aabb.topleft

    def _get_speed(self):
        if self.entity.is_moving() and util.distance_sqrd(self.entity.aabb.topleft, self.last_pos) < self.acceleration:
            self.current_speed = 0
            print "hit!"  # todo: this should only fire once

        return self.current_speed

    def tick(self):
        current = self._keystack.top

        # todo: only change direction to opposite if stopped, otherwise brake

        # no input
        self.braking = current is None
        if not self.braking:
            self._brake_force = 1
        elif self.entity.is_moving():
            self._brake_force *= 0.995

        # input
        if current is not None:
            for k, v in self.wasd.items():
                self.wasd[k] = (k == current)

            # starting to move
            if not self.current_speed:
                self.current_speed = self.acceleration * (2 / constants.DELTA)  # start with 1 seconds worth of acceleration
            else:
                self.current_speed *= self.acceleration

            # limit to max speed
            if self.current_speed > self.max_speed:
                self.current_speed = self.max_speed

        self._move_entity()
        self.last_pos = self.entity.aabb.topleft

    def _move_entity(self):
        if self.braking:
            self.entity.velocity *= self._brake_force
            if self.entity.velocity and self.entity.velocity.get_length_sqrd() < constants.TILE_SIZE_SQRD:
                self.halt()
        else:
            BaseController._move_entity(self)

    def handle(self, keydown, key):
        if key in _KEYS:
            last_top = self._keystack.top
            if keydown:
                self._keystack.push(key)
            else:
                self._keystack.remove_item(key)

            if last_top != self._keystack.top:
                self._lasttop = last_top

    def halt(self):
        BaseController.halt(self)
        self.entity.velocity.zero()
        self.current_speed = 0


class BaseBehaviour:
    def __init__(self, the_entity):
        self.entity = the_entity
        self.controller = the_entity.controller

    def tick(self):
        pass

    def handle(self, keydown, key):
        self.controller.handle(keydown, key)


class RandomHumanWanderer(BaseBehaviour):
    def __init__(self, the_entity):
        # BaseController.__init__(self, the_entity, constants.Speed.MEDIUM if random.random() < 0.5 else constants.Speed.SLOW)
        BaseBehaviour.__init__(self, the_entity)
        self.last_press = 0
        self.keys = {}

    def tick(self):
        self.last_press -= 1
        if self.last_press < 0:
            self.last_press = random.randrange(1, 12)

            # choose random key to press
            if len(self.keys) < 2 and random.random() < 0.1:
                newkey = random.choice(_KEYS)
                if newkey not in self.keys:
                    self.keys[newkey] = random.randrange(1, 8)
                    self.handle(True, newkey)

            # press/unpress all
            for key, time in self.keys.items():
                time -= 1
                release = time < 0
                if release:
                    del self.keys[key]
                else:
                    self.keys[key] = time

                self.handle(not release, key)


class SimpleVehicleFollower(BaseBehaviour):
    """
    Causes the given entity to follow the given points in order
    """

    class _PathFinder:
        def __init__(self, world, start_pos, *allowed_blocks):
            self.all_blocks = self._flood_find(world, start_pos, allowed_blocks)

        def find_path(self, goal, path_follower):
            # ah fuck, what now
            pass

        # noinspection PyMethodMayBeStatic
        def _flood_find(self, world, pos, allowed_blocktypes):
            stack = set()
            results = []
            allowed_blocktypes = set(allowed_blocktypes)
            stack.add(pos)

            while stack:
                (x, y) = stack.pop()
                block = world.get_block(x, y)
                if block.blocktype in allowed_blocktypes and (x, y) not in results:
                    results.append((x, y))
                    if x > 0:
                        stack.add((x - 1, y))
                    if x < world.tile_width - 1:
                        stack.add((x + 1, y))
                    if y > 0:
                        stack.add((x, y - 1))
                    if y < world.tile_height - 1:
                        stack.add((x, y + 1))
            return results

    def __init__(self, the_entity):
        """
        :param speed: The starting constants.Speed at which the entity will move
        """
        BaseBehaviour.__init__(self, the_entity)

        self.points = []
        self.current_goal = self._next_point()

        # finder = _PathFinder(the_entity.world, util.pixel_to_tile(the_entity.rect.center), (23, 6), world.BlockType.PAVEMENT_C)

        self.add_point(33, 8)
        self.add_point(36, 28)
        self.following = True

    def add_point(self, tilex, tiley):
        """
        Appends the given point to the end of the path
        """
        self.points.append((tilex * constants.TILE_SIZE, tiley * constants.TILE_SIZE))

    def _next_point(self):
        try:
            p = self.points.pop(0)
        except IndexError:
            p = None
        return p

    def tick(self):
        """
        Sets the velocity of the entity, in order to walk directly towards its next goal
        It is pushed once in the right direction; its velocity is only updated when it reaches a goal
        """
        pos = self.entity.rect.center

        # debug draw nodes
        for p in self.points:
            constants.SCREEN.draw_circle(p)

        if not self.following:
            return

        if not self.current_goal or self._reached_goal(pos):
            self.current_goal = self._next_point()
            # print("switched to", self.current_goal, self.points)

            # new goal
            if self.current_goal:
                goal = self.current_goal
                direction = Vec2d(goal[0] - pos[0], goal[1] - pos[1])

                angle = util.round_to_multiple(direction.get_angle(), 45)
                # new_vel = Vec2d.from_angle(angle, self.speed)
                # self.entity.velocity = new_vel

            # end goal reached
            else:
                self.entity.velocity.zero()
                self.following = False
                return

        constants.SCREEN.draw_line(pos, self.current_goal)

    def _reached_goal(self, pos, threshold=2):
        x = abs(pos[0] - self.current_goal[0])
        y = abs(pos[1] - self.current_goal[1])
        dist_squared = x * x + y * y
        return dist_squared < constants.TILE_SIZE / threshold ** 2
