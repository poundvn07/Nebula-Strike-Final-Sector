"""Abstract enemy foundation for Nebula Strike."""

from __future__ import annotations

from abc import abstractmethod
from math import cos, sin
from random import randint
from typing import TypeAlias

import pygame

from src.entities.bullet import Bullet
from src.entities.feather_core import FeatherCore
from src.entities.game_object import GameObject
from src.utils.assets import load_enemy_sprite, play_sound
from src.utils.constants import MIN_HEALTH

FormationOffset: TypeAlias = tuple[float, float]

READY_ATTACK_COOLDOWN_SECONDS = 0.0
DEFAULT_ATTACK_COOLDOWN_SCALE = 1.0
MIN_SCALED_ATTACK_COOLDOWN_SECONDS = 0.25
DEFAULT_ENEMY_COLOR = (255, 255, 255)
DEFAULT_FORMATION_OFFSET: FormationOffset = (0.0, 0.0)
FORMATION_PATTERN_COUNT = 3
GRID_FORMATION_PATTERN = 0
V_FORMATION_PATTERN = 1
SPIRAL_FORMATION_PATTERN = 2
V_FORMATION_X_SCALE = 0.5
SPIRAL_RADIUS = 24.0
SPIRAL_ANGULAR_SPEED = 2.0
FEATHER_CORE_UNIT_VALUE = 1
FEATHER_CORE_DROP_SPACING = 10.0
DEFAULT_BULLET_WIDTH = 8
DEFAULT_BULLET_HEIGHT = 12
BULLET_CENTER_DIVISOR = 2.0


