"""Abstract weapon hierarchy foundation for Nebula Strike."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from math import hypot
from typing import TypeAlias

from src.entities.bullet import Bullet  # TODO: implement in Phase X — use stub for now

Direction: TypeAlias = tuple[float, float]
SkillEffect: TypeAlias = dict[str, object]

READY_COOLDOWN_SECONDS = 0.0
ZERO_VECTOR_MAGNITUDE = 0.0
MIN_WEAPON_LEVEL = 1
SECOND_WEAPON_LEVEL = 2
MAX_WEAPON_LEVEL = 3
LEVEL_ONE_TO_TWO_UPGRADE_COST = 25
LEVEL_TWO_TO_THREE_UPGRADE_COST = 50
NO_UPGRADE_AVAILABLE_COST = 0

DEFAULT_FIRE_DIRECTION: Direction = (0.0, -1.0)
DEFAULT_PROJECTILE_WIDTH = 8
DEFAULT_PROJECTILE_HEIGHT = 16
DEFAULT_CHAIN_TARGETS = 0
DEFAULT_EXPLOSION_RADIUS = 0.0


class WeaponType(Enum):
    """Enum identifying the five polymorphic weapon families."""

    LASER = "LASER"
    PLASMA = "PLASMA"
    ICE = "ICE"
    THUNDER = "THUNDER"
    MISSILE = "MISSILE"


class Weapon(ABC):
    """Abstract base class for all player weapons and their shared behavior."""

    def __init__(self, name: str, damage: int, cooldown: float, weapon_type: WeaponType) -> None:
        """Initialize shared weapon state used polymorphically by all subclasses."""
        self.name = name
        self.damage = damage
        self.cooldown = cooldown
        self.current_cooldown = READY_COOLDOWN_SECONDS
        self.upgrade_level = MIN_WEAPON_LEVEL
        self.weapon_type = weapon_type

    @abstractmethod
    def fire(self, origin_x: float, origin_y: float, direction: Direction) -> list[Bullet]:
        """Fire the weapon and return configured bullet stubs."""

    @abstractmethod
    def get_skill_effect(self) -> SkillEffect:
        """Return metadata for this weapon's special skill effect."""

    def upgrade(self) -> bool:
        """Increase the weapon level if it is below level 3."""
        if self.upgrade_level >= MAX_WEAPON_LEVEL:
            return False

        self.upgrade_level += 1
        return True

    def can_fire(self) -> bool:
        """Return whether the weapon cooldown has finished."""
        return self.current_cooldown <= READY_COOLDOWN_SECONDS

    def update_cooldown(self, dt: float) -> None:
        """Reduce the current cooldown by delta time without going below ready."""
        if dt <= READY_COOLDOWN_SECONDS:
            return

        self.current_cooldown = max(READY_COOLDOWN_SECONDS, self.current_cooldown - dt)

    def get_upgrade_cost(self) -> int:
        """Return the FC cost for the next upgrade level."""
        if self.upgrade_level == MIN_WEAPON_LEVEL:
            return LEVEL_ONE_TO_TWO_UPGRADE_COST
        if self.upgrade_level == SECOND_WEAPON_LEVEL:
            return LEVEL_TWO_TO_THREE_UPGRADE_COST
        return NO_UPGRADE_AVAILABLE_COST

    def _start_cooldown(self) -> None:
        """Set the weapon cooldown after a successful shot."""
        self.current_cooldown = self.cooldown

    def _create_bullet(
        self,
        origin_x: float,
        origin_y: float,
        direction: Direction,
        speed: float,
        *,
        width: int = DEFAULT_PROJECTILE_WIDTH,
        height: int = DEFAULT_PROJECTILE_HEIGHT,
        piercing: bool = False,
        chain_targets: int = DEFAULT_CHAIN_TARGETS,
        homing: bool = False,
        explosion_radius: float = DEFAULT_EXPLOSION_RADIUS,
        debuffs: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Bullet:
        """Create a configured Bullet stub without implementing bullet physics yet."""
        normalized_x, normalized_y = normalize_direction(direction)
        bullet = Bullet()
        bullet.x = origin_x
        bullet.y = origin_y
        bullet.vx = normalized_x * speed
        bullet.vy = normalized_y * speed
        bullet.width = width
        bullet.height = height
        bullet.damage = self.damage
        bullet.weapon_type = self.weapon_type
        bullet.source_weapon = self.name
        bullet.upgrade_level = self.upgrade_level
        bullet.piercing = piercing
        bullet.chain_targets = chain_targets
        bullet.homing = homing
        bullet.tracking_mode = "nearest_enemy" if homing else None
        bullet.explosion_radius = explosion_radius
        bullet.debuffs = dict(debuffs or {})
        bullet.metadata = dict(metadata or {})
        bullet.active = True
        return bullet


def normalize_direction(direction: Direction) -> Direction:
    """Return a normalized direction, defaulting upward for a zero vector."""
    dx, dy = direction
    magnitude = hypot(dx, dy)
    if magnitude <= ZERO_VECTOR_MAGNITUDE:
        return DEFAULT_FIRE_DIRECTION
    return dx / magnitude, dy / magnitude
