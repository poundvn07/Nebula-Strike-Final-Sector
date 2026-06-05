"""Thunder Rail weapon implementation."""

from __future__ import annotations

from src.entities.bullet import Bullet  # TODO: implement in Phase X — use stub for now
from src.utils.constants import THUNDER_RAIL_BASE_DAMAGE
from src.weapons.weapon import Direction, MAX_WEAPON_LEVEL, SkillEffect, Weapon, WeaponType

THUNDER_NAME = "Thunder Rail"
THUNDER_COOLDOWN_SECONDS = 0.8
THUNDER_PROJECTILE_SPEED = 500.0
THUNDER_DEFAULT_CHAIN_TARGETS = 2
THUNDER_LEVEL_THREE_CHAIN_TARGETS = 4
CHAIN_STORM_MAX_TARGETS = 5
CHAIN_STORM_DAMAGE_MULTIPLIER = 1.25


class ThunderRail(Weapon):
    """Concrete thunder weapon that chains damage between nearby enemies."""

    def __init__(self) -> None:
        """Initialize the thunder rail with thunder-specific base values."""
        super().__init__(
            name=THUNDER_NAME,
            damage=THUNDER_RAIL_BASE_DAMAGE,
            cooldown=THUNDER_COOLDOWN_SECONDS,
            weapon_type=WeaponType.THUNDER,
        )

    def fire(self, origin_x: float, origin_y: float, direction: Direction) -> list[Bullet]:
        """Fire a rail projectile that chains to nearby enemies."""
        if not self.can_fire():
            return []

        chain_count = (
            THUNDER_LEVEL_THREE_CHAIN_TARGETS
            if self.upgrade_level >= MAX_WEAPON_LEVEL
            else THUNDER_DEFAULT_CHAIN_TARGETS
        )
        bullet = self._create_bullet(
            origin_x=origin_x,
            origin_y=origin_y,
            direction=direction,
            speed=THUNDER_PROJECTILE_SPEED,
            chain_count=chain_count,
        )
        self._start_cooldown()
        return [bullet]

    def get_skill_effect(self) -> SkillEffect:
        """Return the Chain Storm max-target chain metadata."""
        return {
            "name": "Chain Storm",
            "effect": "chain_lightning",
            "max_targets": CHAIN_STORM_MAX_TARGETS,
            "damage": self.damage * CHAIN_STORM_DAMAGE_MULTIPLIER,
        }
