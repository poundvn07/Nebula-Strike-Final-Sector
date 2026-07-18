"""Tests for wave spawning and progression behavior."""

from __future__ import annotations

import json
import sys
from math import pi
from types import SimpleNamespace
from pathlib import Path

import pygame

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.game_scene import (
    CONTROLS_BACK_RECT,
    PAUSE_CONTROLS_RECT,
    PAUSE_RESUME_RECT,
    GameScene,
)
from src.enemies.armored_rooster import ArmoredRooster
from src.enemies.kamikaze import KamikazeChicken
from src.enemies.space_rooster import SpaceRooster
from src.entities.player_ship import PlayerShip
from src.systems.save_manager import SaveManager
from src.systems.wave_manager import (
    FORMATIONS_PER_ROW,
    MAP_ONE_WAVE_ONE_ENEMY_COUNT,
    MAP_ONE_WAVE_ONE_SPAWN_Y,
    WaveManager,
)
from src.utils.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from src.weapons.laser_cannon import LaserCannon
from src.weapons.plasma_spread import PlasmaSpread


def test_map_one_wave_one_coordinated_shooters() -> None:
    """Map 1 Wave 1 spawns visible upper-screen enemies in a bounded formation."""
    wave_manager = WaveManager(1)
    wave_manager.start_wave(1)
    wave_manager.spawn_pending_now()
    starting_positions = [(enemy.x, enemy.y) for enemy in wave_manager.enemies_alive]
    wave_manager.update(1.0)

    assert len(wave_manager.enemies_alive) == MAP_ONE_WAVE_ONE_ENEMY_COUNT
    assert len(wave_manager.enemies_alive) % FORMATIONS_PER_ROW == 0
    assert all(enemy.y >= MAP_ONE_WAVE_ONE_SPAWN_Y for enemy in wave_manager.enemies_alive)
    assert all(getattr(enemy, "coordinated_formation_enemy", False) for enemy in wave_manager.enemies_alive)
    assert any((enemy.x, enemy.y) != starting_positions[index] for index, enemy in enumerate(wave_manager.enemies_alive))
    assert all(0 <= enemy.x <= SCREEN_WIDTH - enemy.width for enemy in wave_manager.enemies_alive)
    assert all(0 <= enemy.y <= SCREEN_HEIGHT - enemy.height for enemy in wave_manager.enemies_alive)
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

    assert len(wave_manager.enemies_alive) >= FORMATIONS_PER_ROW * 2
    assert len(wave_manager.enemies_alive) % FORMATIONS_PER_ROW == 0


def test_higher_maps_use_distinct_json_selected_layouts() -> None:
    """Map 4 demonstrates chevron, wave, staggered, and diamond formations."""
    wave_manager = WaveManager(4)
    layouts: list[str] = []
    position_sets: list[list[tuple[float, float]]] = []
    for wave_number in range(1, 5):
        wave_manager.start_wave(wave_number)
        layouts.append(str(wave_manager.active_formation["layout"]))
        position_sets.append([
            (float(entry["x"]), float(entry["y"]))
            for entry in wave_manager.spawn_queue
        ])

    assert layouts == ["chevron", "wave", "staggered", "diamond"]
    assert len({position[1] for position in position_sets[0][:FORMATIONS_PER_ROW]}) > 1
    assert len({position[1] for position in position_sets[1][:FORMATIONS_PER_ROW]}) > 1
    assert position_sets[2][FORMATIONS_PER_ROW][0] != position_sets[2][0][0]
    assert position_sets[3][1][0] == position_sets[3][0][0]
    assert position_sets[3][2][1] == position_sets[3][0][1]


def test_enemy_formation_can_use_json_positions(tmp_path: Path) -> None:
    """A custom JSON file controls enemy types, count, and exact spawn positions."""
    config = {
        "formations": {
            "custom": {
                "columns": 2,
                "origin": [200, 80],
                "spacing": [50, 30],
                "movement": "grid",
                "spawn_delay": 0.25,
                "spawn_stagger": 0.5,
                "spawn_all_on_intro": False,
                "coordinated_types": ["chicken_grunt", "egg_bomber"],
                "sway": {"x": 0, "y": 0, "x_rate": 0, "y_rate": 0},
                "bounds": {"top": 0, "bottom_ratio": 1, "left": 0, "right": 0},
            }
        },
        "maps": {
            "map_1": {
                "waves": [{
                    "formation": "custom",
                    "enemies": ["egg_bomber", "chicken_grunt"],
                    "positions": [[111, 77], [333, 155]],
                    "attack_cooldown_scale": 1.0,
                }]
            }
        },
    }
    config_path = tmp_path / "custom_waves.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    wave_manager = WaveManager(1, config_path)
    wave_manager.start_wave(1)

    assert wave_manager.should_spawn_all_on_intro() is False
    assert [entry["enemy_type"] for entry in wave_manager.spawn_queue] == ["egg_bomber", "chicken_grunt"]
    assert [(entry["x"], entry["y"]) for entry in wave_manager.spawn_queue] == [(111.0, 77.0), (333.0, 155.0)]
    assert [entry["timer"] for entry in wave_manager.spawn_queue] == [0.25, 0.75]


