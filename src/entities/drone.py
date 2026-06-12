"""Abstract drone foundation for Nebula Strike companion systems."""

from __future__ import annotations

from abc import abstractmethod
from enum import Enum
from math import cos, sin
from typing import TYPE_CHECKING

import pygame

from src.entities.game_object import GameObject
from src.utils.constants import MIN_HEALTH

if TYPE_CHECKING:
    from src.enemies.enemy import Enemy
    from src.entities.feather_core import FeatherCore
    from src.entities.player_ship import PlayerShip

DRONE_WIDTH = 12
DRONE_HEIGHT = 12
DRONE_HP = 1
DRONE_ORBIT_SPEED = 2.6
DRONE_DEFAULT_ORBIT_ANGLE = 0.0
DRONE_DEFAULT_ORBIT_RADIUS = 92
DRONE_DEFAULT_SUMMON_COST = 30
DRONE_COLOR = (120, 240, 255)
DRONE_DESTROYED_COLOR = (90, 90, 90)
DRONE_CENTER_DIVISOR = 2.0


class DroneMode(Enum):
    """Enum describing drone targeting posture."""

    AUTO = "AUTO"
    FOLLOW = "FOLLOW"


class Drone(GameObject):
    """Abstract GameObject companion owned by PlayerShip and updated polymorphically."""

    def __init__(
        self,
        owner: PlayerShip,
        orbit_radius: int = DRONE_DEFAULT_ORBIT_RADIUS,
        fc_cost_to_summon: int = DRONE_DEFAULT_SUMMON_COST,
    ) -> None:
        """Initialize shared drone orbit, owner, cost, and one-hit durability."""
        super().__init__(
            x=owner.x,
            y=owner.y,
            width=DRONE_WIDTH,
            height=DRONE_HEIGHT,
            hp=DRONE_HP,
        )
        self.owner = owner
        self.orbit_angle = DRONE_DEFAULT_ORBIT_ANGLE
        self.orbit_radius = orbit_radius
        self.is_destroyed = False
        self.fc_cost_to_summon = fc_cost_to_summon
        self.mode = DroneMode.AUTO
        self.orbit_around_player(0.0)

    @abstractmethod
    def update_behavior(
        self,
        dt: float,
        player: PlayerShip,
        enemies: list[Enemy],
        fc_items: list[FeatherCore],
    ) -> list[object]:
        """Run subclass-specific drone behavior and return emitted gameplay objects."""

    def update(self, dt: float) -> None:
        """Advance default orbit movement for systems that update drones directly."""
        if not self.is_destroyed:
            self.orbit_around_player(dt)

    def render(self, surface: pygame.Surface) -> None:
        """Draw a simple drone circle until companion sprites are available."""
        color = DRONE_DESTROYED_COLOR if self.is_destroyed else DRONE_COLOR
        pygame.draw.circle(surface, color, self._center_position(), self.width // 2)

    def on_death(self) -> None:
        """Destroy and deactivate the drone."""
        self.is_destroyed = True
        self.active = False

    def orbit_around_player(self, dt: float) -> None:
        """Update this drone's position around its owner at orbit_radius."""
        self.orbit_angle += DRONE_ORBIT_SPEED * dt
        owner_center_x = self.owner.x + self.owner.width / DRONE_CENTER_DIVISOR
        owner_center_y = self.owner.y + self.owner.height / DRONE_CENTER_DIVISOR
        self.x = owner_center_x + cos(self.orbit_angle) * self.orbit_radius - self.width / DRONE_CENTER_DIVISOR
        self.y = owner_center_y + sin(self.orbit_angle) * self.orbit_radius - self.height / DRONE_CENTER_DIVISOR

    def take_damage(self, amount: int) -> None:
        """Destroy the drone on any positive damage because drones have no HP buffer."""
        if amount <= MIN_HEALTH or self.is_destroyed:
            return

        self.hp = MIN_HEALTH
        self.on_death()

    def set_mode(self, mode: DroneMode) -> None:
        """Set the current drone targeting posture."""
        self.mode = mode

    def _center_position(self) -> tuple[int, int]:
        """Return the integer center point used by simple drone rendering."""
        return (
            int(self.x + self.width / DRONE_CENTER_DIVISOR),
            int(self.y + self.height / DRONE_CENTER_DIVISOR),
        )
