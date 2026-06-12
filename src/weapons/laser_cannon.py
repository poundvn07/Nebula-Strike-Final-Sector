"""Laser Cannon weapon implementation."""

from __future__ import annotations

from src.entities.bullet import Bullet  # TODO: implement in Phase X — use stub for now
from src.utils.constants import LASER_CANNON_BASE_DAMAGE
from src.weapons.weapon import Direction, MAX_WEAPON_LEVEL, SkillEffect, Weapon, WeaponType

LASER_NAME = "Laser Cannon"
LASER_STATS_KEY = "laser_cannon"
LASER_COOLDOWN_SECONDS = 0.35
LASER_PROJECTILE_SPEED = 520.0
LASER_OVERCHARGE_DURATION_SECONDS = 2.0
LASER_OVERCHARGE_DAMAGE_MULTIPLIER = 1.5


class LaserCannon(Weapon):
    """Concrete laser weapon that specializes in fast direct-fire shots."""

    def __init__(self) -> None:
        """Initialize the laser cannon with laser-specific base values."""
        super().__init__(
            name=LASER_NAME,
            damage=LASER_CANNON_BASE_DAMAGE,
            cooldown=LASER_COOLDOWN_SECONDS,
            weapon_type=WeaponType.LASER,
            stats_key=LASER_STATS_KEY,
        )

    def fire(self, origin_x: float, origin_y: float, direction: Direction) -> list[Bullet]:
        """Fire one fast projectile, gaining piercing at level 3."""
        if not self.can_fire():
            return []

        bullet = self._create_bullet(
            origin_x=origin_x,
            origin_y=origin_y,
            direction=direction,
            speed=LASER_PROJECTILE_SPEED,
            is_piercing=self.upgrade_level >= MAX_WEAPON_LEVEL,
        )
        self._start_cooldown()
        return [bullet]

    def get_skill_effect(self) -> SkillEffect:
        """Return the Overcharge continuous all-screen beam metadata."""
        return {
            "name": "Overcharge",
            "effect": "continuous_beam",
            "coverage": "all_screen",
            "duration": LASER_OVERCHARGE_DURATION_SECONDS,
            "damage": self.damage * LASER_OVERCHARGE_DAMAGE_MULTIPLIER,
        }
