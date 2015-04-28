import random
import logging

import pygame

import ai
import event as event_module
import constants
import entity
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

        if self.is_controlling(entity):
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

    def is_controlling(self, an_entity):
        return self.controller.entity == an_entity


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
        pass

    def tick(self):
        """
        Called per frame
        """
        pass

    def on_load(self):
        """
        Called every time the state is loaded
        """
        pass

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

    def on_load(self):
        constants.SCREEN.camera.update_boundaries(self.world)
        constants.SCREEN.camera.centre()

    def tick(self):
        for w in world_module.WORLDS:
            w.tick(render=(w == self.world))
        constants.STATEMANAGER.controller.tick()

    def handle_event(self, event):
        constants.STATEMANAGER.controller.handle_event(event)


class OutsideWorldState(BaseGameState):
    """
    Main world state
    """

    def __init__(self):
        BaseGameState.__init__(self)
        self.building_timer = 0

        # load entities
        entity.EntityLoader.load_all()

        # load main world, with all buildings
        self.world = world_module.World.load_tmx("world.tmx")
        logging.info("Loaded %d worlds" % len(world_module.WORLDS))

        constants.SCREEN.set_camera_world(self.world)
        constants.STATEMANAGER.controller.set_camera(constants.SCREEN.camera)

        # render worlds
        for w in world_module.WORLDS:
            w.renderer.initial_render()

        # add some humans
        for _ in xrange(5):
            entity.create_entity(self.world, constants.EntityType.HUMAN)

        # add some vehicles
        for _ in xrange(5):
            entity.create_entity(self.world, constants.EntityType.VEHICLE)

        # centre on a random entity
        constants.SCREEN.camera.centre(random.choice(self.world.entity_buffer.keys()).transform)

        # move mouse to centre
        pygame.mouse.set_pos(constants.WINDOW_CENTRE)

    def tick(self):
        BaseGameState.tick(self)

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
