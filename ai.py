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
        self.speed = constants.Speed.SLOW if speed is None else speed
        self.boost = False
        self.wasd = OrderedDict()
        
        for k in _KEYS:
            self.wasd[k] = False
        
    def tick(self):
        pass
            
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

    def _get_direction(self, neg, pos):
        n = self.wasd[neg]
        p = self.wasd[pos]
        speed = constants.Speed.FAST if self.boost else self.speed
        return 0 if n == p else -speed if n else speed
        
    def _move_entity(self):
        keys = self.wasd.keys()
        self.entity.velocity.x = self._get_direction(keys[1], keys[3])
        self.entity.velocity.y = self._get_direction(keys[0], keys[2])


class PlayerController(BaseController):
    def __init__(self, the_entity, speed=None):
        BaseController.__init__(self, the_entity, speed)
        
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
        except AttributeError:
            pass


class VehicleController(BaseController):
    def __init__(self, vehicle):
        BaseController.__init__(self, vehicle, constants.Speed.MAX)
    
    def tick(self):
        # maintain speed if key is pressed, otherwise slow down/friction
        pass
    
    def handle(self, keydown, key):
        # if current direction: speed up, else slow down
        pass
        
    def halt(self):
        # apply other direction until stopped
        pass

class RandomWanderer(BaseController):
    def __init__(self, the_entity):
        BaseController.__init__(self, the_entity, constants.Speed.MEDIUM if random.random() < 0.5 else constants.Speed.SLOW)
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
