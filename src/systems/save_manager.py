"""JSON save manager for complete Nebula Strike game state."""

from __future__ import annotations

from json import JSONDecodeError, dump, load
from pathlib import Path
from typing import Any

from src.entities.drone import Drone
from src.entities.player_ship import PLAYER_WEAPON_SLOT_COUNT, PlayerShip
from src.entities.support_drone import SupportDrone
from src.utils.constants import FIRST_MAP_INDEX, MAP_COUNT, MIN_HEALTH
from src.weapons.laser_cannon import LaserCannon
from src.weapons.missile_salvo import MissileSalvo
from src.weapons.plasma_spread import PlasmaSpread
from src.weapons.weapon import MIN_WEAPON_LEVEL, Weapon

SAVE_PATH = Path(__file__).resolve().parents[2] / "data" / "save_state.json"
WEAPON_STATS_PATH = Path(__file__).resolve().parents[2] / "data" / "weapon_stats.json"
DEFAULT_HIGHEST_WAVE_REACHED = 1
DEFAULT_SCORE = 0
DEFAULT_FC_INVENTORY = 0
DEFAULT_LIVES = 3
DEFAULT_MAP_UNLOCKED = [True, False, False, False, False]
SHIP_FULL_HP_PERCENT = 100.0
WEAPON_SLOT_COUNT = PLAYER_WEAPON_SLOT_COUNT
DEFAULT_STARTING_LOADOUT = {
    "weapon_slots": [{"type": "LASER_CANNON", "level": MIN_WEAPON_LEVEL}, None, None],
    "special_slot": None,
    "active_weapon_slot": 0,
}

WEAPON_TYPES: dict[str, type[Weapon]] = {
    "LASER_CANNON": LaserCannon,
    "PLASMA_SPREAD": PlasmaSpread,
    "MISSILE_SALVO": MissileSalvo,
}
DRONE_TYPES: dict[str, type[Drone]] = {
    "SUPPORT_DRONE": SupportDrone,
}
WEAPON_TYPE_NAMES = {weapon_class: type_name for type_name, weapon_class in WEAPON_TYPES.items()}
DRONE_TYPE_NAMES = {drone_class: type_name for type_name, drone_class in DRONE_TYPES.items()}


class SaveManager:
    """Serializes and restores player, progress, loadout, drone, and map state."""

    def __init__(self, save_path: Path = SAVE_PATH) -> None:
        """Initialize the manager with the save file path."""
        self.save_path = save_path

    def save(self, player: PlayerShip, game_state: dict) -> bool:
        """Serialize complete game state to JSON, returning False if the write fails."""
        data = self._build_save_data(player, game_state)
        try:
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            with self.save_path.open("w", encoding="utf-8") as save_file:
                dump(data, save_file, indent=2)
        except OSError:
            return False
        return True

    def load(self) -> dict | None:
        """Read save JSON, returning None when missing or corrupted."""
        try:
            with self.save_path.open("r", encoding="utf-8") as save_file:
                return dict(load(save_file))
        except (FileNotFoundError, JSONDecodeError, OSError, TypeError):
            return None

    def apply_to_player(self, data: dict, player: PlayerShip) -> None:
        """Restore saved ship, weapon, drone, score, and FC state onto a PlayerShip."""
        player.hp = int(data.get("ship_hp", player.hp))
        player.max_hp = int(data.get("ship_max_hp", player.max_hp))
        player._fc_inventory = int(data.get("fc_inventory", DEFAULT_FC_INVENTORY))
        player.score = int(data.get("score", DEFAULT_SCORE))
        player.lives = int(data.get("lives", DEFAULT_LIVES))

        weapon_slots = list(data.get("weapon_slots", []))[:WEAPON_SLOT_COUNT]
        player.weapon_slots = [
            _deserialize_weapon(weapon_data)
            for weapon_data in weapon_slots
        ]
        while len(player.weapon_slots) < WEAPON_SLOT_COUNT:
            player.weapon_slots.append(None)

        player.special_slot = _deserialize_weapon(data.get("special_slot"))
        player.select_weapon_slot(_clamp_slot_index(data.get("active_weapon_slot", 0)))
        player.get_active_combo()

        unlocked_drone_types = {
            drone_type
            for drone_name in data.get("unlocked_drone_types", [])
            if (drone_type := DRONE_TYPES.get(str(drone_name))) is not None
        }
        player.drone_manager.unlocked_drone_types = set(unlocked_drone_types)
        player.unlocked_drones = player.drone_manager.unlocked_drone_types

        player.drone_manager.drones = []
        for drone_data in data.get("drones_active", []):
            drone = _deserialize_drone(drone_data, player)
            if drone is not None:
                player.drone_manager.drones.append(drone)
        player.drones = player.drone_manager.drones

    def apply_starting_loadout(self, player: PlayerShip) -> None:
        """Equip the configured New Game starter weapons onto a PlayerShip."""
        loadout = _load_starting_loadout()
        weapon_slots = list(loadout.get("weapon_slots", DEFAULT_STARTING_LOADOUT["weapon_slots"]))[:WEAPON_SLOT_COUNT]
        while len(weapon_slots) < WEAPON_SLOT_COUNT:
            weapon_slots.append(None)

        for slot_index, weapon_data in enumerate(weapon_slots):
            player.equip_weapon(_deserialize_weapon(weapon_data), slot_index)
        player.special_slot = _deserialize_weapon(loadout.get("special_slot"))
        player.select_weapon_slot(_clamp_slot_index(loadout.get("active_weapon_slot", 0)))

    def delete_save(self) -> None:
        """Remove the save file for the New Game option."""
        try:
            self.save_path.unlink()
        except FileNotFoundError:
            pass

    def get_save_summary(self) -> dict:
        """Return compact save metadata for the main menu Continue screen."""
        data = self.load()
        if data is None:
            return {}

        ship_hp = int(data.get("ship_hp", MIN_HEALTH))
        ship_max_hp = int(data.get("ship_max_hp", MIN_HEALTH))
        hp_percent = (
            ship_hp / ship_max_hp * SHIP_FULL_HP_PERCENT
            if ship_max_hp > MIN_HEALTH
            else 0.0
        )
        return {
            "current_map": int(data.get("current_map", FIRST_MAP_INDEX)),
            "score": int(data.get("score", DEFAULT_SCORE)),
            "fc_inventory": int(data.get("fc_inventory", DEFAULT_FC_INVENTORY)),
            "ship_hp_percent": hp_percent,
        }

    def _build_save_data(self, player: PlayerShip, game_state: dict) -> dict[str, Any]:
        """Build the complete JSON-safe save schema."""
        return {
            "ship_hp": int(player.hp),
            "ship_max_hp": int(player.max_hp),
            "fc_inventory": int(player.fc_inventory),
            "score": int(player.score),
            "lives": int(getattr(player, "lives", DEFAULT_LIVES)),
            "current_map": int(game_state.get("current_map", FIRST_MAP_INDEX)),
            "highest_wave_reached": int(
                game_state.get("highest_wave_reached", DEFAULT_HIGHEST_WAVE_REACHED)
            ),
            "weapon_slots": [_serialize_weapon(weapon) for weapon in player.weapon_slots[:WEAPON_SLOT_COUNT]],
            "special_slot": _serialize_weapon(player.special_slot),
            "active_weapon_slot": _clamp_slot_index(getattr(player, "active_weapon_slot", 0)),
            "drones_active": [_serialize_drone(drone) for drone in player.drones],
            "unlocked_drone_types": [
                _drone_type_name(drone_type)
                for drone_type in sorted(
                    player.unlocked_drones,
                    key=lambda drone_class: _drone_type_name(drone_class),
                )
                if _drone_type_name(drone_type) is not None
            ],
            "map_unlocked": _normalize_map_unlocked(game_state.get("map_unlocked")),
        }


