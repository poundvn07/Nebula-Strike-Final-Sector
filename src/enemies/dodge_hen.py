"""Dodge Hen enemy implementation."""

from __future__ import annotations

from math import sin
from typing import Sequence

from src.entities.bullet import Bullet  # TODO: implement in Phase X — use stub for now
from src.entities.feather_core import FeatherCore
from src.enemies.enemy import Enemy
from src.utils.constants import MIN_HEALTH
from src.weapons.weapon import WeaponType

DODGE_HEN_WIDTH = 42
DODGE_HEN_HEIGHT = 38
DODGE_HEN_HP = 44
DODGE_HEN_STRAFE_SPEED = 115.0
DODGE_HEN_DODGE_SPEED = 180.0
DODGE_HEN_SCORE_VALUE = 320
DODGE_HEN_FC_DROP_MIN = 5
DODGE_HEN_FC_DROP_MAX = 8
DODGE_HEN_ATTACK_INTERVAL_SECONDS = 1.25
DODGE_HEN_PELLET_SPEED = 230.0
DODGE_HEN_PELLET_DAMAGE = 6
DODGE_HEN_PELLET_WIDTH = 6
DODGE_HEN_PELLET_HEIGHT = 10
DODGE_HEN_THREAT_X_RANGE = 48.0
DODGE_HEN_THREAT_Y_RANGE = 140.0
MIN_THREAT_DISTANCE = 0.0
DODGE_HEN_STRAFE_AMPLITUDE = 60.0
DODGE_HEN_STRAFE_FREQUENCY = 2.5
DODGE_HEN_VERTICAL_SPEED = 0.0
DODGE_HEN_PELLET_VX = 0.0
LEFT_DODGE_DIRECTION = -1.0
RIGHT_DODGE_DIRECTION = 1.0


class DodgeHen(Enemy):
    """Tier 2 enemy that overrides move() to strafe and dodge bullet threats."""

    def __init__(
        self,
        x: float,
        y: float,
        incoming_bullets: Sequence[Bullet] | None = None,
    ) -> None:
        """Initialize an evasive enemy that only missile AOE can damage."""
        super().__init__(
            x=x,
            y=y,
            width=DODGE_HEN_WIDTH,
            height=DODGE_HEN_HEIGHT,
            hp=DODGE_HEN_HP,
            vx=DODGE_HEN_STRAFE_SPEED,
            vy=DODGE_HEN_VERTICAL_SPEED,
            fc_drop_min=DODGE_HEN_FC_DROP_MIN,
            fc_drop_max=DODGE_HEN_FC_DROP_MAX,
            score_value=DODGE_HEN_SCORE_VALUE,
        )
        self.incoming_bullets = list(incoming_bullets or [])
        self.strafe_time = DODGE_HEN_VERTICAL_SPEED
        self._start_attack_cooldown(DODGE_HEN_ATTACK_INTERVAL_SECONDS)

    def move(self, dt: float) -> None:
        """Overrides move() to implement evasive behavior based on bullet positions."""
        self.strafe_time += dt
        threat = self._nearest_threat()
        if threat is not None:
            threat_x = getattr(threat, "x", self.x)
            dodge_direction = LEFT_DODGE_DIRECTION if threat_x >= self.x else RIGHT_DODGE_DIRECTION
            self.x += dodge_direction * DODGE_HEN_DODGE_SPEED * dt
            return

        self.x += sin(self.strafe_time * DODGE_HEN_STRAFE_FREQUENCY) * DODGE_HEN_STRAFE_AMPLITUDE * dt

    def attack(self, dt: float) -> list[Bullet]:
        """Overrides attack() to fire small pellets on a short cooldown."""
        self._update_attack_cooldown(dt)
        if not self._can_attack():
            return []

        self._start_attack_cooldown(DODGE_HEN_ATTACK_INTERVAL_SECONDS)
        return [
            self._create_enemy_bullet(
                vx=DODGE_HEN_PELLET_VX,
                vy=DODGE_HEN_PELLET_SPEED,
                damage=DODGE_HEN_PELLET_DAMAGE,
                width=DODGE_HEN_PELLET_WIDTH,
                height=DODGE_HEN_PELLET_HEIGHT,
                metadata={"pattern": "small_pellet"},
            )
        ]

    def take_damage(
        self,
        amount: int,
        weapon_type: WeaponType | None = None,
        is_aoe: bool = False,
    ) -> list[FeatherCore]:
        """Only accept damage from AOE Missile bullets; ignore all other hits."""
        if amount <= MIN_HEALTH or not self.active:
            return []
        if weapon_type is not WeaponType.MISSILE or not is_aoe:
            return []

        return super().take_damage(amount)

    def on_death(self) -> list[FeatherCore]:
        """Overrides on_death() to drop 5-8 Feather Cores."""
        return self.drop_fc()

    def _nearest_threat(self) -> Bullet | None:
        """Return the first nearby incoming bullet that should trigger a dodge."""
        for bullet in self.incoming_bullets:
            bullet_x = getattr(bullet, "x", self.x)
            bullet_y = getattr(bullet, "y", self.y)
            if (
                abs(bullet_x - self.x) <= DODGE_HEN_THREAT_X_RANGE
                and MIN_THREAT_DISTANCE <= self.y - bullet_y <= DODGE_HEN_THREAT_Y_RANGE
            ):
                return bullet
        return None
