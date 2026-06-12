"""Resource manager for Feather Core spending and Fever Mode tracking."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.entities.drone import Drone
    from src.entities.player_ship import PlayerShip

from src.utils.constants import FINAL_MAP_INDEX, FIRST_MAP_INDEX, MIN_HEALTH
from src.weapons.ice_bolt import IceBolt
from src.weapons.laser_cannon import LaserCannon
from src.weapons.missile_salvo import MissileSalvo
from src.weapons.plasma_spread import PlasmaSpread
from src.weapons.thunder_rail import ThunderRail
from src.weapons.weapon import Weapon

FEVER_STREAK_TRIGGER_COUNT = 10
FEVER_DURATION_SECONDS = 5.0
FEVER_DAMAGE_MULTIPLIER = 1.5
NORMAL_DAMAGE_MULTIPLIER = 1.0
REPAIR_FC_CHUNK = 10
UPGRADE_LEVEL_ONE_COST = 120
UPGRADE_LEVEL_TWO_COST = 260
DRONE_SUMMON_COST = 30
DRONE_UNLOCK_COST = 120
LIFE_PURCHASE_COST = 160
MAX_PURCHASED_LIVES = 5
WEAPON_SHOP_ORDER = ("LASER_CANNON", "PLASMA_SPREAD", "ICE_BOLT", "MISSILE_SALVO", "THUNDER_RAIL")
WEAPON_SHOP_TYPES: dict[str, type[Weapon]] = {
    "LASER_CANNON": LaserCannon,
    "PLASMA_SPREAD": PlasmaSpread,
    "ICE_BOLT": IceBolt,
    "MISSILE_SALVO": MissileSalvo,
    "THUNDER_RAIL": ThunderRail,
}
WEAPON_PURCHASE_COSTS = {
    "LASER_CANNON": 60,
    "PLASMA_SPREAD": 95,
    "ICE_BOLT": 100,
    "MISSILE_SALVO": 130,
    "THUNDER_RAIL": 155,
}
WEAPON_UNLOCK_MAPS = {
    "LASER_CANNON": FIRST_MAP_INDEX,
    "PLASMA_SPREAD": FIRST_MAP_INDEX,
    "ICE_BOLT": 2,
    "MISSILE_SALVO": 3,
    "THUNDER_RAIL": 3,
}
ZERO_TIME = 0.0


class ResourceManager:
    """Tracks Feather Core streaks, Fever Mode, and FC spending interfaces."""

    def __init__(self) -> None:
        """Initialize Fever Mode streak state and timer."""
        self.streak_count = 0
        self.last_hit_time = ZERO_TIME
        self.fever_active = False
        self.fever_timer = ZERO_TIME

    def on_fc_collected(self) -> None:
        """Increment FC pickup streak and reset the time since the last streak event."""
        self.streak_count += 1
        self.last_hit_time = ZERO_TIME
        self.check_fever_trigger()

    def on_player_hit(self) -> None:
        """Break the FC pickup streak after the player takes damage."""
        self.streak_count = 0
        self.last_hit_time = ZERO_TIME

    def check_fever_trigger(self) -> None:
        """Activate Fever Mode once the FC pickup streak reaches 10."""
        if self.streak_count >= FEVER_STREAK_TRIGGER_COUNT and not self.fever_active:
            self.fever_active = True
            self.fever_timer = FEVER_DURATION_SECONDS

    def update(self, dt: float) -> None:
        """Tick Fever Mode and deactivate it when the 5 second duration expires."""
        self.last_hit_time += dt
        if not self.fever_active:
            return

        self.fever_timer = max(ZERO_TIME, self.fever_timer - dt)
        if self.fever_timer <= ZERO_TIME:
            self.fever_active = False

    def get_damage_multiplier(self) -> float:
        """Return the active Fever Mode damage multiplier."""
        return FEVER_DAMAGE_MULTIPLIER if self.fever_active else NORMAL_DAMAGE_MULTIPLIER

    def repair_ship(self, player: PlayerShip, fc_amount: int) -> int:
        """Spend 10 FC per 20 percent HP restored through the PlayerShip repair API."""
        return int(player.repair(fc_amount))

    def upgrade_weapon(self, player: PlayerShip, slot: int, weapon: Weapon | None = None) -> bool:
        """Spend the weapon's configured FC cost, then upgrade the selected weapon."""
        selected_weapon = weapon or player.weapon_slots[slot]
        if selected_weapon is None:
            return False

        upgrade_cost = _get_weapon_upgrade_cost(selected_weapon)
        if upgrade_cost <= 0:
            return False
        if not player.spend_fc(upgrade_cost):
            return False

        upgraded = bool(selected_weapon.upgrade())
        if not upgraded:
            player.add_fc(upgrade_cost)
        return upgraded

    def summon_drone(self, player: PlayerShip, drone_type: type[Drone]) -> Drone | None:
        """Spend FC, instantiate a drone, and add it to the player's drones."""
        summon_method = getattr(player, "summon_drone", None)
        if summon_method is not None:
            return summon_method(drone_type)

        if not player.spend_fc(DRONE_SUMMON_COST):
            return None

        drone = drone_type(player)
        player.drones.append(drone)
        return drone

    def unlock_drone_type(self, player: PlayerShip, drone_type: type[Drone]) -> bool:
        """Spend the drone unlock cost and add the drone type to player.unlocked_drones."""
        unlocked_drones = _ensure_unlocked_drones(player)
        if drone_type in unlocked_drones:
            return True

        unlock_method = getattr(player, "unlock_drone", None)
        if unlock_method is not None:
            unlocked = bool(unlock_method(drone_type))
            if unlocked:
                unlocked_drones.add(drone_type)
            return unlocked

        if not player.spend_fc(DRONE_UNLOCK_COST):
            return False

        unlocked_drones.add(drone_type)
        return True

    def purchase_life(self, player: PlayerShip) -> bool:
        """Spend FC to buy one extra life before a map starts."""
        current_lives = int(getattr(player, "lives", 0))
        if current_lives >= MAX_PURCHASED_LIVES:
            return False
        if not player.spend_fc(LIFE_PURCHASE_COST):
            return False

        player.lives = current_lives + 1
        return True

    def get_weapon_shop_items(self, current_map: int) -> list[dict[str, object]]:
        """Return weapon shop items with map-based unlock metadata."""
        return get_weapon_shop_items(current_map)

    def purchase_weapon(
        self,
        player: PlayerShip,
        weapon_key: str,
        slot_index: int,
        current_map: int = FINAL_MAP_INDEX,
    ) -> bool:
        """Buy a weapon and equip it into the selected player slot."""
        weapon_class = WEAPON_SHOP_TYPES.get(weapon_key)
        if weapon_class is None:
            return False
        if slot_index < MIN_HEALTH or slot_index >= len(player.weapon_slots):
            return False
        if current_map < WEAPON_UNLOCK_MAPS.get(weapon_key, FINAL_MAP_INDEX):
            return False

        existing_weapon = player.weapon_slots[slot_index]
        if existing_weapon is not None and isinstance(existing_weapon, weapon_class):
            return False

        cost = WEAPON_PURCHASE_COSTS[weapon_key]
        if not player.spend_fc(cost):
            return False

        player.equip_weapon(weapon_class(), slot_index)
        return True


