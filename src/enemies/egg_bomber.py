"""Egg Bomber enemy implementation."""

from __future__ import annotations

from src.entities.bullet import Bullet
from src.entities.pickup import Pickup
from src.enemies.enemy import Enemy, FormationOffset

EGG_BOMBER_WIDTH = 51
EGG_BOMBER_HEIGHT = 46
EGG_BOMBER_HP = 26
EGG_BOMBER_SPEED = 96.0
EGG_BOMBER_SCORE_VALUE = 140
EGG_BOMBER_FC_DROP_MIN = 1
EGG_BOMBER_FC_DROP_MAX = 2
EGG_BOMBER_ATTACK_INTERVAL_SECONDS = 4.4
EGG_BOMBER_EGG_SPEED = 105.0
EGG_BOMBER_EGG_DAMAGE = 7
EGG_BOMBER_CLUSTER_SIDE_VX = 42.0
EGG_BOMBER_CENTER_VX = 0.0


class EggBomber(Enemy):
    """Tier 1 enemy that overrides attack() with a three-egg cluster spread."""

    def __init__(
        self,
        x: float,
        y: float,
        wave_num: int = 1,
        formation_offset: FormationOffset = (0.0, 0.0),
    ) -> None:
        """Initialize a faster formation enemy with cluster egg attacks."""
        super().__init__(
            x=x,
            y=y,
            width=EGG_BOMBER_WIDTH,
            height=EGG_BOMBER_HEIGHT,
            hp=EGG_BOMBER_HP,
            vx=EGG_BOMBER_CENTER_VX,
            vy=EGG_BOMBER_SPEED,
            fc_drop_min=EGG_BOMBER_FC_DROP_MIN,
            fc_drop_max=EGG_BOMBER_FC_DROP_MAX,
            score_value=EGG_BOMBER_SCORE_VALUE,
            formation_offset=formation_offset,
        )
        self.wave_num = wave_num
        self._start_attack_cooldown(EGG_BOMBER_ATTACK_INTERVAL_SECONDS)

    def move(self, dt: float) -> None:
        """Overrides move() to reuse formation flight at a slightly faster speed."""
        self._move_in_formation(dt=dt, wave_num=self.wave_num, speed=EGG_BOMBER_SPEED)

    def attack(self, dt: float) -> list[Bullet]:
        """Overrides attack() to drop a cluster of 3 spread eggs."""
        self._update_attack_cooldown(dt)
        if not self._can_attack():
            return []

        self._start_attack_cooldown(EGG_BOMBER_ATTACK_INTERVAL_SECONDS)
        return [
            self._create_enemy_bullet(
                vx=-EGG_BOMBER_CLUSTER_SIDE_VX,
                vy=EGG_BOMBER_EGG_SPEED,
                damage=EGG_BOMBER_EGG_DAMAGE,
                metadata={"pattern": "cluster_left"},
            ),
            self._create_enemy_bullet(
                vx=EGG_BOMBER_CENTER_VX,
                vy=EGG_BOMBER_EGG_SPEED,
                damage=EGG_BOMBER_EGG_DAMAGE,
                metadata={"pattern": "cluster_center"},
            ),
            self._create_enemy_bullet(
                vx=EGG_BOMBER_CLUSTER_SIDE_VX,
                vy=EGG_BOMBER_EGG_SPEED,
                damage=EGG_BOMBER_EGG_DAMAGE,
                metadata={"pattern": "cluster_right"},
            ),
        ]

    def on_death(self) -> list[Pickup]:
        """Overrides on_death() to drop 1-2 Feather Cores."""
        return self.drop_fc()
