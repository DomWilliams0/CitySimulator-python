from collections import OrderedDict
import random

import pygame

import constants
import entity
import event
import util


_KEYS = [pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d]
_VERTICAL_KEYS = [_KEYS[0], _KEYS[2]]
_BRAKE_KEY = pygame.K_SPACE
_KEY_DIRECTIONS = [3, 1, 0, 2]


class BaseController:
    def __init__(self, the_entity):
        self.entity = the_entity
        self.wasd = OrderedDict()

        for k in _KEYS:
            self.wasd[k] = False

        self.behaviour_tree = None
        self._suppressed_behaviour = False

    # self._behaviours = util.Stack()
    #
    # def add_behaviour(self, b):
    # self._behaviours.push(b)
    #
    # def remove_current_behaviour(self):
    # self._behaviours.pop()
    #
    # def set_suppressed_behaviours(self, suppress):
    # if suppress and self._behaviours.top is not None:
    #         self.add_behaviour(None)
    #     elif not suppress and self._behaviours.top is None:
    #         self.remove_current_behaviour()
    #
    # def _tick_current_behaviour(self):
    #     top_exists = self._behaviours.top is not None
    #     if top_exists:
    #         self._behaviours.top.tick()
    #     return top_exists

    def suppress(self, suppressed):
        self._suppressed_behaviour = suppressed

    def tick(self):
        # debug btree will not be None when not debugging
        if not self.behaviour_tree:
            return

        if not self._suppressed_behaviour:
            self.behaviour_tree.tick()

    def handle_event(self, e):
        self.handle(*event.simplify_key_event(e))

    def move_in_direction(self, direction, stop=True):
        if stop:
            self.halt()
        self.handle(True, self._direction_to_key(direction))

    def handle(self, keydown, key):
        if key in self.wasd.keys():
            self.wasd[key] = keydown
            self._move_entity()

    def halt(self):
        for k in self.wasd:
            self.wasd[k] = False
        self._move_entity()

    def _get_direction(self, vertical):
        n = self._key_from_index(0 if vertical else 1)
        p = self._key_from_index(2 if vertical else 3)
        return 0 if n == p else -1 if n else 1

    def _get_speed(self):
        raise NotImplementedError()

    def _move_entity(self):
        speed = self._get_speed()
        self.entity.velocity.x = self._get_direction(False) * speed
        self.entity.velocity.y = self._get_direction(True) * speed

    def _key_from_index(self, i):
        return self.wasd[_KEYS[i]]

    @staticmethod
    def _key_to_direction(key):
        if key in _VERTICAL_KEYS:
            return constants.Direction.NORTH if key == _KEYS[0] else constants.Direction.SOUTH
        else:
            return constants.Direction.WEST if key == _KEYS[1] else constants.Direction.EAST

    @staticmethod
    def _direction_to_key(direction):
        return _KEYS[_KEY_DIRECTIONS.index(direction)]


class InputController:
    def __init__(self):
        # self.controllers = {entity.Human: BaseController, entity.Vehicle: VehicleController}
        self.entity = None
        self.current = None

    def control(self, the_entity):
        # cls = self.controllers.get(the_entity.__class__)
        # if cls:
        # self.entity = the_entity
        # self.current = the_entity.controller
        # self.current = cls(the_entity)

        if self.current:
            self.current.suppress(False)
        self.current = the_entity.controller
        self.current.suppress(True)
        self.entity = the_entity

    def handle(self, e):
        if not self.current:
            return

        se = event.simplify_key_event(e)
        if not se:
            return

        keydown, key = se

        self.current.handle(keydown, key)

        try:
            if keydown:
                if key == pygame.K_j:
                    util.debug_block(self.entity.rect.center, self.entity.world)

                if key == pygame.K_n:
                    for b in self.entity.world.buildings:
                        for w in b.windows.keys():
                            b.set_window(w, random.random() < 0.5)
                if key == pygame.K_g:
                    h = entity.Human(self.entity.world)
                    h.move_entity(*self.entity.rect.center)

                if key == pygame.K_h:
                    v = entity.Vehicle(self.entity.world)
                    v.move_entity(*self.entity.rect.center)

                if key == pygame.K_l:
                    print(self.entity.get_current_tile())
        except AttributeError:
            pass


