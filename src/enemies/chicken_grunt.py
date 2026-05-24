"""Chicken Grunt enemy implementation."""

from __future__ import annotations

from src.entities.bullet import Bullet  # TODO: implement in Phase X — use stub for now
from src.entities.feather_core import FeatherCore
from src.enemies.enemy import Enemy, FormationOffset

CHICKEN_GRUNT_WIDTH = 36
CHICKEN_GRUNT_HEIGHT = 34
CHICKEN_GRUNT_HP = 20
CHICKEN_GRUNT_SPEED = 80.0
CHICKEN_GRUNT_SCORE_VALUE = 100
CHICKEN_GRUNT_FC_DROP_MIN = 1
CHICKEN_GRUNT_FC_DROP_MAX = 2
CHICKEN_GRUNT_ATTACK_INTERVAL_SECONDS = 2.0
CHICKEN_GRUNT_EGG_SPEED = 180.0
CHICKEN_GRUNT_EGG_DAMAGE = 8
CHICKEN_GRUNT_EGG_VX = 0.0


class ChickenGrunt(Enemy):
    """Tier 1 enemy that overrides move() with fixed formation flight."""

    def __init__(
        self,
        x: float,
        y: float,
        wave_num: int = 1,
        formation_offset: FormationOffset = (0.0, 0.0),
    ) -> None:
        """Initialize a basic formation enemy with a timed egg attack."""
        super().__init__(
            x=x,
            y=y,
            width=CHICKEN_GRUNT_WIDTH,
            height=CHICKEN_GRUNT_HEIGHT,
            hp=CHICKEN_GRUNT_HP,
            vx=CHICKEN_GRUNT_EGG_VX,
            vy=CHICKEN_GRUNT_SPEED,
            fc_drop_min=CHICKEN_GRUNT_FC_DROP_MIN,
            fc_drop_max=CHICKEN_GRUNT_FC_DROP_MAX,
            score_value=CHICKEN_GRUNT_SCORE_VALUE,
            formation_offset=formation_offset,
        )
        self.wave_num = wave_num
        self._start_attack_cooldown(CHICKEN_GRUNT_ATTACK_INTERVAL_SECONDS)

    def move(self, dt: float) -> None:
        """Overrides move() to keep the grunt in wave-based formation."""
        self._move_in_formation(dt=dt, wave_num=self.wave_num, speed=CHICKEN_GRUNT_SPEED)

    def attack(self, dt: float) -> list[Bullet]:
        """Overrides attack() to drop one egg straight down every 2 seconds."""
        self._update_attack_cooldown(dt)
        if not self._can_attack():
            return []

        self._start_attack_cooldown(CHICKEN_GRUNT_ATTACK_INTERVAL_SECONDS)
        return [
            self._create_enemy_bullet(
                vx=CHICKEN_GRUNT_EGG_VX,
                vy=CHICKEN_GRUNT_EGG_SPEED,
                damage=CHICKEN_GRUNT_EGG_DAMAGE,
                metadata={"pattern": "straight_egg"},
            )
        ]

    def on_death(self) -> list[FeatherCore]:
        """Overrides on_death() to drop 1-2 Feather Cores."""
        return self.drop_fc()
