"""Support Drone companion implementation."""

from __future__ import annotations

from math import hypot
from typing import TYPE_CHECKING

from src.entities.drone import DRONE_DEFAULT_SUMMON_COST, Drone
from src.entities.feather_core import FeatherCore
from src.entities.game_object import GameObject

if TYPE_CHECKING:
    from src.entities.player_ship import PlayerShip

SUPPORT_DRONE_ORBIT_RADIUS = 100
SUPPORT_DRONE_UNLOCK_COST = 40
SUPPORT_DRONE_UNLOCK_TIER = 2
SUPPORT_DRONE_PLAYER_PICKUP_RADIUS = 120.0
SUPPORT_DRONE_MOVE_SPEED = 240.0
SUPPORT_DRONE_COLLECT_DISTANCE = 14.0
ZERO_DISTANCE = 0.0


class SupportDrone(Drone):
    """Drone subclass that retrieves distant Feather Core pickups for the player."""

    unlock_cost = SUPPORT_DRONE_UNLOCK_COST
    unlock_tier = SUPPORT_DRONE_UNLOCK_TIER

    def __init__(self, owner: PlayerShip) -> None:
        """Initialize a support drone that can collect unsafe FC drops."""
        super().__init__(
            owner=owner,
            orbit_radius=SUPPORT_DRONE_ORBIT_RADIUS,
            fc_cost_to_summon=DRONE_DEFAULT_SUMMON_COST,
        )
        self.target_fc: FeatherCore | None = None

    def update_behavior(
        self,
        dt: float,
        player: PlayerShip,
        enemies: list[GameObject],
        fc_items: list[FeatherCore],
    ) -> list[object]:
        """Move toward the nearest distant FC pickup and collect it for the player."""
        self.target_fc = self._nearest_distant_fc(player, fc_items)
        if self.target_fc is None:
            self.orbit_around_player(dt)
            return []

        self._move_toward_fc(dt, self.target_fc)
        if _distance(self, self.target_fc) <= SUPPORT_DRONE_COLLECT_DISTANCE:
            player.add_fc(self.target_fc.collect())
            self.target_fc = None
        return []

    def _nearest_distant_fc(
        self,
        player: PlayerShip,
        fc_items: list[FeatherCore],
    ) -> FeatherCore | None:
        """Return the nearest active FC outside the player's pickup radius."""
        candidates = [
            fc_item
            for fc_item in fc_items
            if getattr(fc_item, "active", True)
            and not getattr(fc_item, "collected", False)
            and _distance(player, fc_item) > SUPPORT_DRONE_PLAYER_PICKUP_RADIUS
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda fc_item: _distance(self, fc_item))

    def _move_toward_fc(self, dt: float, fc_item: FeatherCore) -> None:
        """Move the drone toward a target FC pickup."""
        dx = fc_item.x - self.x
        dy = fc_item.y - self.y
        distance = hypot(dx, dy)
        if distance <= ZERO_DISTANCE:
            return

        travel = min(distance, SUPPORT_DRONE_MOVE_SPEED * dt)
        self.x += dx / distance * travel
        self.y += dy / distance * travel


def _distance(source: object, target: object) -> float:
    """Return Euclidean distance between two objects with x/y coordinates."""
    dx = float(getattr(target, "x", 0.0)) - float(getattr(source, "x", 0.0))
    dy = float(getattr(target, "y", 0.0)) - float(getattr(source, "y", 0.0))
    return hypot(dx, dy)