class HumanController(BaseController):
    def __init__(self, the_entity):
        BaseController.__init__(self, the_entity)
        self.sprint = False
        self.speed = random.randrange(constants.Speed.HUMAN_MIN, constants.Speed.HUMAN_FAST)
        self.sprint_speed = self.speed + random.randrange(constants.Speed.HUMAN_MAX - self.speed)

        # walk = EntityMoveToLocation(self, (random.randrange(13, 19), random.randrange(6, 12)))
        # debug = DebugPrint("I, %r, am hearby debugged" % hex(id(self.entity)))
        self.behaviour_tree = BehaviourTree(self, Repeater(EntityWander(self)))

    def _get_speed(self):
        return self.sprint_speed if self.sprint else self.speed

    def handle(self, keydown, key):
        if key == pygame.K_LSHIFT:
            self.sprint = not self.sprint
            self._move_entity()
        else:
            BaseController.handle(self, keydown, key)


class VehicleController(BaseController):
    STOPPED = 0
    BRAKING = 1
    DRIFTING = 2
    ACCELERATING = 3

    class Pedal:
        def __init__(self, brake_time, accelerating=False):
            self.brake_time = brake_time
            self._was_applied = False
            self._applied = False
            self._gen = None
            self.accelerating = accelerating
            if accelerating:
                self._default_force = 1
                self._variation = 0.9
                self._func = lambda force, division, count: max(1, 0.9 + (1 / ((count + 1) / 2.0)))
            else:
                self._default_force = 0
                self._variation = 0.2
                self._func = lambda force, division, count: force - division

        def is_applied(self):
            return self._applied

        def set_applied(self, applied):
            self._was_applied = self._applied
            self._applied = applied

            if applied != self._was_applied:
                if applied:
                    self._gen = self._pedal_force_gen(self.brake_time)
                else:
                    self._gen = None

        def get_force(self):
            force = next(self._gen, 1)
            return force

        def _pedal_force_gen(self, brake_time, tick_count=20):
            division = self._variation / tick_count
            # if self.accelerating:
            # division *= -1

            force = 1
            time_passed = 0
            step = float(brake_time) / tick_count
            next_step = 0
            count = 0

            while time_passed <= brake_time:
                time_passed += constants.DELTA
                if time_passed >= next_step:
                    count += 1
                    next_step += step
                    force = self._func(force, division, count)
                    yield force
                else:
                    yield 1

            yield self._default_force

    def __init__(self, vehicle):
        BaseController.__init__(self, vehicle)
        # self.add_behaviour(SimpleVehicleFollower(vehicle))
        # todo: add new sub-behaviour to go towards a target, then use for path follower
        # todo also base human movement on vehicle, instead of setting velocity directly

        self._keystack = util.Stack()
        self._lasttop = None

        self.brake = VehicleController.Pedal(0.5)
        self.drift_brake = VehicleController.Pedal(self.brake.brake_time * 2)
        self.accelerator = VehicleController.Pedal(5, accelerating=True)
        self.pedals = {VehicleController.BRAKING: self.brake, VehicleController.DRIFTING: self.drift_brake,
                       VehicleController.ACCELERATING: self.accelerator}

        self.current_speed = 0
        self.acceleration = 1.03
        self.max_speed = constants.Speed.VEHICLE_MAX * random.uniform(0.75, 1)
        self.last_pos = self.entity.aabb.topleft

        self.state = VehicleController.STOPPED
        self.last_directions = [0, 0]
        self.last_state = self.state

    def _get_speed(self):
        return self.current_speed

    def _get_direction(self, vertical):

        if self.state == VehicleController.STOPPED:
            return 0

        if self.state == VehicleController.BRAKING or self.state == VehicleController.DRIFTING:
            return self.last_directions[vertical]

        top = self._get_pressed_key()

        if vertical:
            if top == _KEYS[2]:
                return 1
            elif top == _KEYS[0]:
                return -1
        else:
            if top == _KEYS[3]:
                return 1
            elif top == _KEYS[1]:
                return -1

        return 0

    def __setattr__(self, key, value):
        if key == "state" and value != VehicleController.STOPPED:
            self.press_pedal(value)
        self.__dict__[key] = value

    def press_pedal(self, state):
        for s, pedal in self.pedals.items():
            pedal.set_applied(s == state)

    def _get_applied_pedal_force(self):
        for p in self.pedals.values():
            if p.is_applied():
                return p.get_force()
        return None

    def tick(self):
        # todo: only change direction to opposite if stopped, otherwise brake
        BaseController.tick(self)
        # self.btree.tick()

        # None if no key, brake_key if brake is held down
        current = self._get_pressed_key()

        # update state
        if current == _BRAKE_KEY:
            if self.state == VehicleController.ACCELERATING or self.state == VehicleController.DRIFTING:
                self.state = VehicleController.BRAKING

        elif current is None:
            if self.state == VehicleController.ACCELERATING:
                self.state = VehicleController.DRIFTING

        else:
            self.state = VehicleController.ACCELERATING

        if self.state == VehicleController.ACCELERATING:
            if self.current_speed == 0:
                self.current_speed = constants.TILE_SIZE

        if self.state != VehicleController.STOPPED:
            self.press_pedal(self.state)
            force = self._get_applied_pedal_force()
            if force is not None:
                self.current_speed *= force

            # limit to max speed
            if self.current_speed > self.max_speed:
                self.current_speed = self.max_speed

        self._move_entity()
        self.last_pos = self.entity.aabb.topleft
        self.last_directions[0], self.last_directions[1] = self._get_direction(False), self._get_direction(True)

        # if self.state != self.last_state:
        # print(">>>>> %s" % util.get_enum_name(VehicleController, self.state))
        self.last_state = self.state

        """
            pseudo
            if brake key is held:
                if accelerating or drifting:
                    state = BRAKING
                else
                    state = STOPPED

            else if no key is held:
                if state is ACCELERATING:
                    state = DRIFTING

            else movement key is held
                state = ACCELERATING regardless

            THEN:

            switch state:
                BRAKING: apply brake
                ACCELERATING: apply acceleration, clamp speed
                DRIFTING: apply drag
                STOPPED: nothing
        """

    def _move_entity(self):
        # if self.brake.is_applied():
        # self.current_speed *= self.brake.get_force()

        if self.state != VehicleController.ACCELERATING and self.state != VehicleController.STOPPED and self._has_virtually_stopped():
            self.halt()

        else:
            BaseController._move_entity(self)

    def _has_virtually_stopped(self):
        return self.current_speed < constants.TILE_SIZE

    def handle(self, keydown, key):
        if key in _KEYS:
            last_top = self._keystack.top
            if keydown:

                # todo: is this necessary? a car can turn around quickly enough to make this restriction redundant
                # register = True
                # if self.state != VehicleController.STOPPED:
                # current_direction = self.entity.direction
                # key_press_direction = self._key_to_direction(key)
                # key_opposite = constants.Direction.opposite(key_press_direction)
                #
                # if key_opposite == current_direction:
                # register = False
                #
                # if register:
                # self._keystack.push(key)
                if key != last_top:
                    self._keystack.push(key)
            else:
                self._keystack.remove_item(key)

            if last_top != self._keystack.top:
                self._lasttop = last_top
        # brake
        elif key == _BRAKE_KEY:
            self.brake.set_applied(keydown)

    def _get_pressed_key(self):
        return self._keystack.top if not self.brake.is_applied() else _BRAKE_KEY

    def halt(self):
        BaseController.halt(self)
        self.entity.velocity.zero()
        self.current_speed = 0
        self.state = VehicleController.STOPPED


