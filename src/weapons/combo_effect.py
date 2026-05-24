"""Weapon combo effect implementation."""

from __future__ import annotations

from enum import Enum
from typing import Sequence

from src.entities.bullet import Bullet  # TODO: implement in Phase X — use stub for now
from src.weapons.weapon import MAX_WEAPON_LEVEL, WeaponType

ION_BEAM_AOE_RADIUS = 40
CRYO_BURST_AOE_RADIUS = 80
CRYO_BURST_SLOW_SECONDS = 3.0
CRYO_BURST_FREEZE_SECONDS = 1.0
STORM_FIELD_AOE_RADIUS = 60
STORM_FIELD_SLOW_SECONDS = 2.0
STORM_FIELD_STUN_SECONDS = 1.0
VOLT_BEAM_CHAIN_COUNT = 3
HOMING_NOVA_AOE_RADIUS = 50


class ComboType(Enum):
    """Enum describing supported tier 2 weapon combo effects."""

    ION_BEAM = "ION_BEAM"
    CRYO_BURST = "CRYO_BURST"
    STORM_FIELD = "STORM_FIELD"
    VOLT_BEAM = "VOLT_BEAM"
    HOMING_NOVA = "HOMING_NOVA"


COMBO_MAP: dict[frozenset[WeaponType], ComboType] = {
    frozenset((WeaponType.LASER, WeaponType.PLASMA)): ComboType.ION_BEAM,
    frozenset((WeaponType.PLASMA, WeaponType.ICE)): ComboType.CRYO_BURST,
    frozenset((WeaponType.ICE, WeaponType.THUNDER)): ComboType.STORM_FIELD,
    frozenset((WeaponType.THUNDER, WeaponType.LASER)): ComboType.VOLT_BEAM,
    frozenset((WeaponType.MISSILE, WeaponType.PLASMA)): ComboType.HOMING_NOVA,
}


class ComboEffect:
    """Resolves and applies behavior modifiers for two-weapon combo effects."""

    def __init__(
        self,
        first_weapon_type: WeaponType,
        second_weapon_type: WeaponType,
        first_weapon_level: int = MAX_WEAPON_LEVEL,
        second_weapon_level: int = MAX_WEAPON_LEVEL,
    ) -> None:
        """Resolve the combo for two weapon types and record tier 2 unlock state."""
        self.first_weapon_type = first_weapon_type
        self.second_weapon_type = second_weapon_type
        self.combo_type = COMBO_MAP.get(frozenset((first_weapon_type, second_weapon_type)))
        self.required_level = MAX_WEAPON_LEVEL
        self.is_unlocked = (
            self.combo_type is not None
            and first_weapon_level >= self.required_level
            and second_weapon_level >= self.required_level
        )

    def apply(self, bullets: list[Bullet], targets: Sequence[object]) -> list[Bullet]:
        """Modify bullet behavior in place according to the resolved combo."""
        if self.combo_type is None or not self.is_unlocked:
            return bullets

        for bullet in bullets:
            bullet.combo_type = self.combo_type
            bullet.combo_targets = list(targets)
            if self.combo_type is ComboType.ION_BEAM:
                self._apply_ion_beam(bullet)
            elif self.combo_type is ComboType.CRYO_BURST:
                self._apply_cryo_burst(bullet)
            elif self.combo_type is ComboType.STORM_FIELD:
                self._apply_storm_field(bullet)
            elif self.combo_type is ComboType.VOLT_BEAM:
                self._apply_volt_beam(bullet)
            elif self.combo_type is ComboType.HOMING_NOVA:
                self._apply_homing_nova(bullet)

        return bullets

    def _apply_ion_beam(self, bullet: Bullet) -> None:
        """Add piercing and explosion behavior for Laser plus Plasma."""
        bullet.is_piercing = True
        bullet.is_aoe = True
        bullet.aoe_radius = ION_BEAM_AOE_RADIUS

    def _apply_cryo_burst(self, bullet: Bullet) -> None:
        """Add freeze AOE behavior for Plasma plus Ice."""
        bullet.is_aoe = True
        bullet.aoe_radius = CRYO_BURST_AOE_RADIUS
        _merge_debuffs(
            bullet,
            {
                "SLOWED": CRYO_BURST_SLOW_SECONDS,
                "FROZEN": CRYO_BURST_FREEZE_SECONDS,
            },
        )

    def _apply_storm_field(self, bullet: Bullet) -> None:
        """Add slow and stun field behavior for Ice plus Thunder."""
        bullet.is_aoe = True
        bullet.aoe_radius = STORM_FIELD_AOE_RADIUS
        _merge_debuffs(
            bullet,
            {
                "SLOWED": STORM_FIELD_SLOW_SECONDS,
                "STUNNED": STORM_FIELD_STUN_SECONDS,
            },
        )

    def _apply_volt_beam(self, bullet: Bullet) -> None:
        """Add piercing and chain behavior for Thunder plus Laser."""
        bullet.is_piercing = True
        bullet.chain_count = VOLT_BEAM_CHAIN_COUNT

    def _apply_homing_nova(self, bullet: Bullet) -> None:
        """Add homing and AOE behavior for Missile plus Plasma."""
        bullet.homing = True
        bullet.tracking_mode = "nearest_enemy"
        bullet.is_aoe = True
        bullet.aoe_radius = HOMING_NOVA_AOE_RADIUS


def _merge_debuffs(bullet: Bullet, debuffs: dict[str, object]) -> None:
    """Merge combo debuffs onto a Bullet stub without owning future hit logic."""
    existing_debuffs = getattr(bullet, "debuffs", {})
    merged_debuffs = dict(existing_debuffs)
    merged_debuffs.update(debuffs)
    bullet.debuffs = merged_debuffs
