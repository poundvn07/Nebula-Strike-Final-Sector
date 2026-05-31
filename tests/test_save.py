"""Tests for SaveManager round-tripping and map-loss persistence."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.game_scene import GameScene
from src.core.scene_manager import SceneManager
from src.entities.attack_drone import AttackDrone
from src.entities.player_ship import PlayerShip
from src.entities.shield_drone import ShieldDrone
from src.systems.resource_manager import LIFE_PURCHASE_COST, MAX_PURCHASED_LIVES, ResourceManager
from src.systems.save_manager import SaveManager
from src.ui.result_screen import ResultScene
from src.weapons.laser_cannon import LaserCannon
from src.weapons.plasma_spread import PlasmaSpread


def test_save_and_load_roundtrip(save_path: Path) -> None:
    """SaveManager preserves player and map state through JSON."""
    save_manager = SaveManager(save_path)
    player = PlayerShip()
    player.hp = 72
    player.lives = 2
    player.add_fc(90)
    player.score = 12450
    laser = LaserCannon()
    laser.upgrade()
    player.weapon_slots[0] = laser
    player.weapon_slots[1] = PlasmaSpread()
    player.drone_manager.unlocked_drone_types.add(ShieldDrone)
    player.unlocked_drones = player.drone_manager.unlocked_drone_types
    player.drones.append(AttackDrone(player))
    game_state = {
        "current_map": 2,
        "highest_wave_reached": 4,
        "map_unlocked": [True, True, False, False, False],
    }

    assert save_manager.save(player, game_state) is True
    data = save_manager.load()

    assert data is not None
    assert data["ship_hp"] == 72
    assert data["ship_max_hp"] == player.max_hp
    assert data["fc_inventory"] == 90
    assert data["score"] == 12450
    assert data["lives"] == 2
    assert data["current_map"] == 2
    assert data["highest_wave_reached"] == 4
    assert data["weapon_slots"][0] == {"type": "LASER_CANNON", "level": 2}
    assert data["weapon_slots"][1] == {"type": "PLASMA_SPREAD", "level": 1}
    assert data["drones_active"] == [{"type": "ATTACK_DRONE"}]
    assert "SHIELD_DRONE" in data["unlocked_drone_types"]

    restored_player = PlayerShip()
    save_manager.apply_to_player(data, restored_player)

    assert restored_player.hp == 72
    assert restored_player.fc_inventory == 90
    assert restored_player.score == 12450
    assert restored_player.lives == 2
    assert isinstance(restored_player.weapon_slots[0], LaserCannon)
    assert restored_player.weapon_slots[0].upgrade_level == 2
    assert isinstance(restored_player.weapon_slots[1], PlasmaSpread)
    assert any(isinstance(drone, AttackDrone) for drone in restored_player.drones)
    assert ShieldDrone in restored_player.unlocked_drones


def test_load_missing_file(save_path: Path) -> None:
    """Loading a missing save returns None without crashing."""
    assert SaveManager(save_path).load() is None


def test_load_corrupted_file(save_path: Path) -> None:
    """Loading corrupted JSON returns None without crashing."""
    save_path.write_text("{invalid json", encoding="utf-8")

    assert SaveManager(save_path).load() is None


def test_starting_loadout_equips_weapon(save_path: Path) -> None:
    """New Game loadout gives the player a usable starting weapon."""
    player = PlayerShip()

    SaveManager(save_path).apply_starting_loadout(player)
    fired_bullets = player.fire(0.1)

    assert isinstance(player.weapon_slots[0], LaserCannon)
    assert player.weapon_slots[0].upgrade_level == 1
    assert player.weapon_slots[1] is None
    assert len(fired_bullets) == 1


def test_lose_penalty(save_path: Path) -> None:
    """Losing a map reduces FC inventory by exactly 25 percent."""
    save_manager = SaveManager(save_path)
    player = PlayerShip()
    player.add_fc(100)
    scene = GameScene(player, save_manager, {"current_map": 2})

    assert scene.on_map_lose() is True

    assert player.fc_inventory == 75
    assert save_manager.load()["fc_inventory"] == 75


def test_map_unlock(save_path: Path) -> None:
    """Completing map 2 persists map 3 as unlocked while map 4 remains locked."""
    save_manager = SaveManager(save_path)
    player = PlayerShip()
    game_state = {
        "current_map": 3,
        "highest_wave_reached": 1,
        "map_unlocked": [True, True, True, False, False],
    }

    assert save_manager.save(player, game_state) is True
    data = save_manager.load()

    assert data is not None
    assert data["map_unlocked"][2] is True
    assert data["map_unlocked"][3] is False


def test_retry_reactivates_defeated_player(save_path: Path) -> None:
    """Retry should restart from playable HP instead of returning to immediate loss."""
    player = PlayerShip()
    player.hp = 0
    player.active = False
    scene_manager = SceneManager()
    result_scene = ResultScene(
        player,
        scene_manager,
        SaveManager(save_path),
        {"current_map": 1},
        won=False,
    )

    result_scene._retry()

    assert isinstance(scene_manager.current_scene, GameScene)
    assert player.active is True
    assert player.hp == player.max_hp


def test_game_scene_respawns_until_lives_are_empty(save_path: Path) -> None:
    """HP reaching zero consumes lives before the full reset/loss result."""
    player = PlayerShip()
    scene = GameScene(player, SaveManager(save_path), {"current_map": 1})
    player.hp = 0
    player.active = False

    scene._handle_player_defeat()

    assert player.active is True
    assert player.hp == player.max_hp
    assert player.lives == 2
    assert scene._transitioned_to_result is False


def test_game_scene_final_life_resets_run(save_path: Path) -> None:
    """Final death resets saved run state to the starter setup."""
    player = PlayerShip()
    player.lives = 1
    player.add_fc(80)
    player.score = 500
    player.equip_weapon(PlasmaSpread(), 0)
    scene_manager = SceneManager()
    save_manager = SaveManager(save_path)
    scene = GameScene(player, save_manager, {"current_map": 3}, scene_manager=scene_manager)

    scene._handle_player_defeat()
    data = save_manager.load()

    assert data is not None
    assert data["current_map"] == 1
    assert data["score"] == 0
    assert data["fc_inventory"] == 0
    assert data["lives"] == 3
    assert data["weapon_slots"][0] == {"type": "LASER_CANNON", "level": 1}
    assert isinstance(scene_manager.current_scene, ResultScene)


def test_resource_manager_can_purchase_life() -> None:
    """ResourceManager spends FC to buy one life up to the current cap."""
    player = PlayerShip()
    player.add_fc(LIFE_PURCHASE_COST)

    assert ResourceManager().purchase_life(player) is True
    assert player.lives == 4
    assert player.fc_inventory == 0

    player.lives = MAX_PURCHASED_LIVES
    player.add_fc(LIFE_PURCHASE_COST)

    assert ResourceManager().purchase_life(player) is False
    assert player.lives == MAX_PURCHASED_LIVES
