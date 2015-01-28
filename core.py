import pygame

import constants
from state import GameState


class Game:
    def __init__(self):
        constants.SCREEN.create_window()
        constants.STATEMANAGER.change_state(GameState())

        self.running = True

    def start(self):
        """
        Sets up and runs the game
        """
        clock = pygame.time.Clock()
        while self.running:
            constants.DELTA = (clock.tick(60) / 1000.0)
            state = constants.STATEMANAGER.current

            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    quit()
                elif event.type == pygame.USEREVENT:
                    constants.STATEMANAGER.handle_user_event(event)
                else:
                    state.handle_event(event)

            constants.SCREEN.fill(state.background_colour)
            state.tick()

            try:
                constants.STATEMANAGER.tick_transition()
                constants.SCREEN.camera.tick()
            except AttributeError:
                pass

            constants.SCREEN.draw_fps(clock.get_fps())
            pygame.display.flip()

    def quit(self):
        """
        Allows the game to gracefully quit
        """
        self.running = False

    def __setattr__(self, key, value):
        if key == "state":
            pygame.mouse.set_visible(value.mouse_visible)
            constants.SCREEN.fill(value.background_colour)
        self.__dict__[key] = value


def _centre_window():
    import os

    os.environ['SDL_VIDEO_CENTERED'] = '1'


if __name__ == '__main__':
    _centre_window()

    pygame.init()
    Game().start()
