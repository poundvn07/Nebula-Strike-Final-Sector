"""Player ship entity with weapons, resources, and aiming modes."""

from __future__ import annotations

from enum import Enum
from math import ceil, hypot
from typing import Mapping, Sequence

import pygame

from src.entities.bullet import Bullet, PLAYER_BULLET_OWNER
from src.entities.drone import Drone, DroneMode
from src.entities.drone_manager import DroneManager
from src.entities.feather_core import FeatherCore
from src.entities.game_object import GameObject
from src.enemies.enemy import Enemy
from src.utils.assets import load_sprite, play_sound
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
PLAYER_STARTING_LIVES = 3
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
        initial_drones = list(drones or [])[:MAX_ACTIVE_DRONES]
        self.drone_manager = DroneManager(self, initial_drones)
        self.drones: list[Drone] = self.drone_manager.drones
        self.unlocked_drones: set[type[Drone]] = self.drone_manager.unlocked_drone_types
        self._fc_inventory = PLAYER_INITIAL_FC
        self.score = PLAYER_INITIAL_SCORE
        self.lives = PLAYER_STARTING_LIVES
        self.aiming_mode = AimingMode.MANUAL
        self.auto_targets: list[GameObject] = []
        self.active_combo: ComboEffect | None = None
        self.fc_streak_counter = PLAYER_INITIAL_FC

    @property
    def fc_inventory(self) -> int:
        """Return the player's Feather Core inventory."""
        return self._fc_inventory

    def update(self, dt: float) -> None:
        """Update weapon cooldowns; movement is driven by move(keys, dt)."""
        for weapon in self.weapon_slots:
            if weapon is not None:
                weapon.update_cooldown(dt)
        if self.special_slot is not None:
            self.special_slot.update_cooldown(dt)

    def update_drones(
        self,
        dt: float,
        enemies: list[Enemy],
        fc_items: list[FeatherCore],
        enemy_bullets: list[Bullet] | None = None,
    ) -> list[Bullet]:
        """Update composed drones and return bullets emitted by drone behavior."""
        drone_bullets = self.drone_manager.update(dt, enemies, fc_items, enemy_bullets)
        self.drones = self.drone_manager.drones
        return drone_bullets

    def render(self, surface: pygame.Surface) -> None:
        """Draw the player ship sprite, falling back to a rectangle."""
        sprite = load_sprite("player_ship", (int(self.width), int(self.height)))
        if sprite is not None:
            surface.blit(sprite, self.get_rect())
            return
        pygame.draw.rect(surface, PLAYER_COLOR, self.get_rect())

    def on_death(self) -> None:
        """Deactivate the ship when HP reaches zero."""
        self.active = False

    def consume_life(self) -> bool:
        """Spend one life for an in-map respawn, returning False on final death."""
        if self.lives <= 1:
            self.lives = MIN_HEALTH
            return False

        self.lives -= 1
        return True

    def respawn(self) -> None:
        """Restore the ship after a life loss while preserving current run progress."""
        self.hp = self.max_hp
        self.active = True
        self.x = PLAYER_START_X
        self.y = PLAYER_START_Y

    def reset_for_new_run(self) -> None:
        """Reset run-owned player state after all lives have been lost."""
        self.hp = self.max_hp
        self.active = True
        self.x = PLAYER_START_X
        self.y = PLAYER_START_Y
        self._fc_inventory = PLAYER_INITIAL_FC
        self.score = PLAYER_INITIAL_SCORE
        self.lives = PLAYER_STARTING_LIVES
        self.weapon_slots = [None for _ in range(PLAYER_WEAPON_SLOT_COUNT)]
        self.special_slot = None
        self.drone_manager = DroneManager(self, [])
        self.drones = self.drone_manager.drones
        self.unlocked_drones = self.drone_manager.unlocked_drone_types
        self.auto_targets = []
        self.fc_streak_counter = PLAYER_INITIAL_FC
        self.active_combo = None

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
        self._recalculate_combo()
        bullets: list[Bullet] = []
        muzzle_offsets = (PLAYER_LEFT_MUZZLE_OFFSET, PLAYER_RIGHT_MUZZLE_OFFSET)

        for slot_index, weapon in enumerate(self.weapon_slots):
            if weapon is None:
                continue

            origin_x = self.x + self.width / PLAYER_CENTER_DIVISOR + muzzle_offsets[slot_index]
            origin_y = self.y
            fired_bullets = weapon.fire(origin_x, origin_y, self._get_fire_direction())
            if fired_bullets:
                play_sound("player_fire")
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
        if not self.spend_fc(spent_fc):
            return PLAYER_INITIAL_FC

        self.hp = min(self.max_hp, self.hp + restored_hp)
        return spent_fc

    def add_fc(self, amount: int) -> None:
        """Add Feather Core currency to the player inventory."""
        self._fc_inventory += amount

    def spend_fc(self, amount: int) -> bool:
        """Spend Feather Core currency if enough is available."""
        if self._fc_inventory >= amount:
            self._fc_inventory -= amount
            return True
        return False

    def summon_drone(self, drone_type: type[Drone]) -> Drone | None:
        """Summon one unlocked drone type by spending the drone summon FC cost."""
        drone = self.drone_manager.summon_drone(drone_type)
        self.drones = self.drone_manager.drones
        return drone

    def unlock_drone(self, drone_type: type[Drone]) -> bool:
        """Unlock a drone type by spending its unlock FC cost."""
        unlocked = self.drone_manager.unlock_drone(drone_type)
        self.unlocked_drones = self.drone_manager.unlocked_drone_types
        return unlocked

    def apply_debuff(self, debuff_type: str, duration: float) -> None:
        """Stub — player debuff effects not implemented yet (Phase 3)."""
        pass

    def toggle_aiming_mode(self) -> AimingMode:
        """Toggle between automatic nearest-target aiming and manual straight fire."""
        self.aiming_mode = AimingMode.AUTO if self.aiming_mode is AimingMode.MANUAL else AimingMode.MANUAL
        return self.aiming_mode

    def toggle_drone_mode(self) -> DroneMode:
        """Toggle all active drones between AUTO and FOLLOW mode."""
        return self.drone_manager.toggle_mode()

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
    """Keep weapon-created bullets aligned with canonical Bullet fields."""
    bullet.is_piercing = bool(bullet.is_piercing)
    aoe_radius = int(bullet.aoe_radius)
    bullet.aoe_radius = aoe_radius
    bullet.is_aoe = bool(bullet.is_aoe or aoe_radius > MIN_HEALTH)
