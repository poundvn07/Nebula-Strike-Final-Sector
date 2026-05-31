"""Attack Drone companion implementation."""

from __future__ import annotations

from math import hypot
from typing import TYPE_CHECKING

from src.entities.bullet import Bullet, PLAYER_BULLET_OWNER
from src.entities.drone import DRONE_DEFAULT_SUMMON_COST, Drone, DroneMode
from src.entities.feather_core import FeatherCore
from src.entities.game_object import GameObject

if TYPE_CHECKING:
    from src.entities.player_ship import PlayerShip

ATTACK_DRONE_ORBIT_RADIUS = 80
ATTACK_DRONE_RANGE = 300.0
ATTACK_DRONE_FIRE_INTERVAL_SECONDS = 1.5
ATTACK_DRONE_DAMAGE_MULTIPLIER = 0.60
ATTACK_DRONE_BULLET_SPEED = 340.0
ATTACK_DRONE_BULLET_WIDTH = 6
ATTACK_DRONE_BULLET_HEIGHT = 10
ATTACK_DRONE_UNLOCK_COST = 0
ATTACK_DRONE_UNLOCK_TIER = 1
ZERO_DISTANCE = 0.0
DEFAULT_FOLLOW_DIRECTION = (0.0, -1.0)
DRONE_CENTER_DIVISOR = 2.0


class AttackDrone(Drone):
    """Drone subclass that attacks nearby enemies with player-scaled damage."""

    unlock_cost = ATTACK_DRONE_UNLOCK_COST
    unlock_tier = ATTACK_DRONE_UNLOCK_TIER

    def __init__(self, owner: PlayerShip) -> None:
        """Initialize an always-available combat drone."""
        super().__init__(
            owner=owner,
            orbit_radius=ATTACK_DRONE_ORBIT_RADIUS,
            fc_cost_to_summon=DRONE_DEFAULT_SUMMON_COST,
        )
        self.fire_cooldown = 0.0

    def update_behavior(
        self,
        dt: float,
        player: PlayerShip,
        enemies: list[GameObject],
        fc_items: list[FeatherCore],
    ) -> list[Bullet]:
        """Orbit and fire at a target every 1.5 seconds when ready."""
        self.orbit_around_player(dt)
        self.fire_cooldown = max(0.0, self.fire_cooldown - dt)
        if self.fire_cooldown > 0.0:
            return []

        target = self._select_target(player, enemies)
        if target is None and self.mode is DroneMode.AUTO:
            return []

        damage = self._primary_weapon_damage(player)
        if damage <= 0:
            return []

        direction = self._target_direction(player, target)
        bullet = self._create_attack_bullet(direction, damage)
        self.fire_cooldown = ATTACK_DRONE_FIRE_INTERVAL_SECONDS
        return [bullet]

    def _select_target(self, player: PlayerShip, enemies: list[GameObject]) -> GameObject | None:
        """Return the nearest active enemy in AUTO mode, or None in FOLLOW mode."""
        if self.mode is DroneMode.FOLLOW:
            return None

        active_enemies = [
            enemy
            for enemy in enemies
            if getattr(enemy, "active", True)
            and hasattr(enemy, "is_alive")
            and enemy.is_alive()
            and self._distance_to(enemy) <= ATTACK_DRONE_RANGE
        ]
        if not active_enemies:
            return None

        return min(active_enemies, key=self._distance_to)

    def _target_direction(self, player: PlayerShip, target: GameObject | None) -> tuple[float, float]:
        """Return a normalized AUTO target direction or the player's FOLLOW direction."""
        if target is None:
            get_direction = getattr(player, "_get_fire_direction", None)
            direction = get_direction() if get_direction is not None else DEFAULT_FOLLOW_DIRECTION
        else:
            direction = (
                target.x - (self.x + self.width / DRONE_CENTER_DIVISOR),
                target.y - (self.y + self.height / DRONE_CENTER_DIVISOR),
            )

        dx, dy = direction
        magnitude = hypot(dx, dy)
        if magnitude <= ZERO_DISTANCE:
            return DEFAULT_FOLLOW_DIRECTION
        return dx / magnitude, dy / magnitude

    def _primary_weapon_damage(self, player: PlayerShip) -> float:
        """Return 60 percent of the player's primary weapon damage."""
        primary_weapon = player.weapon_slots[0] if player.weapon_slots else None
        return float(getattr(primary_weapon, "damage", 0.0)) * ATTACK_DRONE_DAMAGE_MULTIPLIER

    def _create_attack_bullet(self, direction: tuple[float, float], damage: float) -> Bullet:
        """Create one player-owned drone bullet."""
        dx, dy = direction
        bullet = Bullet(
            x=self.x + self.width / DRONE_CENTER_DIVISOR,
            y=self.y + self.height / DRONE_CENTER_DIVISOR,
            vx=dx * ATTACK_DRONE_BULLET_SPEED,
            vy=dy * ATTACK_DRONE_BULLET_SPEED,
            damage=damage,
            owner=PLAYER_BULLET_OWNER,
            width=ATTACK_DRONE_BULLET_WIDTH,
            height=ATTACK_DRONE_BULLET_HEIGHT,
        )
        bullet.source_drone = self.__class__.__name__
        return bullet

    def _distance_to(self, target: GameObject) -> float:
        """Return distance from the drone center to a target."""
        dx = target.x - self.x
        dy = target.y - self.y
        return hypot(dx, dy)
