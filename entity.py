import random

from pygame.sprite import Sprite
from pygame.surface import Surface

from util import Rect
import ai
import animation
import constants
import util
from vec2d import Vec2d


class Entity(Sprite):
    """
    A Sprite with an image, position, velocity and aabb
    """

    _LASTID = 0

    def __init__(self, dimensions, world, entitytype, spritesheet=None, loc=None, world_collisions=True, world_interactions=False, can_leave_world=False):
        """
        :param dimensions Dimensions of the sprite
        :param loc Starting position, defaults to a random location in the world
        :param world_collisions Whether or not this entity collides with the world
        :param can_leave_world Whether or not this entity is allowed to leave the world's boundaries
        """
        Sprite.__init__(self)
        self.image = Surface(dimensions).convert()
        self.rect = Rect(self.image.get_rect())
        self.aabb = Rect(self.rect)

        self.world = world
        world.spawn_entity(self, loc)

        self.velocity = Vec2d(0, 0)

        self.world_collisions = world_collisions
        self.world_interactions = world_interactions
        self.can_leave_world = can_leave_world

        self.dead = False
        self.visible = True

        self.id = Entity._LASTID
        Entity._LASTID += 1

        self.direction = constants.Direction.SOUTH
        self.vertical_diagonal = True
        self.controller = None

        spritesheet = animation.get_random(entitytype) if not spritesheet else animation.get(spritesheet)
        animator_cls = animation.HumanAnimator if spritesheet.type == constants.EntityType.HUMAN else animation.VehicleAnimator
        self.animator = animator_cls(self, spritesheet)

    def tick(self, render):
        """
        Called per frame
        """
        if self.controller:
            self.controller.tick()

        self._update_direction()
        self.move()

        if render and self.visible:
            self.animator.tick()

    def move(self):
        """
        Moves the aabb by velocity * delta, according to collisions
        """
        # rounding compensation
        delta = self.velocity * constants.DELTA
        """
        rects are no longer rounded to nearest int
        if delta[0] < 0:
            delta[0] += 1
        if delta[1] < 0:
            delta[1] += 1
        """

        self.aabb.add_vector(delta)
        self.catchup_aab()

        # collisions
        if self.world_collisions:
            self.handle_collisions()

        if not self.can_leave_world:
            tl = self.rect.topleft
            br = self.rect.bottomright

            w = self.aabb.width / 2 if self.world.half_block_boundaries else 0
            h = self.aabb.height / 2 if self.world.half_block_boundaries else 0

            dx = dy = 0

            if tl[0] < -w:
                dx = -tl[0] - w

            elif br[0] >= self.world.pixel_width + w:
                dx = self.world.pixel_width - br[0] + w

            if tl[1] < -h * 2:
                dy = -tl[1] - h * 2

            elif br[1] >= self.world.pixel_height + h:
                dy = self.world.pixel_height - br[1] + h

            if dx != 0 or dy != 0:
                c = self.aabb.center
                self.move_entity(c[0] + dx, c[1] + dy)

        if self.world_interactions:
            self.handle_interactions()

    def _update_direction(self):
        """
        If necessary, changes the compass direction that the entity is facing
        """
        if self.is_moving():
            angle = self.velocity.get_angle()
            new_direction = self.direction

            # If true, the entity will look north/south when walking diagonally, otherwise east/west
            if self.vertical_diagonal:
                if angle == 0:
                    new_direction = constants.Direction.EAST
                elif angle == 180:
                    new_direction = constants.Direction.WEST
                elif 0 > angle > -180:
                    new_direction = constants.Direction.NORTH
                elif 0 < angle < 180:
                    new_direction = constants.Direction.SOUTH
            else:
                if angle == 90:
                    new_direction = constants.Direction.SOUTH
                elif angle == -90:
                    new_direction = constants.Direction.NORTH
                elif 90 < angle <= 180 or -90 > angle >= -180:
                    new_direction = constants.Direction.WEST
                elif 0 <= angle < 90 or 0 >= angle >= -90:
                    new_direction = constants.Direction.EAST

            if new_direction != self.direction:
                self.turn(new_direction)

    def catchup_aab(self):
        """
        Moves positional rect to collision-corrected aabb
        """
        self.rect.center = self.aabb.center

    def turn(self, direction):
        """
        Updates compass direction of Human and animator
        :param direction: New direction
        """
        self.direction = direction
        self.animator.turn(direction)

    def kill(self):
        """
        Marks the entity as dead, to be removed on next tick
        """
        self.dead = True

    def is_moving(self):
        """
        :return: Whether or not the entity is moving
        """
        return bool(self.velocity)

    def handle_collisions(self):
        """
        Corrects any collisions with the world
        """
        rects = self.world.get_colliding_blocks(self.aabb)
        if not self.world_interactions:
            rects.extend(self.world.get_colliding_blocks(self.aabb, True))

        half = constants.TILE_SIZE / 2
        half_dim = half, half

        for rect in rects:
            r = rect[0]  # strip the dimensions
            if rect[1] != constants.DIMENSION:
                half_tile = rect[1][0] / 2, rect[1][1] / 2
            else:
                half_tile = half_dim

            # resolve collision
            center_a = self.aabb.center
            center_b = (r[0] + half_tile[0], r[1] + half_tile[1])

            distance_x = center_a[0] - center_b[0]
            distance_y = center_a[1] - center_b[1]
            min_x = self.aabb.width / 2 + half_tile[0]
            min_y = self.aabb.height / 2 + half_tile[1]

            if distance_x > 0:
                x_overlap = min_x - distance_x
            else:
                x_overlap = -min_x - distance_x

            if distance_y > 0:
                y_overlap = min_y - distance_y
            else:
                y_overlap = -min_y - distance_y

            if abs(y_overlap) < abs(x_overlap):
                self.aabb.y += y_overlap
            else:
                self.aabb.x += x_overlap

        self.catchup_aab()

    def handle_interactions(self):
        pass

    def interact_with_block(self, block, x, y):  # todo redundant
        block.interact(self, x, y)

    def move_entity(self, x, y):
        """
        Moves the entity to the given coordinates
        """
        self.aabb.center = x, y
        self.catchup_aab()

    @staticmethod
    def random_velocity(speed, no_zero=False):
        """
        :param speed: Variation range
        :param no_zero: If True, neither x or y can be 0
        """
        if no_zero:
            ran = lambda: (random.randrange(speed) + 1) * (-1 if random.random() < 0.5 else 1)
            return Vec2d(ran(), ran())
        return Vec2d(random.randrange(-speed, speed + 1), random.randrange(-speed, speed + 1))

    @staticmethod
    def random_set_velocity(speed):
        """
        :param speed: a constants.Speed constant
        :return: A vector of this constants.Speed constant in any direction
        """
        ran = lambda: speed * (-1 if random.random() < 0.5 else 1 if random.random() < 0.5 else 0)
        return Vec2d(ran(), ran())

    def __repr__(self):
        return "{%s: %d}" % (str(self.__class__).split('.')[1][:-2], self.id)


