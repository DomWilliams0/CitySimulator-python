import random
import logging

import pygame

import ai
import event as event_module
import animation
import constants
from entity import Human, Vehicle
import world as world_module
import util


class Transition:
    SCREEN_COVER = None

    def __init__(self, duration=1, tick_count=40):
        self.duration = duration
        self._ticker = util.TimeTicker(float(duration) / tick_count)
        self.complete = False
        if not Transition.SCREEN_COVER:
            Transition.SCREEN_COVER = pygame.Surface(constants.WINDOW_SIZE).convert_alpha()

    def tick(self):
        raise NotImplemented("Empty transition")


class FadeTransition(Transition):
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
        pygame.draw.rect(Transition.SCREEN_COVER, (0, 0, 0, 0), self.space.to_tuple())
        constants.SCREEN.blit(Transition.SCREEN_COVER)


class StateManager:
    def __init__(self):
        self._stack = util.Stack()
        self.transition = None
        self.controller = ai.InputController()

    def change_state(self, new_state=None, transition_cls=None):
        """
        Switches to another state
        :param new_state: The state to switch to, or None to return to the previous
        :param transition_cls: Optional transition class between the states
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
        if hasattr(e, "entity"):
            # prevent world transfer flicker
            e.entity.visible = True

            if e.entity == self.controller.entity:
                # building enter/exit
                if hasattr(e, "building"):
                    building = e.building
                    if e.eventtype == event_module.BUILDING_ENTER:
                        constants.SCREEN.camera.update_boundaries(building.inside)
                        self.change_state(BuildingState(building))
                    else:
                        constants.SCREEN.camera.update_boundaries(building.world)
                        self.change_state()

    def tick_transition(self):
        try:
            self.transition.tick()
            if self.transition.complete:
                self.transition = None
        except AttributeError:
            pass

    def transfer_control(self, entity):

        # pop off control override from old controller, if any
        # if self.player_controller is not None:
        # self.player_controller.set_suppressed_behaviours(False)
        #
        # if not entity:
        #     self.player_controller = None
        # else:
        #     self.player_controller = entity.controller
        #     self.player_controller.set_suppressed_behaviours(True)
        #     self.follow_with_camera(entity)
        self.controller.control(entity)
        self.follow_with_camera(entity)

    def follow_with_camera(self, entity):
        constants.SCREEN.camera.target = entity

    def get_current(self):
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
        controller = constants.STATEMANAGER.controller
        if controller:
            controller.handle(event)

    def handle_user_event(self, e):
        pass

    def tick(self):
        """
        Called per frame
        """
        for w in world_module.WORLDS:
            w.tick(render=(w == self.world))

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


class GameState(State):
    def __init__(self):
        State.__init__(self, mouse_visible=False)
        self.building_timer = 0

        # load spritesheets
        animation.load_all()

        # load main world, with all buildings
        self.world = world_module.World.load_tmx("world.tmx")
        logging.info("Loaded %d worlds" % len(world_module.WORLDS))

        constants.SCREEN.set_camera_world(self.world)
        # constants.STATEMANAGER.human_controller.entity = Human(self.world)  # debug creates a new human and follows him
        # constants.SCREEN.camera.target = constants.STATEMANAGER.human_controller.entity

        # render worlds
        for w in world_module.WORLDS:
            w.renderer.initial_render()

        # add some humans
        for _ in xrange(1):
            h = Human(self.world)
            constants.STATEMANAGER.transfer_control(h)

        # add some vehicles
        for _ in xrange(0):
            Vehicle(self.world)

        # debug vehicle to control
        v = Vehicle(self.world)
        # constants.STATEMANAGER.follow_with_camera(v)
        # constants.STATEMANAGER.transfer_control(v)

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


class BuildingState(State):
    def __init__(self, building):
        State.__init__(self, mouse_visible=False)
        self.building = building
        self.world = building.inside
