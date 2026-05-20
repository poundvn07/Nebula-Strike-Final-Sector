"""Missile Salvo weapon implementation."""

from __future__ import annotations

from src.entities.bullet import Bullet  # TODO: implement in Phase X — use stub for now
from src.utils.constants import MISSILE_SALVO_BASE_DAMAGE
from src.weapons.weapon import Direction, SkillEffect, Weapon, WeaponType

MISSILE_NAME = "Missile Salvo"
MISSILE_COOLDOWN_SECONDS = 1.1
MISSILE_PROJECTILE_SPEED = 430.0
MISSILE_EXPLOSION_RADIUS = 48.0
MISSILE_BARRAGE_COUNT = 12
MISSILE_BARRAGE_TARGETING = "nearest_enemy"


class MissileSalvo(Weapon):
    """Concrete missile weapon that produces homing explosive projectiles."""

    def __init__(self) -> None:
        """Initialize the missile salvo with missile-specific base values."""
        super().__init__(
            name=MISSILE_NAME,
            damage=MISSILE_SALVO_BASE_DAMAGE,
            cooldown=MISSILE_COOLDOWN_SECONDS,
            weapon_type=WeaponType.MISSILE,
        )

    def fire(self, origin_x: float, origin_y: float, direction: Direction) -> list[Bullet]:
        """Fire one homing missile that tracks the nearest enemy."""
        if not self.can_fire():
            return []

        bullet = self._create_bullet(
            origin_x=origin_x,
            origin_y=origin_y,
            direction=direction,
            speed=MISSILE_PROJECTILE_SPEED,
            homing=True,
            explosion_radius=MISSILE_EXPLOSION_RADIUS,
        )
        self._start_cooldown()
        return [bullet]

    def get_skill_effect(self) -> SkillEffect:
        """Return the Barrage simultaneous missile metadata."""
        return {
            "name": "Barrage",
            "effect": "missile_barrage",
            "missile_count": MISSILE_BARRAGE_COUNT,
            "targeting": MISSILE_BARRAGE_TARGETING,
            "damage": self.damage,
        }
