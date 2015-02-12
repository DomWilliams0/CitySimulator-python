from collections import OrderedDict
import random

import pygame

import constants
import entity
import event
import util


class BaseController:
    """
    Base controller for entities, keeping track of pressed directional keys and the behaviour tree
    """

    def __init__(self, the_entity):
        self.entity = the_entity
        self.wasd = OrderedDict()

        for k in constants.Input.DIRECTIONAL_KEYS:
            self.wasd[k] = False

        self.behaviour_tree = None
        self._suppressed_behaviour = False

    def suppress_ai(self, suppressed):
        """
        :param suppressed: Should the behaviour tree be suppressed, ie is this entity being controlled from elsewhere
        """
        self._suppressed_behaviour = suppressed

    def tick(self):
        # debug btree will not be None when not debugging
        if not self.behaviour_tree:
            return

        if not self._suppressed_behaviour:
            self.behaviour_tree.tick()

    def handle_event(self, e):
        """
        :return: True if event has been processed and hence consumed, otherwise False
        """
        key_event = event.simplify_key_event(e)
        if key_event:
            self.handle(*key_event)
            return True
        return False

    def move_in_direction(self, direction, stop=True):
        """
        :param direction: Simulates a keypress on the key referred to by the this direction
        :param stop: Should the controller halt before applying this movement
        """
        if stop:
            self.halt()
        self.handle(True, self._direction_to_key(direction))

    def handle(self, keydown, key):
        """
        Handle a key event
        :param keydown: True if keydown, False if keyup
        :param key: Keycode
        """
        if key in self.wasd.keys():
            self.wasd[key] = keydown
            self._move_entity()

    def halt(self):
        """
        Releases all keys, and stops the entity
        """
        for k in self.wasd:
            self.handle(False, k)
        self._move_entity()

    def on_control_start(self):
        """
        Called once when this entity starts to be controlled by the player
        """
        pass

    def on_control_end(self):
        """
        Called once when this entity finishes being controlled by the player
        """
        pass

    def _get_direction(self, vertical):
        """
        :param vertical: True ff north/south, False if otherwise
        :return: 0 if 2 conflicting inputs in one direction, otherwise 1 or -1 depending on the direction
        """
        n = self.wasd[constants.Input.DIRECTIONAL_KEYS[constants.Direction.NORTH if vertical else constants.Direction.WEST]]
        p = self.wasd[constants.Input.DIRECTIONAL_KEYS[constants.Direction.SOUTH if vertical else constants.Direction.EAST]]
        return 0 if n == p else -1 if n else 1

    def _get_speed(self):
        """
        :return: The current speed of the controller, which is applied to the entity's velocity
        """
        raise NotImplementedError()

    def _move_entity(self):
        """
        Modifies the entity's velocity, depending on pressed keys
        """
        speed = self._get_speed()
        self.entity.velocity.x = self._get_direction(False) * speed
        self.entity.velocity.y = self._get_direction(True) * speed

    @staticmethod
    def _key_to_direction(key):
        """
        Converts a directional keycode to the corresponding Direction
        """
        return constants.Direction.VALUES[constants.Input.DIRECTIONAL_KEYS.index(key)]

    @staticmethod
    def _direction_to_key(direction):
        """
        Converts a Direction to the corresponding directional keycode
        """
        return constants.Input.DIRECTIONAL_KEYS[direction]