# class BaseBehaviour:
# def __init__(self, the_entity):
# self.entity = the_entity
# self.controller = the_entity.controller
#
#     def tick(self):
#         pass
#
#     def handle(self, keydown, key):
#         self.controller.handle(keydown, key)
#
#
# class RandomHumanWanderer(BaseBehaviour):
#     def __init__(self, the_entity):
#         # BaseController.__init__(self, the_entity, constants.Speed.MEDIUM if random.random() < 0.5 else constants.Speed.SLOW)
#         BaseBehaviour.__init__(self, the_entity)
#         self.ticker = util.TimeTicker((0.05, 0.4))
#
#         self.keys = {}
#
#     def tick(self):
#         if self.ticker.tick():
#             # choose random key to press
#             if random.random() < (0.3 if len(self.keys) < 2 else 0.1):
#                 newkey = random.choice(_KEYS)
#                 if newkey not in self.keys:
#                     self.keys[newkey] = random.randrange(1, 8)
#                     self.handle(True, newkey)
#
#             # press/unpress all
#             for key, time in self.keys.items():
#                 time -= 1
#                 release = time < 0
#                 if release:
#                     del self.keys[key]
#                 else:
#                     self.keys[key] = time
#
#                 self.handle(not release, key)
#
#                 # class SimpleVehicleFollower(BaseBehaviour):
#                 # """
#                 # Causes the given entity to follow the given points in order
#                 # """
#                 #
#                 # class _PathFinder:
#                 # def __init__(self, world, start_pos, *allowed_blocks):
#                 # self.all_blocks = self._flood_find(world, start_pos, allowed_blocks)
#                 #
#                 # def find_path(self, goal, path_follower):
#                 # # ah fuck, what now
#                 # pass
#                 #
#                 # # noinspection PyMethodMayBeStatic
#                 # def _flood_find(self, world, pos, allowed_blocktypes):
#                 # stack = set()
#                 # results = []
#                 # allowed_blocktypes = set(allowed_blocktypes)
#                 # stack.add(pos)
#                 #
#                 # while stack:
#                 # (x, y) = stack.pop()
#                 # block = world.get_block(x, y)
#                 # if block.blocktype in allowed_blocktypes and (x, y) not in results:
#                 # results.append((x, y))
#                 # if x > 0:
#                 # stack.add((x - 1, y))
#                 # if x < world.tile_width - 1:
#                 # stack.add((x + 1, y))
#                 # if y > 0:
#                 # stack.add((x, y - 1))
#                 # if y < world.tile_height - 1:
#                 # stack.add((x, y + 1))
#                 # return results
#                 #
#                 # def __init__(self, vehicle):
#                 # BaseBehaviour.__init__(self, vehicle)
#                 # assert isinstance(vehicle, entity.Vehicle)
#                 #
#                 # self.points = []
#                 #
#                 # # finder = _PathFinder(the_entity.world, util.pixel_to_tile(the_entity.rect.center), (23, 6), world.BlockType.PAVEMENT_C)
#                 #         # debug test
#                 #         self.add_point(5, 8)
#                 #         self.add_point(33, 8)
#                 #         self.add_point(36, 28)
#                 #
#                 #         self.current_goal = self._next_point()
#                 #         self.following = True
#                 #
#                 #     def add_point(self, tilex, tiley):
#                 #         """
#                 #         Appends the given point to the end of the path
#                 #         """
#                 #         self.points.append((tilex * constants.TILE_SIZE, tiley * constants.TILE_SIZE))
#                 #
#                 #     def _next_point(self):
#                 #         try:
#                 #             p = self.points.pop(0)
#                 #         except IndexError:
#                 #             p = None
#                 #         return p
#                 #
#                 #     def tick(self):
#                 #         pos = self.entity.rect.center
#                 #
#                 #         # debug draw nodes
#                 #         for p in self.points:
#                 #             constants.SCREEN.draw_circle(p)
#                 #
#                 #         if not self.following:
#                 #             return
#                 #
#                 #         # drive towards
#                 #         if not self._reached_goal(pos):
#                 #             direction = Vec2d(self.current_goal[0] - pos[0], self.current_goal[1] - pos[1])
#                 #             angle = direction.get_angle()
#                 #             halfangle = util.round_to_multiple(angle, 45)
#                 #
#                 #         else:
#                 #             self.controller.halt()
#                 #             self.current_goal = self._next_point()
#                 #             if not self.current_goal:  # complete
#                 #                 self.following = False
#                 #
#                 #         if self.current_goal:
#                 #             constants.SCREEN.draw_line(pos, self.current_goal)
#                 #
#                 #     def _reached_goal(self, pos):
#                 #         return util.distance_sqrd(pos, self.current_goal) < constants.TILE_SIZE_SQRD * 2


