"""Plasma Spread weapon implementation."""

from __future__ import annotations

from math import cos, radians, sin

from src.entities.bullet import Bullet  # TODO: implement in Phase X — use stub for now
from src.utils.constants import PLASMA_SPREAD_BASE_DAMAGE
from src.weapons.weapon import Direction, MAX_WEAPON_LEVEL, SkillEffect, Weapon, WeaponType, normalize_direction

PLASMA_NAME = "Plasma Spread"
PLASMA_STATS_KEY = "plasma_spread"
PLASMA_COOLDOWN_SECONDS = 0.55
PLASMA_PROJECTILE_SPEED = 390.0
PLASMA_DEFAULT_SHOT_COUNT = 3
PLASMA_LEVEL_THREE_SHOT_COUNT = 3
PLASMA_SPREAD_STEP_DEGREES = 15.0
PLASMA_INDEX_OFFSET = 1
PLASMA_CENTER_DIVISOR = 2.0
PLASMA_NOVA_RADIUS = 110.0
PLASMA_NOVA_DAMAGE_MULTIPLIER = 1.5


class PlasmaSpread(Weapon):
    """Concrete plasma weapon that overrides firing with a spread fan."""

    def __init__(self) -> None:
        """Initialize the plasma spread with plasma-specific base values."""
        super().__init__(
            name=PLASMA_NAME,
            damage=PLASMA_SPREAD_BASE_DAMAGE,
            cooldown=PLASMA_COOLDOWN_SECONDS,
            weapon_type=WeaponType.PLASMA,
            stats_key=PLASMA_STATS_KEY,
        )

    def fire(self, origin_x: float, origin_y: float, direction: Direction) -> list[Bullet]:
        """Fire a controlled 3-shot fan at every level."""
        if not self.can_fire():
            return []

        shot_count = (
            PLASMA_LEVEL_THREE_SHOT_COUNT
            if self.upgrade_level >= MAX_WEAPON_LEVEL
            else PLASMA_DEFAULT_SHOT_COUNT
        )
        center_index = (shot_count - PLASMA_INDEX_OFFSET) / PLASMA_CENTER_DIVISOR
        bullets = [
            self._create_bullet(
                origin_x=origin_x,
                origin_y=origin_y,
                direction=_rotate_direction(direction, (shot_index - center_index) * PLASMA_SPREAD_STEP_DEGREES),
                speed=PLASMA_PROJECTILE_SPEED,
            )
            for shot_index in range(shot_count)
        ]
        self._start_cooldown()
        return bullets

    def get_skill_effect(self) -> SkillEffect:
        """Return the Nova Burst large AOE explosion metadata."""
        return {
            "name": "Nova Burst",
            "effect": "aoe_explosion",
            "radius": PLASMA_NOVA_RADIUS,
            "damage": self.damage * PLASMA_NOVA_DAMAGE_MULTIPLIER,
        }


def _rotate_direction(direction: Direction, degrees: float) -> Direction:
    """Rotate a normalized direction by the provided degree offset."""
    dx, dy = normalize_direction(direction)
    angle = radians(degrees)
    return dx * cos(angle) - dy * sin(angle), dx * sin(angle) + dy * cos(angle)
