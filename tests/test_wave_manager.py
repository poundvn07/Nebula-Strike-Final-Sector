"""Tests for wave spawning and progression behavior."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.game_scene import GameScene
from src.enemies.armored_rooster import ArmoredRooster
from src.enemies.kamikaze import KamikazeChicken
from src.entities.player_ship import PlayerShip
from src.systems.save_manager import SaveManager
from src.systems.wave_manager import MAP_ONE_WAVE_ONE_ENEMY_COUNT, MAP_ONE_WAVE_ONE_SPAWN_Y, WaveManager
from src.utils.constants import SCREEN_HEIGHT
from src.weapons.laser_cannon import LaserCannon


def test_map_one_wave_one_coordinated_shooters() -> None:
    """Map 1 Wave 1 spawns visible upper-screen enemies in a bounded formation."""
    wave_manager = WaveManager(1)
    wave_manager.start_wave(1)
    wave_manager.spawn_pending_now()
    starting_positions = [(enemy.x, enemy.y) for enemy in wave_manager.enemies_alive]
    wave_manager.update(1.0)

    assert len(wave_manager.enemies_alive) == MAP_ONE_WAVE_ONE_ENEMY_COUNT
    assert all(enemy.y >= MAP_ONE_WAVE_ONE_SPAWN_Y for enemy in wave_manager.enemies_alive)
    assert all(getattr(enemy, "coordinated_formation_enemy", False) for enemy in wave_manager.enemies_alive)
    assert any((enemy.x, enemy.y) != starting_positions[index] for index, enemy in enumerate(wave_manager.enemies_alive))
    assert all(0 <= enemy.x <= 800 - enemy.width for enemy in wave_manager.enemies_alive)
    assert all(0 <= enemy.y <= 600 - enemy.height for enemy in wave_manager.enemies_alive)
    assert any(getattr(enemy, "last_attack_bullets", []) for enemy in wave_manager.enemies_alive)


def test_game_scene_countdown_spawns_full_wave_and_blocks_fire(save_path: Path, monkeypatch: object) -> None:
    """Countdown starts with every enemy visible and prevents early player shots."""
    scene = GameScene(PlayerShip(), SaveManager(save_path), {"current_map": 1})
    scene.player.equip_weapon(LaserCannon(), 0)

    assert scene._is_wave_intro_active() is True
    assert scene._wave_intro_phase == "3"
    assert len(scene.wave_manager.enemies_alive) == MAP_ONE_WAVE_ONE_ENEMY_COUNT

    monkeypatch.setattr("pygame.key.get_pressed", lambda: {32: True})
    scene._fire_player_weapons(0.1)

    assert scene.bullets == []


def test_game_scene_countdown_reaches_go_before_combat(save_path: Path) -> None:
    """Wave intro counts 3, 2, 1, GO before unlocking gameplay."""
    scene = GameScene(PlayerShip(), SaveManager(save_path), {"current_map": 1})

    scene._update_wave_intro(1.0)
    assert scene._wave_intro_phase == "2"
    scene._update_wave_intro(1.0)
    assert scene._wave_intro_phase == "1"
    scene._update_wave_intro(1.0)
    assert scene._wave_intro_phase == "GO"
    scene._update_wave_intro(0.5)
    assert scene._is_wave_intro_active() is False


def test_every_wave_has_at_least_two_enemy_rows() -> None:
    """Each non-boss wave has enough enemies to fill two formation rows."""
    wave_manager = WaveManager(1)
    wave_manager.start_wave(2)
    wave_manager.spawn_pending_now()

    assert len(wave_manager.enemies_alive) >= 10


def test_special_enemies_keep_unique_movement_and_missed_dive_despawns() -> None:
    """Kamikaze movement is not replaced by group formation and missed dives clear."""
    wave_manager = WaveManager(1)
    wave_manager.start_wave(2)
    wave_manager.spawn_pending_now()
    kamikaze = next(enemy for enemy in wave_manager.enemies_alive if isinstance(enemy, KamikazeChicken))
    kamikaze.hp = 1
    start_y = kamikaze.y

    wave_manager.update(0.2)

    assert getattr(kamikaze, "coordinated_formation_enemy", False) is False
    assert kamikaze.y > start_y

    kamikaze.x = -100
    kamikaze.y = SCREEN_HEIGHT + 100
    kamikaze.vy = 10.0
    wave_manager.update(0.1)

    assert kamikaze.active is False


def test_armored_rooster_is_not_formation_overridden() -> None:
    """ArmoredRooster keeps its patrol move instead of the shared formation sway."""
    wave_manager = WaveManager(2)
    wave_manager.start_wave(4)
    wave_manager.spawn_pending_now()
    armored = next(enemy for enemy in wave_manager.enemies_alive if isinstance(enemy, ArmoredRooster))

    assert getattr(armored, "coordinated_formation_enemy", False) is False


def test_game_scene_collects_enemy_bullets_once(save_path: Path) -> None:
    """Collected enemy bullets are cleared so they cannot duplicate every frame."""
    scene = GameScene(PlayerShip(), SaveManager(save_path), {"current_map": 1})
    wave_manager = WaveManager(1)
    wave_manager.start_wave(1)
    wave_manager.update(10.0)
    scene.wave_manager = wave_manager

    scene._collect_enemy_attack_bullets()
    first_count = len(scene.bullets)
    scene._collect_enemy_attack_bullets()

    assert first_count > 0
    assert len(scene.bullets) == first_count


def test_player_fires_only_when_space_is_pressed(save_path: Path, monkeypatch: object) -> None:
    """GameScene does not auto-fire unless Space is held."""
    scene = GameScene(PlayerShip(), SaveManager(save_path), {"current_map": 1})
    scene.player.equip_weapon(LaserCannon(), 0)
    scene._wave_intro_phase = ""

    monkeypatch.setattr("pygame.key.get_pressed", lambda: {})
    scene._fire_player_weapons(0.1)
    assert scene.bullets == []

    scene.player.weapon_slots[0].current_cooldown = 0.0
    monkeypatch.setattr("pygame.key.get_pressed", lambda: {32: True})
    scene._fire_player_weapons(0.1)
    assert len(scene.bullets) == 1