# behaviour tree goodness
class BehaviourTree:
    def __init__(self, entity_controller, tree):
        self.root = None
        self.current = None
        # self.data_context = {}
        self.controller = entity_controller

        # debug example
        # sequence = Sequence(self.data_context,
        # EntityMoveToLocation(entity_controller, (36, 7)),
        #                     DebugPrint())
        #
        # self.root = Repeater(sequence, self.data_context)

        self.root = tree
        self.current = self.root

        self.current.init()

    def tick(self):
        # todo: don't traverse the tree each frame
        # todo: INTERUPTIONS?!
        self.current.process()


class Task:
    RUNNING = 0
    FAILURE = 1
    SUCCESS = 2

    def __init__(self, *children):
        # self.data_context = data_context
        self.children_tasks = list(children)

    def init(self):
        pass

    def end(self):
        pass

    def process(self):
        # returns its new state?
        pass


class LeafTask(Task):
    def __init__(self):
        # leaves have no children
        Task.__init__(self)


# nodes have multiple children
# leaves have no children; None children list?


class Composite(Task):
    def __init__(self, *children):
        Task.__init__(self, *children)
        self.children_stack = util.Stack()

    def init(self):
        for child in reversed(self.children_tasks):
            # child.data_context = self.data_context
            self.children_stack.push(child)
        self.children_stack.top.init()

    def end(self):
        self.children_stack.clear()

    def _process_current(self):
        current = self.children_stack.top
        return current.process()