class InputController:
    """
    Player input controller, delegates events to the camera controller and currently controlled entity's controller
    """

    def __init__(self):
        self.entity = None
        self.current = None
        self._camera_controller = CameraController()
        self._arrow = pygame.image.load(util.get_relative_path("sprites\misc\controller_arrow.png")).convert_alpha()

    def set_camera(self, camera):
        """
        The camera controller's camera must be set after the camera is initialised
        """
        self._camera_controller.entity = camera

    def control(self, the_entity):
        """
        Transfers control to the given entity
        :param the_entity: If None, returns control to the camera
        """
        if self.current:
            self.current.suppress_ai(False)
            self.current.on_control_end()

        self.entity = the_entity
        if the_entity:
            self.current = the_entity.controller
            self.current.suppress_ai(True)
            self.current.on_control_start()
        else:
            self.current = None

        self._camera_controller.halt()

    def tick(self):
        if not self.current:
            self._camera_controller.tick()
        else:
            arrow_pos = self.entity.animator.get_arrow_position()
            constants.SCREEN.blit(self._arrow, constants.SCREEN.camera.apply(arrow_pos))

    def handle_global_event(self, e):
        """
        Handles events that are independant of current state/control, such as pausing/quitting the game
        :return: True if the event has been consumed, and hence should not be processed any further, otherwise False
        """
        consumed = False
        if e.type == pygame.KEYDOWN and e.key == constants.Input.QUIT:
            constants.RUNNING = False
            consumed = True

        return consumed

    def handle_event(self, e):
        """
        Delegates the given event
        :param e: pygame event
        """
        if self.handle_global_event(e):
            return

        if not self.current:
            self._camera_controller.handle_event(e)
            return

        se = event.simplify_key_event(e)
        if not se:
            return

        keydown, key = se
        self.current.handle(keydown, key)

        # debug keys
        try:
            if keydown:
                if key == pygame.K_j:
                    util.debug_block(self.entity.rect.center, self.entity.world)

                elif key == pygame.K_n:
                    for b in self.entity.world.buildings:
                        for w in b.windows.keys():
                            b.set_window(w, random.random() < 0.5)
                elif key == pygame.K_g:
                    h = entity.Human(self.entity.world)
                    h.move_entity(*self.entity.rect.center)

                elif key == pygame.K_h:
                    v = entity.Vehicle(self.entity.world)
                    v.move_entity(*self.entity.rect.center)

                elif key == pygame.K_l:
                    print(self.entity.get_current_tile())
        except AttributeError:
            pass


class GeneralEntityController(BaseController):
    """
    A general controller of stop-start entities, namely humans and the camera
    """

    def __init__(self, the_entity, min_speed, fast_speed, max_speed_or_random):
        """
        :param max_speed_or_random: If None, then normal speed and sprint speed are set to min_speed and fast_speed respectively.
                                    Otherwise, normal speed is randomly selected beteween min_speed and fast_speed, and
                                    sprint speed is randomly selected between normal speed and max_speed
        """

        BaseController.__init__(self, the_entity)
        self.sprint = False
        if max_speed_or_random:
            self.speed = random.randrange(min_speed, fast_speed)
            self.sprint_speed = self.speed + random.randrange(max_speed_or_random - self.speed / 2)
        else:
            self.speed = min_speed
            self.sprint_speed = fast_speed

    def _get_speed(self):
        return self.sprint_speed if self.sprint else self.speed

    def handle(self, keydown, key):
        if key == constants.Input.BOOST:
            self.sprint = keydown
            self._move_entity()
        else:
            BaseController.handle(self, keydown, key)


class CameraController(GeneralEntityController):
    """
    The controller for the camera
    """

    def __init__(self):
        GeneralEntityController.__init__(self, None, constants.Speed.CAMERA_MIN, constants.Speed.CAMERA_FAST, None)
        self._drag = VehicleController.Pedal(0.3)
        self.border_thickness = 20
        self._was_moving = False
        self.screen_boundary = map(lambda x: x - self.border_thickness, constants.WINDOW_SIZE)
        self.entity = None

    def tick(self):
        if self._drag.is_applied():
            self.entity.velocity *= self._drag.get_force()
        self.entity.move_camera()

    def _mouse_border_to_direction(self, mouse_pos):
        """
        Returns a (x, y) direction, indicating how close to the border the mouse is
        :param mouse_pos: Current mouse position
        :return: A direction (eg. (5, 0)) for the camera to move if the mouse is near the border, otherwise (0, 0)
        """

        def check_coord(coord, x_or_y_coord):
            """
            :return: World coordinate off the edge of the screen, for camera to target
            """
            if coord < self.border_thickness:
                return coord - self.border_thickness
                # return self.border_thickness - coord
            elif coord > self.screen_boundary[x_or_y_coord]:
                return coord - self.screen_boundary[x_or_y_coord]
                # return constants.WINDOW_SIZE[x_or_y_coord] + (self.screen_boundary[x_or_y_coord] - coord)
            return 0

        dx = check_coord(mouse_pos[0], 0)
        dy = check_coord(mouse_pos[1], 1)

        return dx, dy

    def halt(self):
        self._drag.set_applied(True, override=True)
        BaseController.halt(self)

    def handle_event(self, e):
        consumed = BaseController.handle_event(self, e)
        if not consumed:
            # move camera towards mouse
            if e.type == pygame.MOUSEMOTION:
                moved = False
                pos = self._mouse_border_to_direction(e.pos)
                for i in xrange(2):
                    vertical = i == 1
                    if pos[i] != 0:
                        direction = constants.Direction.delta_to_direction(pos[i], vertical)
                        self.move_in_direction(direction, stop=False)
                        moved = True
                if not moved and self._was_moving:
                    self.halt()
                self._was_moving = moved

    def _move_entity(self):
        speed = self._get_speed()
        hdir = self._get_direction(False)
        vdir = self._get_direction(True)
        if hdir or vdir:
            self.entity.velocity.x = hdir * speed
            self.entity.velocity.y = vdir * speed
            dragging = False
        else:
            dragging = True

        self._drag.set_applied(dragging)


