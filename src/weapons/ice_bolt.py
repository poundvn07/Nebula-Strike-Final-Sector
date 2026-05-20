"""Ice Bolt weapon implementation."""

from __future__ import annotations

from src.entities.bullet import Bullet  # TODO: implement in Phase X — use stub for now
from src.utils.constants import ICE_BOLT_BASE_DAMAGE
from src.weapons.weapon import Direction, SkillEffect, Weapon, WeaponType

ICE_NAME = "Ice Bolt"
ICE_COOLDOWN_SECONDS = 0.5
ICE_PROJECTILE_SPEED = 360.0
ICE_SLOW_DEBUFF = "SLOWED"
ICE_SLOW_DURATION_SECONDS = 2.0
ICE_SLOW_MULTIPLIER = 0.5
BLIZZARD_DURATION_SECONDS = 3.0
BLIZZARD_COVERAGE = "screen_wide"


class IceBolt(Weapon):
    """Concrete ice weapon that applies slowing debuffs through projectiles."""

    def __init__(self) -> None:
        """Initialize the ice bolt with ice-specific base values."""
        super().__init__(
            name=ICE_NAME,
            damage=ICE_BOLT_BASE_DAMAGE,
            cooldown=ICE_COOLDOWN_SECONDS,
            weapon_type=WeaponType.ICE,
        )

    def fire(self, origin_x: float, origin_y: float, direction: Direction) -> list[Bullet]:
        """Fire a slow bolt that applies the SLOWED debuff on hit."""
        if not self.can_fire():
            return []

        bullet = self._create_bullet(
            origin_x=origin_x,
            origin_y=origin_y,
            direction=direction,
            speed=ICE_PROJECTILE_SPEED,
            debuffs={
                ICE_SLOW_DEBUFF: {
                    "duration": ICE_SLOW_DURATION_SECONDS,
                    "multiplier": ICE_SLOW_MULTIPLIER,
                }
            },
        )
        self._start_cooldown()
        return [bullet]

    def get_skill_effect(self) -> SkillEffect:
        """Return the Blizzard screen-wide slow field metadata."""
        return {
            "name": "Blizzard",
            "effect": "slow_field",
            "coverage": BLIZZARD_COVERAGE,
            "duration": BLIZZARD_DURATION_SECONDS,
            "debuff": ICE_SLOW_DEBUFF,
            "multiplier": ICE_SLOW_MULTIPLIER,
        }