class Human(Entity):
    def __init__(self, world, spritesheet=None, spawn_index=0):
        """
        :param world: The world this Human should be added to
        :param spritesheet Name of spritesheet: if None, a random spritesheet is chosen
        :param spawn_index: The spawn at which the player will be spawned
        """
        Entity.__init__(self, (32, 32), world, constants.EntityType.HUMAN, spritesheet=spritesheet)

        self.interact_aabb = Rect(self.aabb)
        offset = self.rect.width / 4
        self.interact_aabb.width -= offset * 2
        self.interact_aabb.x += offset
        self.interact_aabb.height *= 0.6

        self.aabb.height /= 2
        self.aabb.inflate(-6, 0)

        self.world.move_to_spawn(self, spawn_index)

    def catchup_aab(self):
        self.rect.center = self.aabb.midtop
        try:
            self.interact_aabb.center = self.aabb.center
        except AttributeError:
            pass

    def handle_interactions(self):
        rects = self.world.get_colliding_blocks(self.interact_aabb, interactables=True)
        buildings = set()
        for rect in rects:
            r = rect[0]
            block = self.world.get_solid_block(*util.pixel_to_tile(r))
            try:
                if block.building not in buildings:
                    buildings.add(block)
                    self.interact_with_block(block, *r)
            except AttributeError:
                pass

    def wander(self):
        self.controller = ai.RandomWanderer(self)


class Player(Human):
    def __init__(self, world):
        Human.__init__(self, world, "business_man", 0)
        self.controller = ai.PlayerController(self)


class Vehicle(Entity):
    def __init__(self, world, spritesheet=None):
        Entity.__init__(self, (32, 32), world, constants.EntityType.VEHICLE, spritesheet=spritesheet, can_leave_world=False)
        self.controller = ai.VehicleController(self)
        self.vertical_diagonal = False

        self.aabb.height /= 2

        self.animator.spritesheet.set_colour((200, 0, 0))

        # todo should move to road spawn
        self.world.move_to_spawn(self, 0)

    def catchup_aab(self):
        self.rect.center = self.aabb.midtop