class HumanController(GeneralEntityController):
    """
    Controller for humans, with their behaviour tree
    """

    def __init__(self, the_entity):
        GeneralEntityController.__init__(self, the_entity, constants.Speed.HUMAN_MIN, constants.Speed.HUMAN_FAST, constants.Speed.HUMAN_MAX)

        # walk = EntityMoveToLocation(self, (random.randrange(13, 19), random.randrange(6, 12)))
        # debug = DebugPrint("I, %r, am hearby debugged" % hex(id(self.entity)))
        self.behaviour_tree = BehaviourTree(self, Repeater(EntityWander(self)))

    def on_control_start(self):
        self.halt()


class VehicleController(BaseController):
    """
    Controller for vehicles, keeping track of drift/brake/accelerating
    """
    STOPPED = 0
    BRAKING = 1
    DRIFTING = 2
    ACCELERATING = 3

    class Pedal:
        """
        Framerate-independant application of force/braking
        """

        def __init__(self, brake_time, accelerating=False):
            """
            :param brake_time: Seconds to apply force over
            :param accelerating: If True, values will converge to 1, otherwise 0 (to come to a halt)
            """
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
            """
            :return: Is this pedal currently applied
            """
            return self._applied

        def set_applied(self, applied, override=False):
            """
            :param applied: New applied status of pedal
            :param override: If True, forces the pedal to be applied as specified by 'applied',
                            otherwise the pedal will keep its current state if 'applied' is equal to current state
            """
            self._was_applied = self._applied
            self._applied = applied

            if applied != self._was_applied or override:
                if applied:
                    self._gen = self._pedal_force_gen(self.brake_time)
                else:
                    self._gen = None

        def get_force(self):
            """
            :return: Float to multiply velocity by, to apply the pedals force
            """
            return next(self._gen, 1)

        def _pedal_force_gen(self, brake_time, tick_count=20):
            """
            :param brake_time: Seconds over which to reach final pedal force
            :param tick_count: Number of intermediate values
            :return: Generator for this pedal
            """
            division = self._variation / tick_count

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
            if top == constants.Input.DIRECTIONAL_KEYS[2]:
                return 1
            elif top == constants.Input.DIRECTIONAL_KEYS[0]:
                return -1
        else:
            if top == constants.Input.DIRECTIONAL_KEYS[3]:
                return 1
            elif top == constants.Input.DIRECTIONAL_KEYS[1]:
                return -1

        return 0

    def __setattr__(self, key, value):
        if key == "state" and value != VehicleController.STOPPED:
            self.press_pedal(value)
        self.__dict__[key] = value

    def press_pedal(self, state):
        """
        Applies the pedal for the given VehicleController state
        """
        for s, pedal in self.pedals.items():
            pedal.set_applied(s == state)

    def _get_applied_pedal_force(self):
        """
        :return: The currently pressed pedal's force, None if no pedals are applied
        """
        for p in self.pedals.values():
            if p.is_applied():
                return p.get_force()
        return None

    def tick(self):
        # todo: only change direction to opposite if stopped, otherwise brake
        BaseController.tick(self)

        # None if no key, brake_key if brake is held down
        current = self._get_pressed_key()

        # update state
        if current == constants.Input.BRAKE:
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
        if self.state != VehicleController.ACCELERATING and self.state != VehicleController.STOPPED and self._has_virtually_stopped():
            self.halt()
        else:
            BaseController._move_entity(self)

    def _has_virtually_stopped(self):
        """
        :return: If the speed is so low that it's safe to jolt to a halt
        """
        return self.current_speed < constants.TILE_SIZE

    def handle(self, keydown, key):
        if key in constants.Input.DIRECTIONAL_KEYS:
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
        elif key == constants.Input.BRAKE:
            self.brake.set_applied(keydown)

    def _get_pressed_key(self):
        """
        :return: Most recently pressed key, or brake key if brake is applied
        """
        return self._keystack.top if not self.brake.is_applied() else constants.Input.BRAKE

    def halt(self):
        self.entity.velocity.zero()
        self.current_speed = 0
        self.state = VehicleController.STOPPED
        self.press_pedal(VehicleController.STOPPED)

    def on_control_end(self):
        self._keystack.clear()
        self.press_pedal(VehicleController.DRIFTING)


