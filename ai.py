from collections import OrderedDict
import logging
from math import log
import random
import operator

import pygame

import constants
import entity
import event
import util
import world as world_module


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
        :param vertical: True if north/south, False if otherwise
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
        Handles events that are independent of current state/control, such as pausing/quitting the game
        :return: True if the event has been consumed, and hence should not be processed any further, otherwise False
        """
        consumed = False
        if e.type == pygame.KEYDOWN and e.key == constants.Input.QUIT:
            constants.RUNNING = False
            consumed = True

        return consumed

    def handle_global_game_event(self, e):
        """
        Handles game events, such as selecting entities to control,
                            clicking doors to navigate,
                            entity interactions
        :param e: pygame event
        """
        consumed = False
        world = constants.STATEMANAGER.get_current().world

        # mouse clicking to control an entity, or interact with a block
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            world_pos = util.intify(map(operator.add, e.pos, constants.SCREEN.camera.transform))

            grid_cell = world.entity_grid.get_nearest_cell(world_pos)
            closest = world.match_nearest_entity(world_pos, grid_cell, None, constants.TILE_SIZE_SQRD)

            if closest:
                should_control = True

                # empty vehicles: no no
                if closest.entitytype == constants.EntityType.VEHICLE:
                    if closest.is_empty():
                        should_control = False

                # propagate control to vehicle if a passenger is selected
                elif closest.entitytype == constants.EntityType.HUMAN:
                    if closest.vehicle:
                        closest = closest.vehicle

                if should_control:
                    consumed = True
                    constants.STATEMANAGER.transfer_control(closest)

            # block click
            else:
                # door block
                door_block = world.get_door_block(*util.pixel_to_tile(world_pos))
                if door_block:
                    building = door_block.building
                    entering = door_block.blocktype == world_module.BlockType.SLIDING_DOOR

                    constants.STATEMANAGER.switch_to_building(building if entering else None)

                    # centre camera on door
                    closest_door = None
                    if entering:
                        # find inner door
                        world_pos = map(lambda x: util.round_down_to_multiple(x, constants.TILE_SIZE), world_pos)
                        tup_world_pos = tuple(world_pos)
                        for d in building.doors:
                            if tuple(d[1]) == tup_world_pos:
                                closest_door = d[0]
                                break

                    else:
                        closest_door = building.get_closest_exit(world_pos)

                    if closest_door is None:
                        logging.warning("Could not find the %s door position" % "entrance" if entering else "exit")

                    else:
                        constants.SCREEN.camera.centre(closest_door)
                        constants.STATEMANAGER.transfer_control(None)

        elif e.type == pygame.KEYDOWN:

            # release controller
            if e.key == constants.Input.RELEASE_CONTROL:
                constants.STATEMANAGER.transfer_control(None)

            # interactions
            elif e.key == constants.Input.INTERACT:
                control_entity = constants.STATEMANAGER.controller.entity
                entitytype = control_entity.entitytype if control_entity else constants.EntityType.ALL

                # humans
                if entitytype == constants.EntityType.HUMAN:

                    # entering vehicles
                    vehicle_predicate = lambda v: v.entitytype == constants.EntityType.VEHICLE
                    nearby = world.match_nearest_entity(control_entity.transform, control_entity.grid_cell, vehicle_predicate, constants.TILE_SIZE_SQRD)
                    if nearby:
                        consumed = True
                        nearby.enter(control_entity)

                # vehicles
                elif entitytype == constants.EntityType.VEHICLE:
                    # todo: get the last controlled entity, instead of first seat: use a stack of controlled entities?
                    # seat = entity.match_first_seat(lambda s: s == constants.STATEMANAGER.controller.entity)
                    seat = control_entity.get_first_full_seat()
                    if seat >= 0:
                        consumed = True
                        control_entity.exit(seat)
        return consumed

    def handle_event(self, e):
        """
        Delegates the given event

        :param e: pygame event
        """
        if self.handle_global_event(e):
            return

        if self.handle_global_game_event(e):
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
                    h = entity.create_entity(self.entity.world, constants.EntityType.HUMAN)
                    h.move_entity(*self.entity.rect.center)

                elif key == pygame.K_h:
                    v = entity.create_entity(self.entity.world, constants.EntityType.VEHICLE)
                    v.move_entity(*self.entity.rect.center)

                elif key == pygame.K_l:
                    print(self.entity.get_current_tile())

                elif key == pygame.K_y:
                    entity.EntityLoader.load_all()
                    print("reloaded")

                elif key == pygame.K_SEMICOLON:
                    constants.SCREEN.shake_camera()

        except AttributeError:
            pass


class GeneralEntityController(BaseController):
    """
    A general controller of stop-start entities, namely humans and the camera
    """

    def __init__(self, the_entity, min_speed, fast_speed, max_speed_or_random):
        """
        :param max_speed_or_random: If None, then normal speed and sprint speed are set to min_speed and fast_speed respectively.
                                    Otherwise, normal speed is randomly selected between min_speed and fast_speed, and
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
        self.engine = _Engine(300, accelerate_rate=-1, brake_rate=2.5)
        self.border_thickness = 20
        self._was_moving = False
        self.screen_boundary = map(lambda x: x - self.border_thickness, constants.WINDOW_SIZE)
        self.entity = None
        self.state = VehicleController.STOPPED

    def tick(self):
        speed = self.engine.get_speed(self.state)
        self.entity.velocity = self.entity.velocity.normalized() * speed
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
        self.state = VehicleController.BRAKING
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

        self.state = VehicleController.BRAKING if dragging else VehicleController.ACCELERATING