class Enemy(GameObject):
    """Abstract GameObject subclass for polymorphic enemy movement and attacks."""

    def __init__(
        self,
        x: float,
        y: float,
        width: int,
        height: int,
        hp: int,
        vx: float,
        vy: float,
        fc_drop_min: int,
        fc_drop_max: int,
        score_value: int,
        formation_offset: FormationOffset = DEFAULT_FORMATION_OFFSET,
    ) -> None:
        """Initialize shared enemy state used by all concrete enemy subclasses."""
        super().__init__(x=x, y=y, width=width, height=height, hp=hp, vx=vx, vy=vy)
        self.fc_drop_min = fc_drop_min
        self.fc_drop_max = fc_drop_max
        self.score_value = score_value
        self.formation_offset = formation_offset
        self.spawn_x = x
        self.spawn_y = y
        self.attack_cooldown = READY_ATTACK_COOLDOWN_SECONDS
        self.formation_time = READY_ATTACK_COOLDOWN_SECONDS
        self.last_attack_bullets: list[Bullet] = []
        self.death_drops: list[FeatherCore] = []
        self.render_color = DEFAULT_ENEMY_COLOR

    @abstractmethod
    def move(self, dt: float) -> None:
        """Move the enemy according to subclass-specific behavior."""

    @abstractmethod
    def attack(self, dt: float) -> list[Bullet]:
        """Attack and return configured enemy bullet stubs."""

    @abstractmethod
    def on_death(self) -> list[FeatherCore]:
        """Return Feather Core drops for this enemy's death."""

    def update(self, dt: float) -> None:
        """Advance enemy behavior by moving and storing emitted attacks."""
        self.update_debuffs(dt)
        if not getattr(self, "stationary_wave_enemy", False):
            self.move(dt)
        self.last_attack_bullets = self.attack(dt)

    def render(self, surface: pygame.Surface) -> None:
        """Render this enemy with its selected sprite, falling back to a rectangle."""
        sprite = load_enemy_sprite(self)
        if sprite is None:
            pygame.draw.rect(surface, self.render_color, self.get_rect())
            return
        surface.blit(sprite, self.get_rect())

    def take_damage(self, amount: int) -> list[FeatherCore]:
        """Apply damage and return death drops when health reaches zero."""
        if amount <= MIN_HEALTH or not self.active:
            return []

        self.hp = max(MIN_HEALTH, self.hp - amount)
        if self.hp == MIN_HEALTH:
            self.active = False
            self.death_drops = self.on_death()
            sound_key = "boss_explosion" if getattr(self, "health_bar_visible", False) else "enemy_explosion"
            play_sound(sound_key)
            return self.death_drops
        return []

    def drop_fc(self) -> list[FeatherCore]:
        """Create a random number of Feather Core pickups within the enemy drop range."""
        drop_count = randint(self.fc_drop_min, self.fc_drop_max)
        return [self._create_feather_core(drop_index) for drop_index in range(drop_count)]

    def apply_debuff(self, debuff_type: str, duration: float) -> None:
        """
        Apply a status effect to this enemy.
        Stores active debuffs in self._active_debuffs dict.
        OOP note: base class provides default debuff storage;
        subclasses can override to add special reactions
        (e.g. ArmoredRooster ignores SLOWED, Missile AOE bypasses armor).
        """
        if not hasattr(self, "_active_debuffs"):
            self._active_debuffs = {}
        self._active_debuffs[debuff_type] = duration

    def update_debuffs(self, dt: float) -> None:
        """Tick all active debuff durations. Remove expired debuffs."""
        if not hasattr(self, "_active_debuffs"):
            self._active_debuffs = {}
            return
        expired = [k for k, v in self._active_debuffs.items() if v - dt <= 0]
        for k in expired:
            del self._active_debuffs[k]
        for k in self._active_debuffs:
            self._active_debuffs[k] -= dt

    @property
    def is_slowed(self) -> bool:
        """Return whether this enemy currently has the SLOWED debuff."""
        return hasattr(self, "_active_debuffs") and "SLOWED" in self._active_debuffs

    @property
    def is_stunned(self) -> bool:
        """Return whether this enemy currently has the STUNNED debuff."""
        return hasattr(self, "_active_debuffs") and "STUNNED" in self._active_debuffs

    def _create_feather_core(self, drop_index: int) -> FeatherCore:
        """Create one configured Feather Core pickup."""
        feather_core = FeatherCore(
            x=self.x + drop_index * FEATHER_CORE_DROP_SPACING,
            y=self.y,
            value=FEATHER_CORE_UNIT_VALUE,
        )
        feather_core.source_enemy = self.__class__.__name__
        return feather_core

    def _create_enemy_bullet(
        self,
        vx: float,
        vy: float,
        damage: int,
        *,
        width: int = DEFAULT_BULLET_WIDTH,
        height: int = DEFAULT_BULLET_HEIGHT,
        is_aoe: bool = False,
        metadata: dict[str, object] | None = None,
    ) -> Bullet:
        """Create one configured enemy Bullet stub without implementing projectile logic."""
        bullet = Bullet()
        bullet.x = self.x + self.width / BULLET_CENTER_DIVISOR
        bullet.y = self.y + self.height
        bullet.vx = vx
        bullet.vy = vy
        bullet.width = width
        bullet.height = height
        bullet.damage = damage
        bullet.owner = "enemy"
        bullet.is_aoe = is_aoe
        bullet.source_enemy = self.__class__.__name__
        bullet.metadata = dict(metadata or {})
        bullet.active = True
        return bullet

    def _update_attack_cooldown(self, dt: float) -> None:
        """Tick down attack cooldown without going below ready."""
        if dt <= READY_ATTACK_COOLDOWN_SECONDS:
            return

        self.attack_cooldown = max(READY_ATTACK_COOLDOWN_SECONDS, self.attack_cooldown - dt)

    def _can_attack(self) -> bool:
        """Return whether the enemy can emit an attack this frame."""
        return self.attack_cooldown <= READY_ATTACK_COOLDOWN_SECONDS

    def _start_attack_cooldown(self, cooldown_seconds: float) -> None:
        """Reset the enemy attack cooldown after a successful attack."""
        cooldown_scale = float(getattr(self, "attack_cooldown_scale", DEFAULT_ATTACK_COOLDOWN_SCALE))
        scaled_cooldown = cooldown_seconds * cooldown_scale
        self.attack_cooldown = max(MIN_SCALED_ATTACK_COOLDOWN_SECONDS, scaled_cooldown)

    def _move_in_formation(self, dt: float, wave_num: int, speed: float) -> None:
        """Apply shared V, grid, or spiral formation movement based on wave number."""
        self.formation_time += dt
        pattern = wave_num % FORMATION_PATTERN_COUNT
        self.y += speed * dt

        if pattern == V_FORMATION_PATTERN:
            self.x = self.spawn_x + self.formation_offset[0] * V_FORMATION_X_SCALE
        elif pattern == GRID_FORMATION_PATTERN:
            self.x = self.spawn_x + self.formation_offset[0]
        elif pattern == SPIRAL_FORMATION_PATTERN:
            angle = self.formation_time * SPIRAL_ANGULAR_SPEED + self.formation_offset[0]
            self.x = self.spawn_x + cos(angle) * SPIRAL_RADIUS
            self.y += sin(angle) * SPIRAL_RADIUS * dt