class Sequence(Composite):
    def process(self):
        state = self._process_current()

        # next sequence
        if state == Task.SUCCESS:

            # end current
            last_child = self.children_stack.pop()
            last_child.end()
            if not self.children_stack:
                # all children complete
                return Task.SUCCESS
            else:
                # running the next child
                self.children_stack.top.init()
                return Task.RUNNING

        # either running or failure: propogate this state up to the parent
        else:
            return state


class Selector(Composite):
    def process(self):
        state = self._process_current()

        if state == Task.FAILURE:
            self.children_stack.top.end()
            self.children_stack.pop()

            # all children failed
            if not self.children_stack:
                return Task.FAILURE

            # start new child
            self.children_stack.top.init()

        # either success or running: propogate to parent
        else:
            return state


class Decorator(Task):
    def __init__(self, child):
        Task.__init__(self)
        self.child = child
        # if child:
        # child.parent = self

    def init(self):
        self.child.init()

    def end(self):
        self.child.end()


class Inverter(Decorator):
    def process(self):
        state = self.child.process()

        # still running
        if state == Task.RUNNING:
            return state

        # invert
        else:
            if state == Task.SUCCESS:
                return Task.FAILURE
            else:
                return Task.SUCCESS


class Succeeder(Decorator):
    def process(self):
        state = self.child.process()

        # still running
        if state == Task.RUNNING:
            return state

        # always success
        else:
            return Task.SUCCESS


class Repeater(Decorator):
    def __init__(self, child, repeat_times=-1):
        Decorator.__init__(self, child)
        self.repeat_times = repeat_times

    def process(self):
        state = self.child.process()

        # still running
        if state == Task.RUNNING:
            return state

        else:
            # repeat a number of times
            if self.repeat_times > 0:
                self.repeat_times -= 1
                if self.repeat_times == 0:
                    return Task.SUCCESS

        # restart
        self.child.end()
        self.child.init()
        return Task.RUNNING


class RepeatUntilFail(Decorator):
    def process(self):
        state = self.child.process()

        # restart child on success
        if state == Task.SUCCESS:
            self.child.begin()
            return Task.RUNNING

        # failure and running
        else:
            return state


# leaf tasks/actions
class EntityLeafTask(LeafTask):
    def __init__(self, entity_controller):
        LeafTask.__init__(self)
        self.entity = entity_controller.entity
        self.controller = entity_controller

    def _bool_to_condition(self, b):
        return Task.SUCCESS if b else Task.FAILURE


class EntityMoveToLocation(EntityLeafTask):
    def __init__(self, controller, target_location):
        EntityLeafTask.__init__(self, controller)
        self.target_location = util.tile_to_pixel(target_location)
        self._size = self.entity.aabb.width

    def process(self):
        dx, dy = self.target_location[0] - self.entity.aabb.x, self.target_location[1] - self.entity.aabb.y

        # arrived
        sqrd = util.distance_sqrd(self.entity.aabb.topleft, self.target_location)
        if sqrd < self._size ** 2:
            return Task.SUCCESS

        # crashed? todo
        # elif not self.vehicle.is_moving():
        # return Task.FAILURE

        # get movement direction
        if abs(dx) > self._size:
            direction = constants.Direction.EAST if dx > 0 else constants.Direction.WEST
        else:
            direction = constants.Direction.SOUTH if dy > 0 else constants.Direction.NORTH

        # move
        self.controller.move_in_direction(direction)
        return Task.RUNNING


class EntityWander(EntityLeafTask):
    def __init__(self, entity_controller):
        EntityLeafTask.__init__(self, entity_controller)
        self.ticker = util.TimeTicker((0.1, 0.8))
        # self.no_obstacle = NoObstacle(entity_controller)

    def init(self):
        self.ticker.reset()

    def process(self):
        # todo: is forever running

        if self.ticker.tick():
            if random.random() < 0.4:
                direction = constants.Direction.random()

                # if self.no_obstacle.process() == Task.FAILURE:
                if self.entity.world.is_direction_blocked(self.entity.get_current_tile(), direction):
                    direction = constants.Direction.opposite(direction)

                self.controller.move_in_direction(direction)
            else:
                self.controller.halt()

        return Task.RUNNING


class NoObstacle(EntityLeafTask):
    def process(self):
        return self._bool_to_condition(not self.entity.world.is_direction_blocked(self.entity.get_current_tile(), self.entity.direction))


class DebugPrint(LeafTask):
    def __init__(self, msg):
        LeafTask.__init__(self)
        self.msg = msg

    def process(self):
        print(self.msg)
        return Task.SUCCESS