def test_group_sway_preserves_spacing_at_screen_bounds() -> None:
    """Boundary clamping moves the whole formation and cannot stack its rows."""
    wave_manager = WaveManager(1)
    wave_manager.start_wave(1)
    wave_manager.spawn_pending_now()
    enemies = wave_manager.enemies_alive
    first_row_enemy = enemies[0]
    second_row_enemy = enemies[FORMATIONS_PER_ROW]
    original_row_gap = second_row_enemy.y - first_row_enemy.y
    wave_manager.active_formation["sway"] = {"x": 0, "y": 200, "x_rate": 0, "y_rate": 1}
    wave_manager.formation_time = 3 * pi / 2

    wave_manager._move_enemies_in_coordinated_formation(enemies)

    assert second_row_enemy.y - first_row_enemy.y == original_row_gap
    first_rect = pygame.Rect(first_row_enemy.x, first_row_enemy.y, first_row_enemy.width, first_row_enemy.height)
    second_rect = pygame.Rect(second_row_enemy.x, second_row_enemy.y, second_row_enemy.width, second_row_enemy.height)
    assert first_rect.colliderect(second_rect) is False


def test_group_sway_keeps_every_formation_sprite_separate() -> None:
    """Extreme sway preserves a visible gap between every coordinated sprite."""
    wave_manager = WaveManager(1)
    wave_manager.start_wave(1)
    wave_manager.spawn_pending_now()
    enemies = wave_manager.enemies_alive
    wave_manager.active_formation["sway"] = {"x": 500, "y": 500, "x_rate": 1, "y_rate": 1}

    for formation_time in (pi / 2, 3 * pi / 2):
        wave_manager.formation_time = formation_time
        wave_manager._move_enemies_in_coordinated_formation(enemies)
        for enemy_index, first_enemy in enumerate(enemies):
            first_rect = first_enemy.get_rect()
            for second_enemy in enemies[enemy_index + 1:]:
                assert first_rect.colliderect(second_enemy.get_rect()) is False


def test_overlapping_json_anchors_are_separated_before_sway(tmp_path: Path) -> None:
    """Unsafe custom positions cannot make coordinated sprites render stacked."""
    config = {
        "formations": {
            "tight": {
                "columns": 2,
                "origin": [300, 100],
                "spacing": [1, 1],
                "movement": "grid",
                "spawn_delay": 0,
                "spawn_stagger": 0,
                "spawn_all_on_intro": True,
                "coordinated_types": ["chicken_grunt", "egg_bomber"],
                "sway": {"x": 80, "y": 80, "x_rate": 1, "y_rate": 1},
                "bounds": {"top": 0, "bottom_ratio": 1, "left": 0, "right": 0},
            }
        },
        "maps": {
            "map_1": {
                "waves": [{
                    "formation": "tight",
                    "enemy_count": 4,
                    "enemy_pattern": ["chicken_grunt", "egg_bomber"],
                }]
            }
        },
    }
    config_path = tmp_path / "overlapping_waves.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    wave_manager = WaveManager(1, config_path)
    wave_manager.start_wave(1)
    wave_manager.spawn_pending_now()

    for enemy_index, first_enemy in enumerate(wave_manager.enemies_alive):
        first_rect = first_enemy.get_rect()
        for second_enemy in wave_manager.enemies_alive[enemy_index + 1:]:
            assert first_rect.colliderect(second_enemy.get_rect()) is False


def test_mixed_enemy_movement_does_not_stack_with_sway_group() -> None:
    """Specialists remain separate from coordinated enemies throughout movement."""
    wave_manager = WaveManager(3)
    wave_manager.start_wave(4)
    wave_manager.spawn_pending_now()

    for _ in range(600):
        wave_manager.update(1 / 60)
        regular_enemies = [
            enemy
            for enemy in wave_manager.enemies_alive
            if getattr(enemy, "active", False)
            and not getattr(enemy, "health_bar_visible", False)
        ]
        for enemy_index, first_enemy in enumerate(regular_enemies):
            first_rect = first_enemy.get_rect()
            for second_enemy in regular_enemies[enemy_index + 1:]:
                assert first_rect.colliderect(second_enemy.get_rect()) is False


