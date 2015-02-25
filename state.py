import random
import logging
import operator
import sys

import pygame

import ai
import event as event_module
import animation
import constants
from entity import Human, Vehicle
import world as world_module
import util


class Transition:
    """
    Base transition
    """
    SCREEN_COVER = None

    def __init__(self, duration=1, tick_count=40):
        """
        :param duration: Seconds to last
        :param tick_count: Number of times to tick
        """
        self.duration = duration
        self._ticker = util.TimeTicker(float(duration) / tick_count)
        self.complete = False
        if not Transition.SCREEN_COVER:
            Transition.SCREEN_COVER = pygame.Surface(constants.WINDOW_SIZE).convert_alpha()

    def tick(self):
        """
        Called per frame
        """
        raise NotImplemented("Empty transition")


class FadeTransition(Transition):
    """
    Fades the screen from black
    """
    def __init__(self):
        Transition.__init__(self)
        self.alpha = 255

    def tick(self):
        if self._ticker.tick():
            self.alpha -= 15
            if self.alpha < 0:
                self.alpha = 0
                self.complete = True

        Transition.SCREEN_COVER.fill((State.BACKGROUND + (self.alpha,)))
        constants.SCREEN.blit(Transition.SCREEN_COVER)


class ZoomTransition(Transition):
    """
    Zooms out from black from the centre
    """
    def __init__(self):
        Transition.__init__(self)
        scale = 10
        self.dim = (constants.WINDOW_SIZE[0] / scale, constants.WINDOW_SIZE[1] / scale)
        self.space = util.Rect(constants.WINDOW_CENTRE, self.dim)

    def tick(self):
        if self._ticker.tick():
            if self.space.width > constants.WINDOW_SIZE[0]:
                self.complete = True

            self.space.inflate(*self.dim)

        Transition.SCREEN_COVER.fill(State.BACKGROUND)
        pygame.draw.rect(Transition.SCREEN_COVER, (0, 0, 0, 0), self.space.as_tuple())
        constants.SCREEN.blit(Transition.SCREEN_COVER)


class StateManager:
    """
    Manages the current state, and player input
    """
    def __init__(self):
        self._stack = util.Stack()
        self.transition = None
        self.controller = ai.InputController()

    def change_state(self, new_state=None, transition_cls=None):
        """
        Switches to another state
        :param new_state: The state to switch to, or None to return to the previous
        :param transition_cls: Optional transition class between the states, otherwise randomly chosen
        """
        if transition_cls is None:
            transition_cls = ZoomTransition if random.random() < 1.0 else FadeTransition

        try:
            self.transition = transition_cls()
        except TypeError:
            pass

        old_state = None

        # pop
        if not new_state:
            old_state = self._stack.pop()

        # push
        else:
            self._stack.push(new_state)

        if old_state:
            old_state.on_unload()

        current = self._stack.top
        current.on_load()

        # mouse visibility
        pygame.mouse.set_visible(current.mouse_visible)

        # update camera boundaries
        if current.world:
            constants.SCREEN.camera.update_boundaries(current.world)

    def handle_user_event(self, e):
        """
        Handles custom events, called from event.py
        :param e: pygame event
        """

        if hasattr(e, "entity"):
            # prevent world transfer flicker
            e.entity.visible = True

            if e.entity == self.controller.entity:
                # building enter/exit
                if hasattr(e, "building"):
                    building = e.building if e.eventtype == event_module.BUILDING_ENTER else None
                    self.switch_to_building(building)

    def switch_to_building(self, building):
        """
        :param building: Building to switch to, or None to exit
        """
        self.change_state(BuildingState(building) if building else None)

    def tick_transition(self):
        """
        Ticks the current transition, if any
        """
        try:
            self.transition.tick()
            if self.transition.complete:
                self.transition = None
        except AttributeError:
            pass

    def transfer_control(self, entity, camera_centre=False):
        """
        Transfers player control to the given entity
        :param entity: If None, control is released completely (and the camera takes over)
        :param camera_centre Should the camera immediately centre on the new controlled entity
        """

        if self.controller.entity == entity:
            return

        self.controller.control(entity)
        constants.SCREEN.camera.target = entity
        if camera_centre:
            constants.SCREEN.camera.centre()

    def get_current(self):
        """
        :return: The current state
        """
        return self._stack.top