# behaviour tree goodness
class BehaviourTree:
    """
    Behaviour tree, containing a hierarchy of behaviours
    """
    def __init__(self, entity_controller, tree):
        """
        :param tree: Root task
        """
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
    """
    Base task
    """
    RUNNING = 0
    FAILURE = 1
    SUCCESS = 2

    def __init__(self, *children):
        """
        :param children: All child nodes
        """
        # self.data_context = data_context
        self.children_tasks = list(children)

    def init(self):
        """
        Called once on start
        """
        pass

    def end(self):
        """
        Called once on end
        """
        pass

    def process(self):
        """
        Called every frame that it is active
        :return: New state
        """
        pass


class LeafTask(Task):
    """
    Childless task, that executes an action
    """
    def __init__(self):
        """
        Leaves have no children
        """
        Task.__init__(self)


class Composite(Task):
    """
    Task that holds several child tasks
    """
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
    """
    Executes each child in order: if one of them fails, then returns failure
    """
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
    """
    Returns a success if any children succeed, and doesn't execute any further children
    """
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
    """
    Task decorator with a single child task
    """
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
    """
    Inverts the result of child task
    """
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
    """
    Always returns success, even if the child task fails
    """
    def process(self):
        state = self.child.process()

        # still running
        if state == Task.RUNNING:
            return state

        # always success
        else:
            return Task.SUCCESS


class Repeater(Decorator):
    """
    Repeats the child task
    """
    def __init__(self, child, repeat_times=-1):
        """
        :param repeat_times: Child task will be repeated this amount of times: if negative, infinite repetition
        """
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
    """
    Repeats the child task until it fails
    """
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
    """
    Helper leaf task involving an entity and its controller
    """
    def __init__(self, entity_controller):
        LeafTask.__init__(self)
        self.entity = entity_controller.entity
        self.controller = entity_controller

    def _bool_to_condition(self, b):
        """
        :return: Success if b is True, otherwise failure
        """
        return Task.SUCCESS if b else Task.FAILURE


class EntityMoveToLocation(EntityLeafTask):
    """
    Moves the child entity to the given location
    """
    def __init__(self, controller, target_location):
        """
        :param target_location: Target tile location
        """
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
        direction = constants.Direction.delta_to_direction(dx, abs(dx) <= self._size)

        # move
        self.controller.move_in_direction(direction)
        return Task.RUNNING


class EntityWander(EntityLeafTask):
    """
    Wanders randomly, turning away from walls if encountered
    """
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
    """
    Checks for a solid block in front of the entity
    """
    def process(self):
        return self._bool_to_condition(not self.entity.world.is_direction_blocked(self.entity.get_current_tile(), self.entity.direction))


class DebugPrint(LeafTask):
    """
    Prints a debug message to the console, then immediately succeeds
    """
    def __init__(self, msg):
        LeafTask.__init__(self)
        self.msg = msg

    def process(self):
        print(self.msg)
        return Task.SUCCESS
