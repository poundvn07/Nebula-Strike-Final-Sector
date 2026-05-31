"""Bomb Drone companion implementation."""

from __future__ import annotations

from math import hypot
from typing import TYPE_CHECKING

from src.entities.bullet import Bullet, PLAYER_BULLET_OWNER
from src.entities.drone import DRONE_DEFAULT_SUMMON_COST, Drone
from src.entities.feather_core import FeatherCore
from src.entities.game_object import GameObject

if TYPE_CHECKING:
    from src.entities.player_ship import PlayerShip

BOMB_DRONE_ORBIT_RADIUS = 90
BOMB_DRONE_UNLOCK_COST = 40
BOMB_DRONE_UNLOCK_TIER = 3
BOMB_DRONE_CLUSTER_RADIUS = 150.0
BOMB_DRONE_CLUSTER_SIZE = 4
BOMB_DRONE_AOE_RADIUS = 120
BOMB_DRONE_COOLDOWN_SECONDS = 15.0
BOMB_DRONE_EGG_BOMB_DAMAGE = 35
BOMB_DRONE_BULLET_SIZE = 24
BOMB_DRONE_ZERO_VELOCITY = 0.0


class BombDrone(Drone):
    """Drone subclass that triggers an AOE Egg Bomb against dense enemy clusters."""

    unlock_cost = BOMB_DRONE_UNLOCK_COST
    unlock_tier = BOMB_DRONE_UNLOCK_TIER

    def __init__(self, owner: PlayerShip) -> None:
        """Initialize a bomb drone with a 15 second Egg Bomb cooldown."""
        super().__init__(
            owner=owner,
            orbit_radius=BOMB_DRONE_ORBIT_RADIUS,
            fc_cost_to_summon=DRONE_DEFAULT_SUMMON_COST,
        )
        self.bomb_cooldown = 0.0

    def update_behavior(
        self,
        dt: float,
        player: PlayerShip,
        enemies: list[GameObject],
        fc_items: list[FeatherCore],
    ) -> list[Bullet]:
        """Orbit and trigger Egg Bomb when four enemies cluster together."""
        self.orbit_around_player(dt)
        self.bomb_cooldown = max(0.0, self.bomb_cooldown - dt)
        if self.bomb_cooldown > 0.0:
            return []

        cluster = self._find_enemy_cluster(enemies)
        if not cluster:
            return []

        center_x, center_y = _cluster_center(cluster)
        self.bomb_cooldown = BOMB_DRONE_COOLDOWN_SECONDS
        return [self._create_egg_bomb(center_x, center_y)]

    def _find_enemy_cluster(self, enemies: list[GameObject]) -> list[GameObject]:
        """Return the first cluster with four active enemies inside 150 pixels."""
        active_enemies = [
            enemy
            for enemy in enemies
            if getattr(enemy, "active", True)
            and hasattr(enemy, "is_alive")
            and enemy.is_alive()
        ]
        for seed_enemy in active_enemies:
            cluster = [
                enemy
                for enemy in active_enemies
                if _distance(seed_enemy, enemy) <= BOMB_DRONE_CLUSTER_RADIUS
            ]
            if len(cluster) >= BOMB_DRONE_CLUSTER_SIZE:
                return cluster[:BOMB_DRONE_CLUSTER_SIZE]
        return []

    def _create_egg_bomb(self, center_x: float, center_y: float) -> Bullet:
        """Create a player-owned AOE bullet marker for the Egg Bomb."""
        bullet = Bullet(
            x=center_x,
            y=center_y,
            vx=BOMB_DRONE_ZERO_VELOCITY,
            vy=BOMB_DRONE_ZERO_VELOCITY,
            damage=BOMB_DRONE_EGG_BOMB_DAMAGE,
            owner=PLAYER_BULLET_OWNER,
            is_piercing=True,
            is_aoe=True,
            aoe_radius=BOMB_DRONE_AOE_RADIUS,
            width=BOMB_DRONE_BULLET_SIZE,
            height=BOMB_DRONE_BULLET_SIZE,
        )
        bullet.source_drone = self.__class__.__name__
        bullet.metadata = {"pattern": "egg_bomb", "aoe_radius": BOMB_DRONE_AOE_RADIUS}
        return bullet


def _distance(source: object, target: object) -> float:
    """Return Euclidean distance between two objects with x/y coordinates."""
    dx = float(getattr(target, "x", 0.0)) - float(getattr(source, "x", 0.0))
    dy = float(getattr(target, "y", 0.0)) - float(getattr(source, "y", 0.0))
    return hypot(dx, dy)


def _cluster_center(enemies: list[GameObject]) -> tuple[float, float]:
    """Return the average x/y center for an enemy cluster."""
    return (
        sum(enemy.x for enemy in enemies) / len(enemies),
        sum(enemy.y for enemy in enemies) / len(enemies),
    )
