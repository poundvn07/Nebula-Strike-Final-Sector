"""Shield Drone companion implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from src.entities.bullet import Bullet, ENEMY_BULLET_OWNER
from src.entities.drone import DRONE_DEFAULT_SUMMON_COST, Drone
from src.entities.feather_core import FeatherCore
from src.entities.game_object import GameObject

if TYPE_CHECKING:
    from src.entities.player_ship import PlayerShip

SHIELD_DRONE_ORBIT_RADIUS = 60
SHIELD_DRONE_UNLOCK_COST = 40
SHIELD_DRONE_UNLOCK_TIER = 2
SHIELD_DRONE_ABSORB_COOLDOWN_SECONDS = 5.0
SHIELD_DRONE_ABSORB_RADIUS = 42.0
SHIELD_BUBBLE_READY_COLOR = (80, 180, 255)
SHIELD_BUBBLE_RECHARGING_COLOR = (90, 90, 140)
SHIELD_BUBBLE_WIDTH = 2
DRONE_CENTER_DIVISOR = 2.0


class ShieldDrone(Drone):
    """Drone subclass that absorbs one incoming enemy bullet on a recharge timer."""

    unlock_cost = SHIELD_DRONE_UNLOCK_COST
    unlock_tier = SHIELD_DRONE_UNLOCK_TIER

    def __init__(self, owner: PlayerShip) -> None:
        """Initialize a defensive drone with a 5 second absorb cooldown."""
        super().__init__(
            owner=owner,
            orbit_radius=SHIELD_DRONE_ORBIT_RADIUS,
            fc_cost_to_summon=DRONE_DEFAULT_SUMMON_COST,
        )
        self.absorb_cooldown = 0.0
        self.shield_bubble_visible = True
        self.shield_recharging = False
        self.incoming_enemy_bullets: list[Bullet] = []

    def update_behavior(
        self,
        dt: float,
        player: PlayerShip,
        enemies: list[GameObject],
        fc_items: list[FeatherCore],
    ) -> list[object]:
        """Orbit and absorb one tracked enemy bullet when the shield is ready."""
        self.orbit_around_player(dt)
        self.absorb_cooldown = max(0.0, self.absorb_cooldown - dt)
        self.shield_recharging = self.absorb_cooldown > 0.0
        if self.shield_recharging:
            return []

        bullet = self._nearest_absorbable_bullet()
        if bullet is None:
            return []

        bullet.active = False
        self.absorb_cooldown = SHIELD_DRONE_ABSORB_COOLDOWN_SECONDS
        self.shield_recharging = True
        return []

    def render(self, surface: pygame.Surface) -> None:
        """Draw the drone plus ready/recharging shield bubble visual cue."""
        super().render(surface)
        if not self.shield_bubble_visible or self.is_destroyed:
            return

        color = SHIELD_BUBBLE_RECHARGING_COLOR if self.shield_recharging else SHIELD_BUBBLE_READY_COLOR
        pygame.draw.circle(surface, color, self._center_position(), int(SHIELD_DRONE_ABSORB_RADIUS), SHIELD_BUBBLE_WIDTH)

    def track_enemy_bullets(self, bullets: list[Bullet]) -> None:
        """Store enemy bullets that this shield may absorb on its next update."""
        self.incoming_enemy_bullets = bullets

    def _nearest_absorbable_bullet(self) -> Bullet | None:
        """Return the nearest active enemy bullet inside the absorb radius."""
        active_bullets = [
            bullet
            for bullet in self.incoming_enemy_bullets
            if getattr(bullet, "active", True)
            and getattr(bullet, "owner", None) == ENEMY_BULLET_OWNER
            and _distance_squared(self, bullet) <= SHIELD_DRONE_ABSORB_RADIUS**2
        ]
        if not active_bullets:
            return None
        return min(active_bullets, key=lambda bullet: _distance_squared(self, bullet))


def _distance_squared(drone: ShieldDrone, bullet: Bullet) -> float:
    """Return squared distance between the shield drone and a bullet."""
    dx = bullet.x - drone.x
    dy = bullet.y - drone.y
    return dx * dx + dy * dy