class State:
    """
    Base state
    """

    BACKGROUND = (18, 18, 20)

    def __init__(self, background_colour=BACKGROUND, mouse_visible=True):
        """
        :param background_colour The background colour of the state
        :param mouse_visible Whether or not the mouse should be visible in this state
        """
        self.background_colour = background_colour
        self.mouse_visible = mouse_visible
        self.world = None

    def handle_event(self, event):
        """
        Processes events
        """
        constants.STATEMANAGER.controller.handle_event(event)

    def tick(self):
        """
        Called per frame
        """
        for w in world_module.WORLDS:
            w.tick(render=(w == self.world))
        constants.STATEMANAGER.controller.tick()

    def on_load(self):
        """
        Called every time the state is loaded
        """
        constants.SCREEN.camera.centre()

    def on_unload(self):
        """
        Called every time the state is unloaded
        """
        pass


class BaseGameState(State):
    """
    Base in-game state
    """
    def __init__(self):
        State.__init__(self, mouse_visible=True)

    def handle_event(self, event):
        """
        Controls entity selection with the mouse, otherwise delegates event to current state
        :param event: pygame event
        """
        # controller selection
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            world_pos = map(operator.add, event.pos, constants.SCREEN.camera.transform)

            # find closest entity within a tile's distance of the mouse
            closest = None
            closest_distance = sys.maxsize
            for entity in self.world.entities:
                dist = util.distance_sqrd(entity.transform, world_pos)
                if dist < constants.TILE_SIZE_SQRD and dist < closest_distance:
                    closest_distance = dist
                    closest = entity

            if closest:
                constants.STATEMANAGER.transfer_control(closest)

            # block click
            else:
                world_pos = util.intify(world_pos)
                # door block
                door_block = self.world.get_door_block(*util.pixel_to_tile(world_pos))
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

        # release controller
        elif event.type == pygame.KEYDOWN and event.key == constants.Input.RELEASE_CONTROL:
            constants.STATEMANAGER.transfer_control(None)
        else:
            State.handle_event(self, event)

    def on_load(self):
        constants.SCREEN.camera.update_boundaries(self.world)
        State.on_load(self)


class OutsideWorldState(BaseGameState):
    """
    Main world state
    """

    def __init__(self):
        BaseGameState.__init__(self)
        self.building_timer = 0

        # load spritesheets
        animation.load_all()

        # load main world, with all buildings
        self.world = world_module.World.load_tmx("world.tmx")
        logging.info("Loaded %d worlds" % len(world_module.WORLDS))

        constants.SCREEN.set_camera_world(self.world)
        constants.STATEMANAGER.controller.set_camera(constants.SCREEN.camera)

        # render worlds
        for w in world_module.WORLDS:
            w.renderer.initial_render()

        # add some humans
        for _ in xrange(10):
            Human(self.world)

        # add some vehicles
        for _ in xrange(1):
            Vehicle(self.world)

        # centre on a random entity
        constants.SCREEN.camera.centre(random.choice(self.world.entity_buffer.keys()).transform)

        # move mouse to centre
        pygame.mouse.set_pos(constants.WINDOW_CENTRE)

    def tick(self):
        State.tick(self)

        # todo temporary building action
        self.building_timer -= 1
        if self.building_timer < 0:
            self.building_timer = random.randrange(20, 100)
            for w in (x for x in world_module.WORLDS if isinstance(x, world_module.World)):
                for b in w.buildings:
                    for _ in xrange(random.randrange(2, 6)):
                        b.set_window(random.choice(b.windows.keys()), random.random() < 0.5)


class BuildingState(BaseGameState):
    """
    Gamestate for building interiors
    """
    def __init__(self, building):
        BaseGameState.__init__(self)
        self.building = building
        self.world = building.inside