def test_boss_minions_join_without_stacking_on_formation() -> None:
    """Boss summons are placed outside occupied regular-enemy sprite bounds."""
    wave_manager = WaveManager(4)
    final_wave = int(wave_manager.map_config["waves"])
    wave_manager.start_wave(final_wave)
    wave_manager.spawn_pending_now()
    wave_manager.update(1 / 60)
    regular_enemies = [
        enemy
        for enemy in wave_manager.enemies_alive
        if getattr(enemy, "active", False)
        and not getattr(enemy, "health_bar_visible", False)
    ]

    for enemy_index, first_enemy in enumerate(regular_enemies):
        first_rect = first_enemy.get_rect()
        for second_enemy in regular_enemies[enemy_index + 1:]:
            assert first_rect.colliderect(second_enemy.get_rect()) is False


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


def test_boss_uses_configured_fc_drop() -> None:
    """Boss FC drops follow enemy_stats.json instead of class fallback values."""
    wave_manager = WaveManager(1)
    wave_manager.start_wave(5)
    wave_manager.spawn_pending_now()
    boss = next(enemy for enemy in wave_manager.enemies_alive if isinstance(enemy, SpaceRooster))

    drops = boss.on_death()

    assert boss.fc_drop_min == 25
    assert boss.fc_drop_max == 25
    assert len(drops) == 25


def test_space_rooster_final_wave_uses_reduced_speed() -> None:
    """SpaceRooster boss speed comes from the reduced final-wave map config."""
    wave_manager = WaveManager(3)
    wave_manager.start_wave(int(wave_manager.map_config["waves"]))
    wave_manager.spawn_pending_now()
    boss = next(enemy for enemy in wave_manager.enemies_alive if isinstance(enemy, SpaceRooster))

    assert boss.map_speed == 34


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


def test_game_scene_combo_pair_input_fires_once(save_path: Path, monkeypatch: object) -> None:
    """Holding two weapon number keys activates one combo attack per press."""
    scene = GameScene(PlayerShip(), SaveManager(save_path), {"current_map": 1})
    laser = LaserCannon()
    plasma = PlasmaSpread()
    while laser.upgrade_level < 3:
        laser.upgrade()
    while plasma.upgrade_level < 3:
        plasma.upgrade()
    scene.player.equip_weapon(laser, 0)
    scene.player.equip_weapon(plasma, 1)
    scene._wave_intro_phase = ""

    monkeypatch.setattr("pygame.key.get_pressed", lambda: {pygame.K_1: True, pygame.K_2: True})
    scene._activate_combo_if_pressed(pygame.key.get_pressed())
    first_count = len(scene.bullets)
    scene._activate_combo_if_pressed(pygame.key.get_pressed())

    assert first_count == 4
    assert len(scene.bullets) == first_count


def test_tab_cycles_weapons_in_game_scene(save_path: Path) -> None:
    """Tab selects the next equipped weapon instead of toggling auto-aim."""
    scene = GameScene(PlayerShip(), SaveManager(save_path), {"current_map": 1})
    scene.player.equip_weapon(LaserCannon(), 0)
    scene.player.equip_weapon(PlasmaSpread(), 2)

    scene.handle_event(SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_TAB))

    assert scene.player.active_weapon_slot == 2


def test_pause_blocks_gameplay_updates(save_path: Path) -> None:
    """Pause input freezes gameplay state until resumed."""
    scene = GameScene(PlayerShip(), SaveManager(save_path), {"current_map": 1})
    phase_before = scene._wave_intro_phase
    scene.handle_event(SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_p))

    scene.update(1.0)

    assert scene.paused is True
    assert scene._wave_intro_phase == phase_before


def test_controls_guide_pauses_gameplay(save_path: Path) -> None:
    """The in-game controls guide pauses gameplay while visible."""
    scene = GameScene(PlayerShip(), SaveManager(save_path), {"current_map": 1})
    scene.handle_event(SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_h))

    assert scene.controls_visible is True
    assert scene.paused is True


def test_pause_controls_are_hidden_until_button_click(save_path: Path) -> None:
    """Pause opens a compact menu; Controls and Back switch explicit panels."""
    scene = GameScene(PlayerShip(), SaveManager(save_path), {"current_map": 1})
    scene.handle_event(SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_p))

    assert scene.paused is True
    assert scene.controls_visible is False

    scene.handle_event(
        SimpleNamespace(
            type=pygame.MOUSEBUTTONDOWN,
            pos=(PAUSE_CONTROLS_RECT.centerx, PAUSE_CONTROLS_RECT.centery),
        )
    )
    assert scene.controls_visible is True

    scene.handle_event(
        SimpleNamespace(
            type=pygame.MOUSEBUTTONDOWN,
            pos=(CONTROLS_BACK_RECT.centerx, CONTROLS_BACK_RECT.centery),
        )
    )
    assert scene.controls_visible is False
    assert scene.paused is True

    scene.handle_event(
        SimpleNamespace(
            type=pygame.MOUSEBUTTONDOWN,
            pos=(PAUSE_RESUME_RECT.centerx, PAUSE_RESUME_RECT.centery),
        )
    )
    assert scene.paused is False
