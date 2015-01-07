import pygame


BUILDING_ENTER = 0
BUILDING_EXIT = 1

_TYPES = {
    BUILDING_ENTER: "BuildingEnter",
    BUILDING_EXIT: "BuildingExit"
}


def call_event(eventtype, **args):
    pygame.event.post(pygame.event.Event(pygame.USEREVENT, dict({"eventtype": eventtype}.items() + args.items())))