def _serialize_weapon(weapon: Weapon | None) -> dict[str, object] | None:
    """Return JSON-safe weapon slot data."""
    if weapon is None:
        return None

    type_name = _weapon_type_name(type(weapon))
    if type_name is None:
        return None
    return {
        "type": type_name,
        "level": int(getattr(weapon, "upgrade_level", MIN_WEAPON_LEVEL)),
    }


def _deserialize_weapon(data: object) -> Weapon | None:
    """Rebuild a weapon object from saved slot data."""
    if not isinstance(data, dict):
        return None

    weapon_class = WEAPON_TYPES.get(str(data.get("type")))
    if weapon_class is None:
        return None

    weapon = weapon_class()
    target_level = max(MIN_WEAPON_LEVEL, int(data.get("level", MIN_WEAPON_LEVEL)))
    while weapon.upgrade_level < target_level:
        if not weapon.upgrade():
            break
    return weapon


def _load_starting_loadout() -> dict[str, object]:
    """Read the New Game loadout from weapon_stats.json, falling back to Laser Cannon."""
    try:
        with WEAPON_STATS_PATH.open("r", encoding="utf-8") as stats_file:
            stats = load(stats_file)
    except (FileNotFoundError, JSONDecodeError, OSError, TypeError):
        return dict(DEFAULT_STARTING_LOADOUT)

    loadout = stats.get("starting_loadout") if isinstance(stats, dict) else None
    if not isinstance(loadout, dict):
        return dict(DEFAULT_STARTING_LOADOUT)
    return dict(loadout)


def _serialize_drone(drone: Drone) -> dict[str, object]:
    """Return JSON-safe active drone data."""
    return {"type": _drone_type_name(type(drone))}


def _deserialize_drone(data: object, player: PlayerShip) -> Drone | None:
    """Rebuild an active drone object from saved data."""
    if not isinstance(data, dict):
        return None

    drone_class = DRONE_TYPES.get(str(data.get("type")))
    if drone_class is None:
        return None
    return drone_class(player)


def _weapon_type_name(weapon_class: type[Weapon]) -> str | None:
    """Return the save type string for a weapon class."""
    return WEAPON_TYPE_NAMES.get(weapon_class)


def _drone_type_name(drone_class: type[Drone]) -> str | None:
    """Return the save type string for a drone class."""
    return DRONE_TYPE_NAMES.get(drone_class)


def _normalize_map_unlocked(map_unlocked: object) -> list[bool]:
    """Return a five-map unlock list with map 1 unlocked by default."""
    if not isinstance(map_unlocked, list):
        return list(DEFAULT_MAP_UNLOCKED)

    normalized = [bool(value) for value in map_unlocked[:MAP_COUNT]]
    while len(normalized) < MAP_COUNT:
        normalized.append(False)
    normalized[0] = True
    return normalized


def _clamp_slot_index(value: object) -> int:
    """Return a valid weapon slot index for saved or configured data."""
    try:
        slot_index = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(WEAPON_SLOT_COUNT - 1, slot_index))
