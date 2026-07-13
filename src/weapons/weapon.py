"""Abstract weapon hierarchy foundation for Nebula Strike."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from json import load
from math import hypot
from pathlib import Path
from typing import TypeAlias

from src.entities.bullet import Bullet 

Direction: TypeAlias = tuple[float, float]
WeaponLevelStats: TypeAlias = dict[int, dict[str, int | float]]

WEAPON_STATS_PATH = Path(__file__).resolve().parents[2] / "data" / "weapon_stats.json"
READY_COOLDOWN_SECONDS = 0.0
ZERO_VECTOR_MAGNITUDE = 0.0
MIN_WEAPON_LEVEL = 1
SECOND_WEAPON_LEVEL = 2
MAX_WEAPON_LEVEL = 3
LEVEL_ONE_TO_TWO_UPGRADE_COST = 120
LEVEL_TWO_TO_THREE_UPGRADE_COST = 260
NO_UPGRADE_AVAILABLE_COST = 0

DEFAULT_FIRE_DIRECTION: Direction = (0.0, -1.0)
DEFAULT_PROJECTILE_WIDTH = 8
DEFAULT_PROJECTILE_HEIGHT = 16
DEFAULT_CHAIN_COUNT = 0
DEFAULT_AOE_RADIUS = 0
PLAYER_BULLET_OWNER = "player"
_WEAPON_STATS_CACHE: dict[str, WeaponLevelStats] | None = None


class WeaponType(Enum):
    """Enum identifying weapon families used by concrete weapon subclasses."""

    LASER = "LASER"
    PLASMA = "PLASMA"
    MISSILE = "MISSILE"


class ComboType(Enum):
    """Names the supported two-weapon attacks resolved by PlayerShip."""

    ION_BEAM = "ION_BEAM"
    HOMING_NOVA = "HOMING_NOVA"


class Weapon(ABC):
    """Abstract base class for all player weapons and their shared behavior."""

    def __init__(
        self,
        name: str,
        damage: int,
        cooldown: float,
        weapon_type: WeaponType,
        stats_key: str | None = None,
    ) -> None:
        """Initialize shared weapon state used polymorphically by all subclasses."""
        self.name = name
        self.damage = damage
        self.cooldown = cooldown
        self.current_cooldown = READY_COOLDOWN_SECONDS
        self.upgrade_level = MIN_WEAPON_LEVEL
        self.weapon_type = weapon_type
        self.stats_key = stats_key
        self._level_stats = _load_weapon_level_stats(stats_key)
        self._apply_level_stats()

    @abstractmethod
    def fire(self, origin_x: float, origin_y: float, direction: Direction) -> list[Bullet]:
        """Fire the weapon and return configured bullet stubs."""

    def upgrade(self) -> bool:
        """Increase the weapon level if it is below level 3."""
        if self.upgrade_level >= MAX_WEAPON_LEVEL:
            return False

        self.upgrade_level += 1
        self._apply_level_stats()
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
        next_level = self.upgrade_level + 1
        if self._level_stats:
            next_stats = self._level_stats.get(next_level, {})
            return int(next_stats.get("upgrade_cost", NO_UPGRADE_AVAILABLE_COST))

        if self.upgrade_level == MIN_WEAPON_LEVEL:
            return LEVEL_ONE_TO_TWO_UPGRADE_COST
        if self.upgrade_level == SECOND_WEAPON_LEVEL:
            return LEVEL_TWO_TO_THREE_UPGRADE_COST
        return NO_UPGRADE_AVAILABLE_COST

    def _apply_level_stats(self) -> None:
        """Apply JSON damage and cooldown values for the current level when available."""
        level_stats = self._level_stats.get(self.upgrade_level, {})
        self.damage = int(level_stats.get("damage", self.damage))
        self.cooldown = float(level_stats.get("cooldown", self.cooldown))

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
        is_piercing: bool = False,
        chain_count: int = DEFAULT_CHAIN_COUNT,
        homing: bool = False,
        aoe_radius: int = DEFAULT_AOE_RADIUS,
        debuffs: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
        owner: str = PLAYER_BULLET_OWNER,
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
        bullet.owner = owner
        bullet.weapon_type = self.weapon_type
        bullet.source_weapon = self.name
        bullet.upgrade_level = self.upgrade_level
        bullet.is_piercing = is_piercing
        bullet.chain_count = chain_count
        bullet.homing = homing
        bullet.tracking_mode = "nearest_enemy" if homing else None
        bullet.aoe_radius = aoe_radius
        bullet.is_aoe = aoe_radius > DEFAULT_AOE_RADIUS
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


def _load_weapon_level_stats(stats_key: str | None) -> WeaponLevelStats:
    """Load per-level weapon stats from data/weapon_stats.json."""
    if stats_key is None:
        return {}

    stats_by_weapon = _load_all_weapon_stats()
    return dict(stats_by_weapon.get(stats_key, {}))


def _load_all_weapon_stats() -> dict[str, WeaponLevelStats]:
    """Load and cache weapon stat tables."""
    global _WEAPON_STATS_CACHE
    if _WEAPON_STATS_CACHE is not None:
        return _WEAPON_STATS_CACHE

    try:
        with WEAPON_STATS_PATH.open("r", encoding="utf-8") as stats_file:
            raw_stats = load(stats_file)
    except (OSError, ValueError, TypeError):
        _WEAPON_STATS_CACHE = {}
        return _WEAPON_STATS_CACHE

    parsed_stats: dict[str, WeaponLevelStats] = {}
    if not isinstance(raw_stats, dict):
        _WEAPON_STATS_CACHE = parsed_stats
        return parsed_stats

    for weapon_key, weapon_data in raw_stats.items():
        if not isinstance(weapon_data, dict):
            continue
        raw_levels = weapon_data.get("levels")
        if not isinstance(raw_levels, dict):
            continue
        levels: WeaponLevelStats = {}
        for level_key, level_stats in raw_levels.items():
            if not isinstance(level_stats, dict):
                continue
            try:
                level = int(level_key)
            except (TypeError, ValueError):
                continue
            levels[level] = {
                stat_key: stat_value
                for stat_key, stat_value in level_stats.items()
                if isinstance(stat_value, int | float)
            }
        parsed_stats[str(weapon_key)] = levels

    _WEAPON_STATS_CACHE = parsed_stats
    return parsed_stats
