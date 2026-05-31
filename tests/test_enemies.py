"""Tests for enemy-specific polymorphic behavior."""

from __future__ import annotations

import sys
from math import isclose
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.enemies.armored_rooster import ARMORED_ROOSTER_ARMOR_HITS, ARMORED_ROOSTER_HP, ArmoredRooster
from src.enemies.chicken_grunt import ChickenGrunt
from src.enemies.dodge_hen import DODGE_HEN_HP, DodgeHen
from src.enemies.kamikaze import KAMIKAZE_DIVE_SPEED, KamikazeChicken
from src.entities.feather_core import FeatherCore
from src.weapons.weapon import WeaponType


def test_armored_rooster_armor() -> None:
    """ArmoredRooster armor breaks after three non-ice hits."""
    enemy = ArmoredRooster(100.0, 40.0)

    enemy.take_damage(10, weapon_type=WeaponType.LASER)
    enemy.take_damage(10, weapon_type=WeaponType.LASER)

    assert enemy.armor_hp == ARMORED_ROOSTER_ARMOR_HITS - 2
    assert enemy.armor_intact is True
    assert enemy.hp == ARMORED_ROOSTER_HP

    enemy.take_damage(10, weapon_type=WeaponType.LASER)

    assert enemy.armor_hp == 0
    assert enemy.armor_intact is False


def test_armored_rooster_ice_bypass() -> None:
    """Ice damage bypasses armor and applies directly to HP."""
    enemy = ArmoredRooster(100.0, 40.0)

    enemy.take_damage(12, weapon_type=WeaponType.ICE)

    assert enemy.armor_hp == ARMORED_ROOSTER_ARMOR_HITS
    assert enemy.hp == ARMORED_ROOSTER_HP - 12


def test_dodge_hen_immunity() -> None:
    """DodgeHen ignores regular damage but accepts Missile AOE damage."""
    enemy = DodgeHen(100.0, 40.0)

    enemy.take_damage(10, weapon_type=WeaponType.LASER, is_aoe=False)
    assert enemy.hp == DODGE_HEN_HP

    enemy.take_damage(10, weapon_type=WeaponType.MISSILE, is_aoe=True)
    assert enemy.hp == DODGE_HEN_HP - 10


def test_kamikaze_dive() -> None:
    """KamikazeChicken points velocity toward the player when below half HP."""
    enemy = KamikazeChicken(0.0, 0.0, player_position=(100.0, 0.0))
    enemy.hp = int(enemy.max_hp * 0.25)

    enemy.move(0.0)

    assert enemy.vx > 0.0
    assert isclose(enemy.vy, 0.0, abs_tol=1e-6)
    assert isclose(enemy.vx, KAMIKAZE_DIVE_SPEED, rel_tol=1e-6)


def test_enemy_on_death_drops() -> None:
    """ChickenGrunt death drops stay within the 1-2 FC range."""
    enemy = ChickenGrunt(100.0, 40.0)

    for _ in range(10):
        drops = enemy.on_death()
        assert 1 <= len(drops) <= 2
        assert all(isinstance(drop, FeatherCore) for drop in drops)


def test_feather_core_falls_downward() -> None:
    """Dropped Feather Cores drift downward instead of staying fixed in place."""
    core = FeatherCore(100.0, 40.0, value=1)

    core.update(1.0)

    assert core.y > 40.0