class HumanController(GeneralEntityController):
    """
    Controller for humans, with their behaviour tree
    """

    def __init__(self, the_entity):
        GeneralEntityController.__init__(self, the_entity, constants.Speed.HUMAN_MIN, constants.Speed.HUMAN_FAST, constants.Speed.HUMAN_MAX)

        # walk = EntityMoveToLocation(self, (random.randrange(13, 19), random.randrange(6, 12)))
        # debug = DebugPrint("I, %r, am hereby debugged" % hex(id(self.entity)))
        self.behaviour_tree = BehaviourTree(self, Repeater(EntityWander(self, move=False)))

    def on_control_start(self):
        self.halt()


class _Engine:
    class Graph:
        ID = 0

        def __init__(self):
            self.values = []
            self.index = 0
            self.id = _Engine.Graph.ID
            _Engine.Graph.ID += 1

        def generate_values(self, func, time_step):
            step_x = 0
            running = True
            self.values.append(0)
            while running:
                y = func(step_x)

                if y >= 1:
                    y = 1
                    running = False

                self.values.append(y)
                step_x += time_step

        def get(self):
            return self.values[self.index]

        def catch_up(self, other_graph):
            self._catch_up_to_value(other_graph.get())

        def _catch_up_to_value(self, value):
            done = False
            for i in xrange(len(self.values)):
                v = self.values[i]
                if v >= value:
                    self.index = i
                    done = True
                    break

            if not done:
                self.index = 0

        def slow(self, fraction):
            self._catch_up_to_value(self.get() * fraction)

        def __eq__(self, other):
            return isinstance(other, _Engine.Graph) and other.id == self.id

        def __hash__(self):
            return self.id

        def __len__(self):
            return len(self.values)

        def __getitem__(self, item):
            return self.values[item]

        def __repr__(self):
            return "{%d}" % self.id

    def __init__(self, max_speed, accelerate_rate=10., brake_rate=10.):
        """
        :param max_speed: Maximum speed of this engine
        :param accelerate_rate: The acceleration rate: lower values = faster acceleration. Negative = instant
        :param brake_rate: The braking rate: lower values = faster braking
        """
        self._state = VehicleController.STOPPED

        self.max_speed = max_speed
        self.min_speed = max_speed / 10
        self.last_speed = 0

        self._time_applied = 0

        self.accelerate_graph = _Engine.Graph()
        self.brake_graph = _Engine.Graph()
        self._speeds = {VehicleController.ACCELERATING: (1, self.accelerate_graph),
                        VehicleController.BRAKING: (-4, self.brake_graph),
                        VehicleController.DRIFTING: (-2, self.brake_graph),
                        VehicleController.CRASHED: (None, self.accelerate_graph),
                        VehicleController.STOPPED: (None, self.accelerate_graph)}

        self.current_graph = self.accelerate_graph

        # instant acceleration
        if accelerate_rate < 0:
            accelerate = lambda x: 1
        else:
            accelerate = lambda x: 1 + log((x / accelerate_rate) + 0.05) * 0.3

        brake = lambda x: x / brake_rate

        self._time_step = 0.25

        self.accelerate_graph.generate_values(accelerate, self._time_step)
        self.brake_graph.generate_values(brake, self._time_step)

    def get_speed(self, state):
        self._time_applied += constants.DELTA

        if self._time_applied >= self._time_step:
            self._time_applied = 0

            index_delta, graph = self._speeds[state]
            length = len(graph)

            # changing speed values
            if graph != self.current_graph:
                graph.catch_up(self.current_graph)
                self.current_graph = graph

            # stopped, so index must be 0
            if index_delta is None:
                index = 0
            else:
                index = self.current_graph.index + index_delta

            self.current_graph.index = util.clamp(index, 0, length - 1)

        speed = self.current_graph.get() * self.max_speed
        self.last_speed = speed

        return speed


