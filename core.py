import os

import pygame

import constants
import state


class Game:
    def __init__(self):
        constants.SCREEN.create_window()
        constants.STATEMANAGER = state.StateManager()
        constants.STATEMANAGER.change_state(state.OutsideWorldState())

    def start(self):
        """
        Sets up and runs the game
        """
        clock = pygame.time.Clock()
        while constants.RUNNING:
            constants.LAST_DELTA = constants.DELTA
            constants.DELTA = (clock.tick(60) / 1000.0)
            current_state = constants.STATEMANAGER.get_current()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    constants.RUNNING = False
                elif event.type == pygame.USEREVENT:
                    constants.STATEMANAGER.handle_user_event(event)
                else:
                    current_state.handle_event(event)

            constants.SCREEN.fill(current_state.background_colour)
            current_state.tick()

            try:
                constants.STATEMANAGER.tick_transition()
                constants.SCREEN.camera.tick()
            except AttributeError:
                pass

            constants.SCREEN.draw_fps(clock.get_fps())
            pygame.display.flip()

    def __setattr__(self, key, value):
        if key == "state":
            pygame.mouse.set_visible(value.mouse_visible)
            constants.SCREEN.fill(value.background_colour)
        self.__dict__[key] = value


def _centre_window():
    """
    Centres the window on the screen
    """
    os.environ['SDL_VIDEO_CENTERED'] = '1'


if __name__ == '__main__':
    _centre_window()

    pygame.init()
    Game().start()
    pygame.quit()