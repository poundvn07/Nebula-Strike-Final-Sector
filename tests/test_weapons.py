"""Tests for weapon upgrades, cooldowns, and combo resolution."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.entities.bullet import Bullet
from src.entities.player_ship import PlayerShip
from src.systems.resource_manager import ResourceManager
from src.weapons.combo_effect import ION_BEAM_AOE_RADIUS, ION_BEAM_DAMAGE_MULTIPLIER, ComboEffect, ComboType
from src.weapons.laser_cannon import LaserCannon
from src.weapons.missile_salvo import MissileSalvo
from src.weapons.plasma_spread import PlasmaSpread
from src.weapons.weapon import WeaponType


def _upgrade_to_max(weapon: object) -> None:
    """Upgrade a weapon until it reaches level 3."""
    while getattr(weapon, "upgrade_level") < 3:
        weapon.upgrade()


def test_weapon_upgrade_levels() -> None:
    """LaserCannon upgrades cap at level 3."""
    weapon = LaserCannon()

    assert weapon.upgrade() is True
    assert weapon.upgrade() is True
    assert weapon.upgrade() is False

    assert weapon.upgrade_level == 3


def test_weapon_upgrade_cost() -> None:
    """A max-level weapon cannot upgrade and does not spend FC."""
    player = PlayerShip()
    weapon = LaserCannon()
    _upgrade_to_max(weapon)
    player.weapon_slots[0] = weapon
    player.add_fc(100)

    upgraded = ResourceManager().upgrade_weapon(player, 0)

    assert upgraded is False
    assert player.fc_inventory == 100
    assert weapon.upgrade_level == 3


def test_combo_resolution() -> None:
    """Equipping max-level Laser plus Plasma resolves Ion Beam."""
    player = PlayerShip()
    laser = LaserCannon()
    plasma = PlasmaSpread()
    _upgrade_to_max(laser)
    _upgrade_to_max(plasma)

    player.equip_weapon(laser, 0)
    player.equip_weapon(plasma, 1)

    combo = player.get_active_combo()
    assert combo is not None
    assert combo.combo_type is ComboType.ION_BEAM


def test_ion_beam_combo_is_capped() -> None:
    """Ion Beam keeps piercing/AOE behavior without full-damage wave-clearing reach."""
    bullet = Bullet(damage=20)
    combo = ComboEffect(WeaponType.LASER, WeaponType.PLASMA)

    combo.apply([bullet], [])

    assert bullet.is_piercing is True
    assert bullet.is_aoe is True
    assert bullet.aoe_radius == ION_BEAM_AOE_RADIUS
    assert bullet.damage == 20 * ION_BEAM_DAMAGE_MULTIPLIER


def test_combo_none_same_type() -> None:
    """Two weapons of the same type do not create a combo."""
    player = PlayerShip()
    first_laser = LaserCannon()
    second_laser = LaserCannon()
    _upgrade_to_max(first_laser)
    _upgrade_to_max(second_laser)

    player.equip_weapon(first_laser, 0)
    player.equip_weapon(second_laser, 1)

    assert player.get_active_combo() is None


def test_player_has_three_weapon_slots_and_fires_only_active_slot() -> None:
    """Space should fire only the selected weapon instead of every owned weapon."""
    player = PlayerShip()
    player.equip_weapon(LaserCannon(), 0)
    player.equip_weapon(MissileSalvo(), 1)
    player.select_weapon_slot(1)

    bullets = player.fire(0.1)

    assert len(player.weapon_slots) == 3
    assert len(bullets) == 1
    assert bullets[0].weapon_type is WeaponType.MISSILE


def test_tab_cycle_skips_empty_weapon_slots() -> None:
    """Cycling weapons should move through equipped slots in order."""
    player = PlayerShip()
    player.equip_weapon(LaserCannon(), 0)
    player.equip_weapon(MissileSalvo(), 2)

    assert player.cycle_weapon_slot() == 2
    assert player.active_weapon_slot == 2
    assert player.cycle_weapon_slot() == 0


def test_max_level_plasma_is_capped_by_json_stats() -> None:
    """Max Plasma keeps a three-shot fan with reduced per-shot scaling."""
    plasma = PlasmaSpread()
    _upgrade_to_max(plasma)

    bullets = plasma.fire(100.0, 100.0, (0.0, -1.0))

    assert plasma.damage == 10
    assert round(plasma.cooldown, 2) == 0.58
    assert len(bullets) == 3
    assert all(bullet.damage == 10 for bullet in bullets)


def test_regular_fire_does_not_auto_apply_combo() -> None:
    """Owning combo weapons does not make every Space shot a combo shot."""
    player = PlayerShip()
    laser = LaserCannon()
    plasma = PlasmaSpread()
    _upgrade_to_max(laser)
    _upgrade_to_max(plasma)
    player.equip_weapon(laser, 0)
    player.equip_weapon(plasma, 1)

    bullets = player.fire(0.1)

    assert len(bullets) == 1
    assert bullets[0].is_aoe is False


def test_combo_attack_requires_slot_pair_activation() -> None:
    """A max-level pair can be activated through explicit weapon slot inputs."""
    player = PlayerShip()
    laser = LaserCannon()
    plasma = PlasmaSpread()
    _upgrade_to_max(laser)
    _upgrade_to_max(plasma)
    player.equip_weapon(laser, 0)
    player.equip_weapon(plasma, 1)

    bullets, combo = player.activate_combo(0, 1)

    assert combo is not None
    assert combo.combo_type is ComboType.ION_BEAM
    assert len(bullets) == 4
    assert all(bullet.is_aoe for bullet in bullets)


def test_cooldown_blocks_fire() -> None:
    """A weapon cannot fire again until its cooldown expires."""
    weapon = LaserCannon()

    first_shot = weapon.fire(100.0, 100.0, (0.0, -1.0))
    second_shot = weapon.fire(100.0, 100.0, (0.0, -1.0))

    assert len(first_shot) == 1
    assert second_shot == []
