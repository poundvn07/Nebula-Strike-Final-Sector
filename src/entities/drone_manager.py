"""Drone manager for PlayerShip companion composition."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.entities.bullet import Bullet
from src.entities.drone import Drone, DroneMode
from src.entities.shield_drone import ShieldDrone
from src.utils.constants import MAX_ACTIVE_DRONES

if TYPE_CHECKING:
    from src.enemies.enemy import Enemy
    from src.entities.feather_core import FeatherCore
    from src.entities.player_ship import PlayerShip

DRONE_SUMMON_FC_COST = 30


class DroneManager:
    """Composed helper that manages PlayerShip drones, modes, unlocks, and summoning."""

    def __init__(self, owner: PlayerShip, drones: list[Drone] | None = None) -> None:
        """Initialize the manager with up to three existing drones."""
        self.owner = owner
        self.mode = DroneMode.AUTO
        self.drones: list[Drone] = list(drones or [])[:MAX_ACTIVE_DRONES]
        self.unlocked_drone_types: set[type[Drone]] = set()
        for drone in self.drones:
            drone.owner = owner
            drone.set_mode(self.mode)
            self.unlocked_drone_types.add(type(drone))

    def update(
        self,
        dt: float,
        enemies: list[Enemy],
        fc_items: list[FeatherCore],
        enemy_bullets: list[Bullet] | None = None,
    ) -> list[Bullet]:
        """Update active drones and return player-owned bullets emitted by them."""
        emitted_bullets: list[Bullet] = []
        for drone in self._active_drones():
            drone.set_mode(self.mode)
            if isinstance(drone, ShieldDrone):
                drone.track_enemy_bullets(enemy_bullets or [])

            emitted = drone.update_behavior(dt, self.owner, enemies, fc_items)
            emitted_bullets.extend(item for item in emitted if isinstance(item, Bullet))

        self.drones = self._active_drones()
        return emitted_bullets

    def summon_drone(self, drone_type: type[Drone]) -> Drone | None:
        """Spend FC to summon one drone when capacity and unlock state allow it."""
        if len(self._active_drones()) >= MAX_ACTIVE_DRONES:
            return None
        if not self.is_unlocked(drone_type):
            return None
        if not self.owner.spend_fc(DRONE_SUMMON_FC_COST):
            return None

        drone = drone_type(self.owner)
        drone.set_mode(self.mode)
        self.drones.append(drone)
        return drone

    def unlock_drone(self, drone_type: type[Drone]) -> bool:
        """Spend the drone unlock cost once so this manager can summon that drone type."""
        if self.is_unlocked(drone_type):
            return True

        unlock_cost = int(getattr(drone_type, "unlock_cost", 0))
        if unlock_cost > 0 and not self.owner.spend_fc(unlock_cost):
            return False

        self.unlocked_drone_types.add(drone_type)
        return True

    def is_unlocked(self, drone_type: type[Drone]) -> bool:
        """Return whether a drone type is currently unlocked for summoning."""
        return int(getattr(drone_type, "unlock_cost", 0)) == 0 or drone_type in self.unlocked_drone_types

    def toggle_mode(self) -> DroneMode:
        """Toggle all drones between AUTO and FOLLOW mode."""
        self.mode = DroneMode.FOLLOW if self.mode is DroneMode.AUTO else DroneMode.AUTO
        for drone in self._active_drones():
            drone.set_mode(self.mode)
        return self.mode

    def _active_drones(self) -> list[Drone]:
        """Return non-destroyed active drones."""
        return [drone for drone in self.drones if not drone.is_destroyed and getattr(drone, "active", True)]