class VehicleController(BaseController):
    """
    Controller for vehicles, keeping track of drift/brake/accelerating
    """
    STOPPED = 0
    BRAKING = 1
    DRIFTING = 2
    ACCELERATING = 3
    CRASHED = 4

    def __init__(self, vehicle):
        BaseController.__init__(self, vehicle)
        # todo: add new sub-behaviour to go towards a target, then use for path follower
        # todo also base human movement on vehicle, instead of setting velocity directly

        self._keystack = util.Stack()
        self._lasttop = None

        self._brake_key_pressed = False
        self.current_speed = 0
        self.acceleration = 1.03

        max_speed = constants.Speed.VEHICLE_MAX * random.uniform(0.75, 1)
        self.engine = _Engine(max_speed, accelerate_rate=7, brake_rate=5)

        self.state = VehicleController.STOPPED
        self.last_key = None
        self.last_state = self.state
        self.last_directions = [0, 0]
        self.last_pos = vehicle.transform.as_tuple()
        self.last_direction = vehicle.direction

    def _get_speed(self):
        return self.engine.last_speed

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

    def slow(self, speed_multiple):
        self.engine.current_graph.slow(speed_multiple)

    def tick(self):
        # todo: only change direction to opposite if stopped, otherwise brake
        BaseController.tick(self)
        # None if no key, BRAKE if brake is held down
        current = self._get_pressed_key()

        # braking while moving
        if current == constants.Input.BRAKE:
            if self.state != VehicleController.STOPPED and self.state != VehicleController.BRAKING:
                self.state = VehicleController.BRAKING

        # key released while accelerating
        elif current is None:
            if self.state == VehicleController.ACCELERATING:
                self.state = VehicleController.DRIFTING

        # directional key is pressed
        else:
            accelerate = True
            if self.state == VehicleController.CRASHED:
                # check for obstructions
                new_direction = self._key_to_direction(current)
                obstructed = self.entity.is_obstructed(new_direction)
                accelerate = not obstructed

            if accelerate:
                self.state = VehicleController.ACCELERATING

                # start with small boost
                if self.last_state == VehicleController.STOPPED:
                    self.engine.accelerate_graph.index += 1

        # check for crashing
        pos = self.entity.transform.as_tuple()
        direction = self.entity.direction

        if direction == self.last_direction and self.state != VehicleController.CRASHED:
            # adjust delta time
            delta = constants.DELTA
            if delta != constants.LAST_DELTA:
                delta += constants.LAST_DELTA - constants.DELTA
            speed = self.current_speed * delta

            # predict new position
            expected_pos = util.add_direction(self.last_pos, direction, speed)
            distance = util.distance_sqrd(pos, expected_pos)

            # crash!
            if distance > 0.5:
                self.state = VehicleController.CRASHED
                self.on_crash()
                self.current_speed = 0

        # apply pedal force if moving
        self.current_speed = self.engine.get_speed(self.state)

        self._move_entity()
        self.last_directions = self._get_direction(False), self._get_direction(True)
        self.last_key = current
        self.last_state = self.state
        self.last_pos = pos
        self.last_direction = direction

        # debug
        # if constants.STATEMANAGER.is_controlling(self.entity):
        # constants.SCREEN.draw_string(util.get_enum_name(VehicleController, self.state), (5, 5), colour=(255, 255, 255))
        # constants.SCREEN.draw_string(str(self.current_speed), (5, 20), colour=(255, 255, 255))

    def _move_entity(self):
        if self.state not in (VehicleController.ACCELERATING, VehicleController.STOPPED, VehicleController.CRASHED) and self._has_virtually_stopped():
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

                # prevents a car switching direction to its opposite
                register = True
                if self.state != VehicleController.STOPPED:
                    current_direction = self.entity.direction
                    key_press_direction = self._key_to_direction(key)
                    key_opposite = constants.Direction.opposite(key_press_direction)

                    if key_opposite == current_direction:
                        register = False

                # there must be a driver
                if register and not self.entity.driver:
                    register = False

                if register and key != last_top:
                    self._keystack.push(key)
            else:
                self._keystack.remove_item(key)

            if last_top != self._keystack.top:
                self._lasttop = last_top

        # brake
        elif key == constants.Input.BRAKE:
            self._brake_key_pressed = keydown

    def _get_pressed_key(self):
        """
        :return: Most recently pressed key, or brake key if brake is applied
        """
        return self._keystack.top if not self._brake_key_pressed else constants.Input.BRAKE

    def halt(self):
        self.entity.velocity.zero()
        self.entity.animator.halt()
        self.current_speed = 0
        self.state = VehicleController.STOPPED

    def on_control_end(self):
        self._keystack.clear()

    def on_crash(self):
        if self.current_speed > constants.Speed.VEHICLE_MIN * 0.75 and constants.STATEMANAGER.is_controlling(self.entity):
            constants.SCREEN.shake_camera()  # todo shake more depending on the speed


