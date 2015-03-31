import logging
import random

from pygame.sprite import Sprite
from pygame.surface import Surface

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

    def __init__(self, dimensions, world, entitytype, spritesheet=None, clone_spritesheet=False, loc=None, world_collisions=True, world_interactions=False, can_leave_world=False):
        """
        :param dimensions Dimensions of the sprite
        :param loc Starting position, defaults to a random location in the world
        :param world_collisions Whether or not this entity collides with the world
        :param can_leave_world Whether or not this entity is allowed to leave the world's boundaries
        :param spritesheet Spritesheet name, if left None a random one is chosen
        :param clone_spritesheet Should the animator just use the shared instance?
        """
        Sprite.__init__(self)
        self.image = Surface(dimensions).convert()
        self.rect = util.Rect(self.image.get_rect())
        self.aabb = util.Rect(self.rect)
        self.transform = util.Transform()

        self.world = world
        self.grid_cell = (0, 0)
        world.spawn_entity(self, loc)

        self.velocity = Vec2d(0, 0)

        self.world_collisions = world_collisions
        self.collisions_enabled = True
        self.world_interactions = world_interactions
        self.can_leave_world = can_leave_world

        self.dead = False
        self.visible = True
        self.entitytype = entitytype

        self.id = Entity._LASTID
        Entity._LASTID += 1

        self.direction = constants.Direction.SOUTH
        self.vertical_diagonal = True
        self.controller = None

        shared_sheet = animation.get_random(entitytype) if not spritesheet else animation.get(spritesheet)
        try:
            animator_cls = animation.HumanAnimator if shared_sheet.type == constants.EntityType.HUMAN else animation.VehicleAnimator
        except AttributeError:
            logging.log(logging.FATAL, "Spritesheet failed to load")
            exit(-1)
            return

        ssheet = shared_sheet if not clone_spritesheet else animation.clone(shared_sheet)
        self.animator = animator_cls(self, ssheet)

    def tick(self, render, block_input=False):
        """
        Called per frame
        """
        if self.controller and not block_input:
            self.controller.tick()

        self._update_direction()
        self.move()

        if render:
            self.render()

    def render(self):
        """
        Renders the entity, if they are visible
        """
        if self.visible:
            self.animator.tick()
            # constants.SCREEN.draw_rect(self.rect, filled=False)
            # constants.SCREEN.draw_rect(self.aabb, filled=False, colour=(0, 255, 0))

    def move(self):
        """
        Moves the aabb by velocity * delta, according to collisions
        """
        """
        rects are no longer rounded to nearest int
        if delta[0] < 0:
            delta[0] += 1
        if delta[1] < 0:
            delta[1] += 1
        """

        delta = self.velocity * constants.DELTA
        delta += self.aabb.center
        self.move_entity(*delta)

        # collisions
        if self.world_collisions and self.collisions_enabled:
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
        if self == constants.STATEMANAGER.controller.entity:
            constants.STATEMANAGER.transfer_control(None)

    def is_moving(self):
        """
        :return: Whether or not the entity is moving
        """
        return bool(self.velocity)

    def get_current_tile(self):
        """
        :return: The current tile position
        """
        return util.pixel_to_tile(self.transform)

    def is_visible(self, boundaries):
        tile = self.get_current_tile()
        return boundaries[0] <= tile[0] <= boundaries[2] and boundaries[1] <= tile[1] <= boundaries[3]

    def _resolve_collision(self, other):
        etype = other.entitytype
        f = None
        if etype == constants.EntityType.HUMAN:
            f = self.resolve_human_collision
        elif etype == constants.EntityType.VEHICLE:
            f = self.resolve_vehicle_collision

        if f:
            f(other)

    def resolve_vehicle_collision(self, vehicle):
        pass

    def resolve_human_collision(self, human):
        pass

    def resolve_world_collision(self, block_rect):
        r = block_rect[0]  # strip the dimensions
        if block_rect[1] != constants.DIMENSION:
            half_tile = block_rect[1][0] / 2, block_rect[1][1] / 2
        else:
            half_tile = constants.HALF_TILE_SIZE

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

    def swap_render_order(self, other):
        """
        Attempts to swap the two entities if they're the wrong way round
        """
        # if other.id < self.id:
        distance = util.distance_sqrd(self.transform, other.transform)
        if distance < (constants.TILE_SIZE * 2) ** 2:
            try:
                h_index = other.world.entities.index(self)
                o_index = self.world.entities.index(other)
                ydiff = self.transform.y - other.transform.y
                if (h_index < o_index and ydiff > 0) or (h_index > o_index and ydiff < 0):
                    self.world.entities[h_index], self.world.entities[o_index] = self.world.entities[o_index], self.world.entities[h_index]
            except ValueError:
                logging.warning("Couldn't swap 2 entities (%r and %r)" % (self, other))

    def handle_collisions(self):
        """
        Corrects any collisions with the world
        """
        rects = self.world.get_colliding_blocks(self.aabb)
        if not self.world_interactions:
            rects.extend(self.world.get_colliding_blocks(self.aabb, True))

        # world collisions
        for rect in rects:
            self.resolve_world_collision(rect)

        # entity collisions
        for grid_cell in self.world.iterate_surrounding_grid_cells(self.grid_cell):
            for other in grid_cell:
                if self != other and not other.dead and self.collides(other):
                    self._resolve_collision(other)

        self.catchup_aab()

    # def should_collide(self, entity):
    # return True

    def collides(self, other):
        """
        :return: If this entity is colliding with the other
        """
        return self.aabb.colliderect(other.aabb)

    def handle_interactions(self):
        pass

    def move_entity(self, x, y):
        """
        Moves the entity to the given coordinates
        """
        self.aabb.center = x, y
        self.transform.set((x, y))
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
        Entity.__init__(self, (32, 32), world, constants.EntityType.HUMAN, spritesheet=spritesheet, world_interactions=True)

        self.controller = ai.HumanController(self)
        self.vehicle = None

        self.interact_aabb = util.Rect(self.aabb)
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
                    block.interact(self, *r)
            except AttributeError:
                pass

    # def should_collide(self, entity):
    # return entity.entitytype != constants.EntityType.HUMAN

    def resolve_vehicle_collision(self, vehicle):
        self.resolve_world_collision(vehicle.aabb.as_half_tuple())

    def entered_vehicle(self, vehicle):
        """
        Called after the vehicle has acknowledged the entry
        """
        self.vehicle = vehicle

        # transfer control to vehicle
        if constants.STATEMANAGER.controller.entity == self:
            constants.STATEMANAGER.transfer_control(vehicle)

        else:
            self.controller.suppress_ai(True)

        # disable collisions
        self.world.entity_grid.set_enabled(self, False)

        self.controller.halt()

    def exited_vehicle(self, vehicle):
        """
        Called before the vehicle has acknowledged the exit
        """
        self.vehicle = None

        # transfer control back to this human
        if constants.STATEMANAGER.controller.entity == vehicle:
            constants.STATEMANAGER.transfer_control(self)

        else:
            self.controller.suppress_ai(False)

        # re-enable collisions
        self.world.entity_grid.set_enabled(self, True)

    def tick(self, render, block_input=False):
        Entity.tick(self, render, self.vehicle is not None)

    def render(self):
        # rendering is managed by the vehicle
        if not self.vehicle:
            Entity.render(self)


