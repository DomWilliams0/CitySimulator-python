from collections import OrderedDict
import random

import pygame

import constants
import entity
import util
import world as world_module
from vec2d import Vec2d
import animation


_KEYS = [pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d]


class BaseController:
    def __init__(self, the_entity, speed):
        self.entity = the_entity
        self.speed = speed

    def tick(self):
        pass

    def halt(self):
        pass

    def __setattr__(self, key, value):
        if key == "entity" and value:
            value.controller = self
        self.__dict__[key] = value


class PlayerController(BaseController):
    def __init__(self, the_entity, speed=None):
        BaseController.__init__(self, the_entity, speed if speed else constants.Speed.SLOW)
        self.wasd = OrderedDict()
        for k in _KEYS:
            self.wasd[k] = False
        self.sprint = False

    def handle_event(self, event):
        t = event.type

        if t == pygame.KEYDOWN or t == pygame.KEYUP:
            k = event.key
            if k == pygame.K_LSHIFT:
                self.sprint = not self.sprint
                self._move_entity()

            # debug keys begin
            try:
                if t == pygame.KEYDOWN:     
                    if k == pygame.K_SPACE:
                        self.speed = random.choice(constants.Speed.VALUES)
                        self._move_entity()

                    if k == pygame.K_j:
                        util.debug_block(self.entity.rect.center, self.entity.world)

                    if k == pygame.K_n:
                        for b in self.entity.world.buildings:
                            for w in b.windows.keys():
                                b.set_window(w, random.random() < 0.5)
                    if k == pygame.K_g:
                        h = entity.Human(self.entity.world)
                        h.wander()
                        h.move_entity(*self.entity.rect.center)
            except AttributeError:
                pass
            # debug keys end

            if k in self.wasd.keys():
                self.wasd[k] = t == pygame.KEYDOWN
                self._move_entity()

    def halt(self):
        for k, _ in self.wasd.items():
            self.wasd[k] = False
            
    def _move_entity(self):
        keys = self.wasd.keys()

        def get_direction(neg, pos):
            n = self.wasd[neg]
            p = self.wasd[pos]
            speed = constants.Speed.WTF_DEBUG if self.sprint else self.speed
            return 0 if n == p else -speed if n else speed

        self.entity.velocity.x = get_direction(keys[1], keys[3])
        self.entity.velocity.y = get_direction(keys[0], keys[2])


class _PathFinder:
    def __init__(self, world, start_pos, *allowed_blocks):
        self.all_blocks = self._flood_find(world, start_pos, allowed_blocks)

    def find_path(self, goal, path_follower):
        # ah fuck...a*?
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


class SimplePathFollower(BaseController):
    """
    Causes the given entity to follow the given points in order
    """

    def __init__(self, the_entity, speed):
        """
        :param speed: The starting constants.Speed at which the entity will move
        """
        BaseController.__init__(self, the_entity, speed)
        self.speed = speed

        self.points = []
        self.current_goal = self._next_point()

        # finder = _PathFinder(the_entity.world, util.pixel_to_tile(the_entity.rect.center), (23, 6), world.BlockType.PAVEMENT_C)

        # self.add_point(9.5 * constants.TILE_SIZE, 13.5 * constants.TILE_SIZE)
        # self.add_point(9.5 * constants.TILE_SIZE, 7.5 * constants.TILE_SIZE)
        # self.add_point(26.5 * constants.TILE_SIZE, 7.5 * constants.TILE_SIZE)

        self.following = False

    def add_point(self, x, y):
        """
        Appends the given point to the end of the path
        """
        self.points.append((x, y))
        self.following = True

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
                new_vel = Vec2d.from_angle(angle, self.speed)
                self.entity.velocity = new_vel

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


# todo wander instead
class RandomPathFollower(SimplePathFollower):
    def __init__(self, the_entity, speed):
        SimplePathFollower.__init__(self, the_entity, speed)
        self._add_random_point()

    def _reached_goal(self, pos, threshold=1):
        reached_goal = SimplePathFollower._reached_goal(self, pos, threshold)
        if reached_goal:
            self._add_random_point()
        return reached_goal

    def _add_random_point(self):
        tile_range = 2
        current = self.entity.rect.center
        pixel_range = tile_range * constants.TILE_SIZE

        dx = random.randrange(-pixel_range, pixel_range + 1)
        dy = random.randrange(-pixel_range, pixel_range + 1)
        self.add_point(current[0] + dx, current[1] + dy)


class RandomWanderer(PlayerController):
    def __init__(self, the_entity):
        PlayerController.__init__(self, the_entity, constants.Speed.MEDIUM if random.random() < 0.5 else constants.Speed.SLOW)
        self.last_press = 0
        self.keys = {}

    class PhonyEvent:
        def __init__(self, etype, key):
            self.type = etype
            self.key = key

    def _move(self, key, pressdown):
        self.handle_event(self.PhonyEvent(pygame.KEYDOWN if pressdown else pygame.KEYUP, key))

    def tick(self):
        self.last_press -= 1
        if self.last_press < 0:
            self.last_press = random.randrange(1, 12)

            # choose random key to press
            if len(self.keys) < 2 and random.random() < 0.1:
                newkey = random.choice(_KEYS)
                if newkey not in self.keys:
                    self.keys[newkey] = random.randrange(1, 8)
                    self._move(newkey, True)

            # press/unpress all
            for key, time in self.keys.items():
                time -= 1
                release = time < 0
                if release:
                    del self.keys[key]
                else:
                    self.keys[key] = time
                self._move(key, not release)

                # key = random.choice([pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d])
                # e = self.PhonyEvent(pygame.KEYDOWN if random.random() < 0.5 else pygame.KEYUP, key)
                # self.handle_event(e)
