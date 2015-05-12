import pygame


BUILDING_ENTER = 0
BUILDING_EXIT = 1

_TYPES = {
    BUILDING_ENTER: "BuildingEnter",
    BUILDING_EXIT: "BuildingExit"
}


def call_event(eventtype, **args):
    """
    Posts a user-event with the given arguments to the event queue
    """
    pygame.event.post(pygame.event.Event(pygame.USEREVENT, dict({"eventtype": eventtype}.items() + args.items())))


def call_human_building_movement(human, building, entered):
    """
    Helper function, to post a building entry event

    :param human: The entering human
    :param building: The building
    :param entered: True if entering, False if exiting
    """
    call_event(BUILDING_ENTER if entered else BUILDING_EXIT, entity=human, building=building)


def simplify_key_event(event):
    """
    :return: (keydown, key) if the given event is a key event, otherwise None
    """
    if event.type == pygame.KEYDOWN or event.type == pygame.KEYUP:
        return event.type == pygame.KEYDOWN, event.key
    return None