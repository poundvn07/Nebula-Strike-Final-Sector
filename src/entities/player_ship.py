"""Player ship entity with weapons, resources, and aiming modes."""

from __future__ import annotations

from enum import Enum
from math import ceil, hypot
from typing import Mapping, Sequence

import pygame

from src.entities.bullet import Bullet, PLAYER_BULLET_OWNER
from src.entities.drone import Drone  # TODO: implement in Phase X — use stub for now
from src.entities.game_object import GameObject
from src.utils.constants import MAX_ACTIVE_DRONES, MIN_HEALTH, SCREEN_HEIGHT, SCREEN_WIDTH
from src.weapons.combo_effect import ComboEffect
from src.weapons.weapon import DEFAULT_FIRE_DIRECTION, Direction, Weapon

PLAYER_WIDTH = 42
PLAYER_HEIGHT = 46
PLAYER_MAX_HP = 100
PLAYER_SPEED = 260.0
PLAYER_START_X = SCREEN_WIDTH / 2 - PLAYER_WIDTH / 2
PLAYER_START_Y = SCREEN_HEIGHT - PLAYER_HEIGHT * 2
PLAYER_WEAPON_SLOT_COUNT = 2
PLAYER_LEFT_MUZZLE_OFFSET = -10.0
PLAYER_RIGHT_MUZZLE_OFFSET = 10.0
PLAYER_CENTER_DIVISOR = 2.0
PLAYER_REPAIR_FC_CHUNK = 10
PLAYER_REPAIR_HP_PERCENT_PER_CHUNK = 0.20
PLAYER_INITIAL_FC = 0
PLAYER_INITIAL_SCORE = 0
ZERO_MOVEMENT = 0.0
PLAYER_COLOR = (80, 220, 255)
MANUAL_FIRE_DIRECTION: Direction = DEFAULT_FIRE_DIRECTION


class AimingMode(Enum):
    """Enum describing player fire direction selection."""

    AUTO = "AUTO"
    MANUAL = "MANUAL"


