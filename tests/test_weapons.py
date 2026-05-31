"""Tests for weapon upgrades, cooldowns, and combo resolution."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.entities.player_ship import PlayerShip
from src.systems.resource_manager import ResourceManager
from src.weapons.combo_effect import ComboType
from src.weapons.laser_cannon import LaserCannon
from src.weapons.plasma_spread import PlasmaSpread


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


def test_cooldown_blocks_fire() -> None:
    """A weapon cannot fire again until its cooldown expires."""
    weapon = LaserCannon()

    first_shot = weapon.fire(100.0, 100.0, (0.0, -1.0))
    second_shot = weapon.fire(100.0, 100.0, (0.0, -1.0))

    assert len(first_shot) == 1
    assert second_shot == []