def _get_weapon_upgrade_cost(weapon: Weapon) -> int:
    """Return the weapon's next upgrade cost."""
    get_upgrade_cost = getattr(weapon, "get_upgrade_cost", None)
    if get_upgrade_cost is not None:
        return int(get_upgrade_cost())

    upgrade_level = int(getattr(weapon, "upgrade_level", 1))
    if upgrade_level == 1:
        return UPGRADE_LEVEL_ONE_COST
    if upgrade_level == 2:
        return UPGRADE_LEVEL_TWO_COST
    return 0


def _ensure_unlocked_drones(player: PlayerShip) -> set[type[Drone]]:
    """Return player.unlocked_drones, creating it when needed."""
    if not hasattr(player, "unlocked_drones"):
        player.unlocked_drones = set()
    return player.unlocked_drones


def get_weapon_shop_items(current_map: int) -> list[dict[str, object]]:
    """Build the map-gated weapon shop catalog for the preparation scene."""
    items: list[dict[str, object]] = []
    for weapon_key in WEAPON_SHOP_ORDER:
        weapon_class = WEAPON_SHOP_TYPES[weapon_key]
        unlock_map = WEAPON_UNLOCK_MAPS[weapon_key]
        prototype = weapon_class()
        items.append(
            {
                "key": weapon_key,
                "name": prototype.name,
                "cost": WEAPON_PURCHASE_COSTS[weapon_key],
                "unlock_map": unlock_map,
                "unlocked": current_map >= unlock_map,
            }
        )
    return items