class NavigationGraph:
    OUT_OF_RANGE = 100
    WRONG_BLOCK_TYPE = 101

    class Node:
        def __init__(self, tile_pos):
            self.tile_pos = tile_pos
            self.children = []

    def __init__(self, the_world):
        assert isinstance(the_world, world_module.World)  # just for pavement

        self.world = the_world
        self.nodes = []
        self.rects = []

    def _valid(self, pos, blocktype):
        """
        :return:    -1 = wrong block
                     0 = invalid block
                     1 = valid
        """
        # out of world
        if not self.world.is_in_range(*pos):
            return NavigationGraph.OUT_OF_RANGE

        block = self.world.get_block(*pos)

        # wrong blocktype
        if block.blocktype != blocktype:
            return NavigationGraph.WRONG_BLOCK_TYPE

        return True

    def _find_valid_directions(self, tile_pos, blocktype, span_width):
        directions = []

        # find span
        for direction in constants.Direction.VALUES:
            next_tile = tile_pos

            valid_direction = True
            for i in xrange(1, span_width):
                next_tile = util.add_direction(next_tile, direction)

                # check each tile in the direction
                if self._valid(next_tile, blocktype) is not True:
                    valid_direction = False
                    break

            if valid_direction:
                # check next
                peek_ahead = util.add_direction(next_tile, direction)

                # valid direction only if different block
                # if self._valid(peek_ahead, blocktype) == NavigationGraph.WRONG_BLOCK_TYPE:
                if self._valid(peek_ahead, blocktype) != NavigationGraph.OUT_OF_RANGE:
                    directions.append(direction)
        return directions

    def _explore(self, tile_pos, blocktype, length_direction, span_direction, span_width):
        # probing time
        current_pos = tile_pos
        tile_count = 0
        probing = True

        while probing:
            # move along
            current_pos = util.add_direction(current_pos, length_direction)

            # already visited
            # if self._is_visited(current_pos):
            # break

            # check whole span
            for delta in xrange(span_width):
                next_pos = util.add_direction(current_pos, span_direction, delta)

                if self._valid(next_pos, blocktype) is not True:
                    probing = False
                    break

            tile_count += 1

        # failure
        if tile_count <= span_width:
            return None

        # create rectangle
        rect = util.Rect(tile_pos, (0, 0))
        rect.expand(span_direction, span_width)
        rect.expand(length_direction, tile_count)

        return rect

    def _is_visited(self, pos):
        pixel_pos = util.tile_to_pixel(pos)
        for r, _ in self.rects:
            if r.collidepoint(pixel_pos):
                return True
        return False

    def generate_graph(self):
        """
            better idea:
            use technique similar to roadmap, by travelling along with a row/line of tiles 2 wide (but abstract line into class)
            for every pavement in the world:
                check not visited already
                scroll along in every direction until we come across a non-pavement
                    if a tile is already visited, keep going anyway
                    set each tile to visited
                add a node at the beginning and end of this rectangle

        """

        blocktype = world_module.BlockType.PAVEMENT
        span_width = 2

        for x, y, b in self.world.iterate_blocks():
            if b.blocktype != blocktype:
                continue

            pos = (x, y)

            # already visited
            if self._is_visited(pos):
                continue

            # find road span direction
            spans = self._find_valid_directions(pos, blocktype, span_width)

            if not spans:
                continue

            for span in spans:
                for direction in constants.Direction.perpendiculars(span):
                    outline = self._explore(pos, blocktype, direction, span, span_width)

                    if not outline:
                        continue

                    # success
                    print(outline)
                    self.rects.append((outline.to_pixel(), util.random_colour()))

        print(len(self.rects))

    def debug_render(self):
        for n in self.nodes:
            pos = util.tile_to_pixel(n.tile_pos)
            constants.SCREEN.draw_rect(util.Rect(pos, constants.TILE_DIMENSION), filled=False, colour=(100, 10, 10, 50))

        for r, c in self.rects:
            constants.SCREEN.draw_rect(r, colour=c, filled=False)


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
        # DebugPrint())
        #
        # self.root = Repeater(sequence, self.data_context)

        self.root = tree
        self.current = self.root

        self.current.init()

    def tick(self):
        # todo: don't traverse the tree each frame
        # todo: INTERRUPTIONS?!
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

        # either running or failure: propagate this state up to the parent
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

        # either success or running: propagate to parent
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
    Wanders/turns randomly, turning away from walls if encountered
    """

    def __init__(self, entity_controller, move=True):
        EntityLeafTask.__init__(self, entity_controller)
        self.ticker = util.TimeTicker((0.1, 0.8))
        self.move = move

    def init(self):
        self.ticker.reset()

    def process(self):
        # todo: is forever running

        if self.ticker.tick():
            if random.random() < 0.4:
                direction = constants.Direction.random()

                if self.move:
                    if self.entity.world.is_point_blocked(self.entity.get_current_tile(), direction):
                        direction = constants.Direction.opposite(direction)
                    self.controller.move_in_direction(direction)

                # simply face another direction
                else:
                    self.controller.entity.turn(direction)
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
