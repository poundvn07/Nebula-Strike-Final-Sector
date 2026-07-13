"""Kamikaze Chicken enemy implementation."""

from __future__ import annotations

from math import hypot

from src.entities.bullet import Bullet
from src.entities.feather_core import FeatherCore
from src.enemies.enemy import Enemy
from src.utils.constants import SCREEN_HEIGHT, SCREEN_WIDTH

KAMIKAZE_WIDTH = 43
KAMIKAZE_HEIGHT = 43
KAMIKAZE_HP = 16
KAMIKAZE_PATROL_SPEED = 90.0
KAMIKAZE_DIVE_SPEED = 260.0
KAMIKAZE_SCORE_VALUE = 120
KAMIKAZE_FC_DROP_MIN = 1
KAMIKAZE_FC_DROP_MAX = 1
KAMIKAZE_HALF_HEALTH_RATIO = 0.5
KAMIKAZE_COLLISION_DAMAGE = 18
KAMIKAZE_PATROL_RADIUS = 80.0
KAMIKAZE_EXPLOSION_RADIUS = 38.0
SCREEN_CENTER_DIVISOR = 2.0
ZERO_DISTANCE = 0.0
DEFAULT_DIVE_DX = 0.0
DEFAULT_DIVE_DY = 1.0
KAMIKAZE_VERTICAL_SPEED = 0.0


class KamikazeChicken(Enemy):
    """Tier 1 enemy that overrides move() to dive when badly damaged."""

    def __init__(
        self,
        x: float,
        y: float,
        player_position: tuple[float, float] = (SCREEN_WIDTH / SCREEN_CENTER_DIVISOR, SCREEN_HEIGHT),
    ) -> None:
        """Initialize a kamikaze enemy with patrol state and collision damage."""
        super().__init__(
            x=x,
            y=y,
            width=KAMIKAZE_WIDTH,
            height=KAMIKAZE_HEIGHT,
            hp=KAMIKAZE_HP,
            vx=KAMIKAZE_PATROL_SPEED,
            vy=KAMIKAZE_VERTICAL_SPEED,
            fc_drop_min=KAMIKAZE_FC_DROP_MIN,
            fc_drop_max=KAMIKAZE_FC_DROP_MAX,
            score_value=KAMIKAZE_SCORE_VALUE,
        )
        self.player_position = player_position
        self.collision_damage = KAMIKAZE_COLLISION_DAMAGE
        self.patrol_origin_x = x
        self.death_explosion_hitbox: tuple[float, float, float, float] | None = None

    def move(self, dt: float) -> None:
        """Overrides move() to patrol until HP < 50%, then dive at the player."""
        if self.hp < self.max_hp * KAMIKAZE_HALF_HEALTH_RATIO:
            dx = self.player_position[0] - self.x
            dy = self.player_position[1] - self.y
            distance = hypot(dx, dy)
            if distance <= ZERO_DISTANCE:
                dx = DEFAULT_DIVE_DX
                dy = DEFAULT_DIVE_DY
                distance = DEFAULT_DIVE_DY
            self.vx = dx / distance * KAMIKAZE_DIVE_SPEED
            self.vy = dy / distance * KAMIKAZE_DIVE_SPEED
        else:
            if abs(self.x - self.patrol_origin_x) >= KAMIKAZE_PATROL_RADIUS:
                self.vx = -self.vx
            self.vy = KAMIKAZE_VERTICAL_SPEED

        self.x += self.vx * dt
        self.y += self.vy * dt

    def attack(self, dt: float) -> list[Bullet]:
        """Overrides attack() with collision damage only and no projectile."""
        return []

    def on_death(self) -> list[FeatherCore]:
        """Overrides on_death() to drop 1 FC and create a small explosion hitbox."""
        self.death_explosion_hitbox = (
            self.x - KAMIKAZE_EXPLOSION_RADIUS,
            self.y - KAMIKAZE_EXPLOSION_RADIUS,
            self.width + KAMIKAZE_EXPLOSION_RADIUS * SCREEN_CENTER_DIVISOR,
            self.height + KAMIKAZE_EXPLOSION_RADIUS * SCREEN_CENTER_DIVISOR,
        )
        return self.drop_fc()