class Vehicle(Entity):
    def __init__(self, world, spritesheet=None):
        Entity.__init__(self, (32, 32), world, constants.EntityType.VEHICLE, spritesheet=spritesheet, clone_spritesheet=True, can_leave_world=False)

        self.aabb.height /= 2
        self.animator.spritesheet.set_colour(self._random_colour())

        self.seats = [(None, None) for _ in xrange(2)]  # (entity, list of sprites)
        self.passengers = {}

        # todo should move to road spawn
        self.world.move_to_spawn(self, 0)

        self.controller = ai.VehicleController(self)

    def catchup_aab(self):
        self.rect.center = self.aabb.midtop

    def _random_colour(self, alpha=255):
        """
        :return: A (hopefully) pretty random colour
        """
        high = random.randrange(127) + 127
        med = random.randrange(100) + 50
        low = random.randrange(50)
        c = [high, med, low]
        random.shuffle(c)
        c.append(alpha)
        return c

    def resolve_human_collision(self, human):
        # no collisions with passengers
        if human in self.passengers:
            return

        speed = self.velocity.get_length_sqrd()

        speed_factor = 1
        if speed > constants.Speed.VEHICLE_KILL ** 2:
            human.kill()
            speed_factor = 0.6
            # todo depends on the mass of the vehicle
            # todo blood splatter
        elif speed > constants.Speed.VEHICLE_DAMAGE ** 2:
            # todo damage
            speed_factor = 0.8

        # slow down
        if speed_factor < 1:
            self.controller.slow(speed_factor)

    def __getattr__(self, item):
        if item == "driver":
            return self.seats[0][0]
        return self.__dict__[item]

    def enter(self, human):
        """
        :return Whether or not the entering was successful
        """
        free_seat = self.get_first_free_seat()
        if free_seat < 0:
            return False
        sprites = human.animator.spritesheet.small_freeze_frames
        self.seats[free_seat] = human, sprites
        self.passengers[human] = free_seat
        human.entered_vehicle(self)
        return True

    def exit(self, seat):
        """
        :return: Whether or not the exiting was successful
        """
        human = self.seats[seat][0]
        if human:
            human.exited_vehicle(self)
            index = self.passengers[human]
            self.seats[index] = None, None
            del self.passengers[human]
            return True
        return False

    def is_empty(self):
        return not bool(self.passengers)

    def get_first_free_seat(self):
        """
        :return: Index of first free seat, otherwise -1 if there are none
        """
        return self.match_first_seat(lambda x: x is None)

    def get_first_full_seat(self):
        """
        :return: Index of first free seat, otherwise -1 if there are none
        """
        return self.match_first_seat(lambda x: x is not None)

    def match_first_seat(self, predicate):
        for i, (s, _) in enumerate(self.seats):
            if predicate(s):
                return i
        return -1

    def tick(self, render, block_input=False):
        Entity.tick(self, render)

        # passengers
        for human in self.passengers:
            if not human:
                continue
            human.move_entity(*self.transform)
            human.direction = self.direction

    def _render_seat(self, horizontal, front_seat):
        sprites = self.seats[0 if front_seat else 1][1]
        tc = list(self.rect.topcenter)
        tc[0] -= self.rect.width / 4
        tc[1] += 1
        delta = animation.HUMAN_DIMENSION[0] * constants.PASSENGER_SCALE

        if not horizontal:
            pos = tc[0] - delta * 0.25, tc[1]

        else:
            if self.direction == constants.Direction.WEST:
                delta *= -1
                tc[0] -= delta * 0.1

            if not front_seat:
                delta *= -1

            pos = tc[0] + (delta * 0.3), tc[1]

        sprite = sprites[self.direction]

        constants.SCREEN.draw_sprite_part(sprite, pos, (0, 0, sprite.get_width(), sprite.get_height() * 0.6))

    def render(self):
        Entity.render(self)

        if False and self.passengers:
            # todo: only if direction changes: calculate on turn() and save as a field
            back_seat = True
            front_seat = True

            horizontal = self.direction in constants.Direction.HORIZONTALS
            if not horizontal:
                if self.direction == constants.Direction.SOUTH:
                    back_seat = False
                else:
                    front_seat = False

            if front_seat and self.seats[0][0]:
                self._render_seat(horizontal, True)
            if back_seat and self.seats[1][0]:
                self._render_seat(horizontal, False)

        """
            don't have transparent windows: draw the car in two separate parts
            specify regions in car file (load a vehicle as xml? one tag is filepath, then offsets and rects etc)

            draw the entire car (opaque the windows)
            draw the passengers in the set rectangles for windows
            redraw the transparent window over the top
        """