class PlayerShip(GameObject):
    """Player-controlled GameObject composed with weapons, drones, and resources."""

    def __init__(
        self,
        x: float = PLAYER_START_X,
        y: float = PLAYER_START_Y,
        speed: float = PLAYER_SPEED,
        drones: Sequence[Drone] | None = None,
    ) -> None:
        """Initialize the player ship with empty weapon slots and no auto-heal."""
        super().__init__(x=x, y=y, width=PLAYER_WIDTH, height=PLAYER_HEIGHT, hp=PLAYER_MAX_HP)
        self.speed = speed
        self.weapon_slots: list[Weapon | None] = [None for _ in range(PLAYER_WEAPON_SLOT_COUNT)]
        self.special_slot: Weapon | None = None
        self.drones: list[Drone] = list(drones or [])[:MAX_ACTIVE_DRONES]
        self.fc_inventory = PLAYER_INITIAL_FC
        self.score = PLAYER_INITIAL_SCORE
        self.aiming_mode = AimingMode.MANUAL
        self.auto_targets: list[GameObject] = []
        self.active_combo: ComboEffect | None = None
        self.fc_streak_counter = PLAYER_INITIAL_FC

    def update(self, dt: float) -> None:
        """Update weapon cooldowns; movement is driven by move(keys, dt)."""
        for weapon in self.weapon_slots:
            if weapon is not None:
                weapon.update_cooldown(dt)
        if self.special_slot is not None:
            self.special_slot.update_cooldown(dt)

    def render(self, surface: pygame.Surface) -> None:
        """Draw the player as a rectangle until ship sprites are available."""
        pygame.draw.rect(surface, PLAYER_COLOR, self.get_rect())

    def on_death(self) -> None:
        """Deactivate the ship when HP reaches zero."""
        self.active = False

    def move(self, keys_pressed: Mapping[int, bool] | Sequence[bool], dt: float) -> None:
        """Move with WASD or arrow keys and clamp the ship to screen bounds."""
        dx = ZERO_MOVEMENT
        dy = ZERO_MOVEMENT

        if _is_pressed(keys_pressed, pygame.K_a) or _is_pressed(keys_pressed, pygame.K_LEFT):
            dx -= self.speed
        if _is_pressed(keys_pressed, pygame.K_d) or _is_pressed(keys_pressed, pygame.K_RIGHT):
            dx += self.speed
        if _is_pressed(keys_pressed, pygame.K_w) or _is_pressed(keys_pressed, pygame.K_UP):
            dy -= self.speed
        if _is_pressed(keys_pressed, pygame.K_s) or _is_pressed(keys_pressed, pygame.K_DOWN):
            dy += self.speed

        magnitude = hypot(dx, dy)
        if magnitude > ZERO_MOVEMENT:
            dx = dx / magnitude * self.speed
            dy = dy / magnitude * self.speed

        self.x = _clamp(self.x + dx * dt, ZERO_MOVEMENT, SCREEN_WIDTH - self.width)
        self.y = _clamp(self.y + dy * dt, ZERO_MOVEMENT, SCREEN_HEIGHT - self.height)

    def fire(self, dt: float) -> list[Bullet]:
        """Fire equipped weapons and apply active combo behavior when available."""
        self.update(dt)
        self._recalculate_combo()
        bullets: list[Bullet] = []
        muzzle_offsets = (PLAYER_LEFT_MUZZLE_OFFSET, PLAYER_RIGHT_MUZZLE_OFFSET)

        for slot_index, weapon in enumerate(self.weapon_slots):
            if weapon is None:
                continue

            origin_x = self.x + self.width / PLAYER_CENTER_DIVISOR + muzzle_offsets[slot_index]
            origin_y = self.y
            fired_bullets = weapon.fire(origin_x, origin_y, self._get_fire_direction())
            for bullet in fired_bullets:
                _mark_player_bullet(bullet)
            bullets.extend(fired_bullets)

        combo = self.get_active_combo()
        if combo is not None:
            combo.apply(bullets, self.auto_targets)
            for bullet in bullets:
                _sync_bullet_aliases(bullet)

        return bullets

    def activate_skill(self) -> dict[str, object] | None:
        """Trigger the special slot skill when its weapon cooldown is ready."""
        if self.special_slot is None or not self.special_slot.can_fire():
            return None

        effect = self.special_slot.get_skill_effect()
        self.special_slot.current_cooldown = self.special_slot.cooldown
        return effect

    def equip_weapon(self, weapon: Weapon | None, slot_index: int) -> None:
        """Equip a weapon into one of two slots and recalculate combo state."""
        if slot_index < MIN_HEALTH or slot_index >= PLAYER_WEAPON_SLOT_COUNT:
            raise IndexError("weapon slot index must be 0 or 1")

        self.weapon_slots[slot_index] = weapon
        self._recalculate_combo()

    def get_active_combo(self) -> ComboEffect | None:
        """Return the unlocked combo effect for two different weapon types, if any."""
        self._recalculate_combo()
        if self.active_combo is None or not self.active_combo.is_unlocked:
            return None
        return self.active_combo

    def take_damage(self, amount: int) -> None:
        """Reduce HP without any automatic regeneration between waves."""
        if amount <= MIN_HEALTH or not self.active:
            return

        self.hp = max(MIN_HEALTH, self.hp - amount)
        if self.hp == MIN_HEALTH:
            self.on_death()

    def repair(self, fc_amount: int) -> int:
        """Spend FC to restore 20 percent max HP for every 10 FC spent."""
        if self.hp >= self.max_hp or fc_amount < PLAYER_REPAIR_FC_CHUNK:
            return PLAYER_INITIAL_FC

        available_fc = min(fc_amount, self.fc_inventory)
        hp_per_chunk = int(self.max_hp * PLAYER_REPAIR_HP_PERCENT_PER_CHUNK)
        missing_hp = self.max_hp - self.hp
        chunks_needed = ceil(missing_hp / hp_per_chunk)
        repair_chunks = min(available_fc // PLAYER_REPAIR_FC_CHUNK, chunks_needed)
        if repair_chunks <= MIN_HEALTH:
            return PLAYER_INITIAL_FC

        spent_fc = repair_chunks * PLAYER_REPAIR_FC_CHUNK
        restored_hp = hp_per_chunk * repair_chunks
        self.fc_inventory -= spent_fc
        self.hp = min(self.max_hp, self.hp + restored_hp)
        return spent_fc

    def add_fc(self, amount: int) -> None:
        """Add Feather Core currency to the player inventory."""
        if amount > MIN_HEALTH:
            self.fc_inventory += amount

    def toggle_aiming_mode(self) -> AimingMode:
        """Toggle between automatic nearest-target aiming and manual straight fire."""
        self.aiming_mode = AimingMode.AUTO if self.aiming_mode is AimingMode.MANUAL else AimingMode.MANUAL
        return self.aiming_mode

    def set_auto_targets(self, enemies: Sequence[GameObject]) -> None:
        """Store enemies used by AUTO aiming and combo target selection."""
        self.auto_targets = [enemy for enemy in enemies if getattr(enemy, "active", True)]

    def _get_fire_direction(self) -> Direction:
        """Return the current fire direction based on the active aiming mode."""
        if self.aiming_mode is AimingMode.MANUAL:
            return MANUAL_FIRE_DIRECTION

        nearest_enemy = self._nearest_enemy()
        if nearest_enemy is None:
            return MANUAL_FIRE_DIRECTION

        origin_x = self.x + self.width / PLAYER_CENTER_DIVISOR
        origin_y = self.y
        return nearest_enemy.x - origin_x, nearest_enemy.y - origin_y

    def _nearest_enemy(self) -> GameObject | None:
        """Return the nearest active enemy for AUTO aiming."""
        active_targets = [enemy for enemy in self.auto_targets if getattr(enemy, "active", True)]
        if not active_targets:
            return None

        origin_x = self.x + self.width / PLAYER_CENTER_DIVISOR
        origin_y = self.y
        return min(active_targets, key=lambda enemy: (enemy.x - origin_x) ** 2 + (enemy.y - origin_y) ** 2)

    def _recalculate_combo(self) -> None:
        """Recalculate combo state from the two equipped weapon slots."""
        first_weapon, second_weapon = self.weapon_slots
        if first_weapon is None or second_weapon is None:
            self.active_combo = None
            return
        if first_weapon.weapon_type is second_weapon.weapon_type:
            self.active_combo = None
            return

        self.active_combo = ComboEffect(
            first_weapon.weapon_type,
            second_weapon.weapon_type,
            first_weapon.upgrade_level,
            second_weapon.upgrade_level,
        )


def _is_pressed(keys_pressed: Mapping[int, bool] | Sequence[bool], key: int) -> bool:
    """Return whether a pygame key is pressed for mapping or sequence key states."""
    getter = getattr(keys_pressed, "get", None)
    if getter is not None:
        return bool(getter(key, False))

    try:
        return bool(keys_pressed[key])
    except (IndexError, KeyError, TypeError):
        return False


def _clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a coordinate between inclusive bounds."""
    return max(minimum, min(maximum, value))


def _mark_player_bullet(bullet: Bullet) -> None:
    """Normalize weapon-created Bullet objects as player-owned projectiles."""
    bullet.owner = PLAYER_BULLET_OWNER
    _sync_bullet_aliases(bullet)


def _sync_bullet_aliases(bullet: Bullet) -> None:
    """Keep legacy weapon fields and Bullet fields aligned."""
    bullet.is_piercing = bool(getattr(bullet, "is_piercing", getattr(bullet, "piercing", False)))
    aoe_radius = int(getattr(bullet, "aoe_radius", getattr(bullet, "explosion_radius", MIN_HEALTH)))
    bullet.aoe_radius = aoe_radius
    bullet.is_aoe = bool(getattr(bullet, "is_aoe", False) or getattr(bullet, "explodes", False) or aoe_radius > MIN_HEALTH)
