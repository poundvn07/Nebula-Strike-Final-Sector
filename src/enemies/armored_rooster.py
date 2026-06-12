"""Armored Rooster enemy implementation."""

from __future__ import annotations

from src.entities.bullet import Bullet  # TODO: implement in Phase X — use stub for now
from src.entities.feather_core import FeatherCore
from src.enemies.enemy import Enemy
from src.utils.constants import MIN_HEALTH
from src.weapons.weapon import WeaponType

ARMORED_ROOSTER_WIDTH = 66
ARMORED_ROOSTER_HEIGHT = 61
ARMORED_ROOSTER_HP = 60
ARMORED_ROOSTER_PATROL_SPEED = 45.0
ARMORED_ROOSTER_SCORE_VALUE = 300
ARMORED_ROOSTER_FC_DROP_MIN = 5
ARMORED_ROOSTER_FC_DROP_MAX = 8
ARMORED_ROOSTER_ARMOR_HITS = 3
ARMORED_ROOSTER_ATTACK_INTERVAL_SECONDS = 4.0
ARMORED_ROOSTER_LASER_SPEED = 180.0
ARMORED_ROOSTER_LASER_DAMAGE = 14
ARMORED_ROOSTER_LASER_WIDTH = 10
ARMORED_ROOSTER_LASER_HEIGHT = 28
ARMORED_ROOSTER_PATROL_RADIUS = 120.0
ARMORED_ROOSTER_VERTICAL_SPEED = 0.0
ARMORED_ROOSTER_LASER_VX = 0.0


class ArmoredRooster(Enemy):
    """Tier 2 enemy that overrides damage handling with breakable armor."""

    def __init__(self, x: float, y: float) -> None:
        """Initialize a slow patrol enemy with armor separate from real HP."""
        super().__init__(
            x=x,
            y=y,
            width=ARMORED_ROOSTER_WIDTH,
            height=ARMORED_ROOSTER_HEIGHT,
            hp=ARMORED_ROOSTER_HP,
            vx=ARMORED_ROOSTER_PATROL_SPEED,
            vy=ARMORED_ROOSTER_VERTICAL_SPEED,
            fc_drop_min=ARMORED_ROOSTER_FC_DROP_MIN,
            fc_drop_max=ARMORED_ROOSTER_FC_DROP_MAX,
            score_value=ARMORED_ROOSTER_SCORE_VALUE,
        )
        self.armor_hp = ARMORED_ROOSTER_ARMOR_HITS
        self.patrol_origin_x = x
        self._start_attack_cooldown(ARMORED_ROOSTER_ATTACK_INTERVAL_SECONDS)

    @property
    def armor_intact(self) -> bool:
        """Return whether the armor layer is still absorbing non-ice hits."""
        return self.armor_hp > MIN_HEALTH

    def move(self, dt: float) -> None:
        """Overrides move() to perform a slow horizontal patrol."""
        self.x += self.vx * dt
        if abs(self.x - self.patrol_origin_x) >= ARMORED_ROOSTER_PATROL_RADIUS:
            self.vx = -self.vx

    def attack(self, dt: float) -> list[Bullet]:
        """Overrides attack() to fire a laser beam on a spaced cooldown."""
        self._update_attack_cooldown(dt)
        if not self._can_attack():
            return []

        self._start_attack_cooldown(ARMORED_ROOSTER_ATTACK_INTERVAL_SECONDS)
        return [
            self._create_enemy_bullet(
                vx=ARMORED_ROOSTER_LASER_VX,
                vy=ARMORED_ROOSTER_LASER_SPEED,
                damage=ARMORED_ROOSTER_LASER_DAMAGE,
                width=ARMORED_ROOSTER_LASER_WIDTH,
                height=ARMORED_ROOSTER_LASER_HEIGHT,
                metadata={"pattern": "laser_beam"},
            )
        ]

    def take_damage(
        self,
        amount: int,
        weapon_type: WeaponType | None = None,
        is_aoe: bool = False,
    ) -> list[FeatherCore]:
        """Apply ice damage directly while armor absorbs other damage first."""
        if amount <= MIN_HEALTH or not self.active:
            return []

        if weapon_type is not WeaponType.ICE and self.armor_intact:
            self.armor_hp = max(MIN_HEALTH, self.armor_hp - 1)
            return []

        return super().take_damage(amount)

    def on_death(self) -> list[FeatherCore]:
        """Overrides on_death() to drop 5-8 Feather Cores."""
        return self.drop_fc()
