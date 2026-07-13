"""Player ship entity with weapons, resources, and drones."""

from __future__ import annotations

from math import ceil, hypot
from typing import Mapping, Sequence

import pygame

from src.entities.bullet import Bullet, PLAYER_BULLET_OWNER
from src.entities.drone import Drone, DroneMode
from src.entities.pickup import Pickup
from src.entities.game_object import GameObject
from src.enemies.enemy import Enemy
from src.utils.resource import load_sprite, play_sound
from src.utils.constants import MAX_ACTIVE_DRONES, MIN_HEALTH, SCREEN_HEIGHT, SCREEN_WIDTH
from src.weapons.weapon import DEFAULT_FIRE_DIRECTION, MAX_WEAPON_LEVEL, ComboType, Direction, Weapon, WeaponType

PLAYER_WIDTH = 54
PLAYER_HEIGHT = 59
PLAYER_MAX_HP = 100
PLAYER_SPEED = 260.0
PLAYER_START_X = SCREEN_WIDTH / 2 - PLAYER_WIDTH / 2
PLAYER_START_Y = SCREEN_HEIGHT - PLAYER_HEIGHT * 2
PLAYER_WEAPON_SLOT_COUNT = 3
PLAYER_MUZZLE_OFFSETS = (-16.0, 0.0, 16.0)
PLAYER_DEFAULT_ACTIVE_WEAPON_SLOT = 0
PLAYER_CENTER_DIVISOR = 2.0
PLAYER_REPAIR_FC_CHUNK = 10
PLAYER_REPAIR_HP_PERCENT_PER_CHUNK = 0.20
PLAYER_INITIAL_FC = 0
PLAYER_INITIAL_SCORE = 0
PLAYER_STARTING_LIVES = 3
NORMAL_DAMAGE_MULTIPLIER = 1.0
DRONE_SUMMON_FC_COST = 30
ION_BEAM_AOE_RADIUS = 16
ION_BEAM_DAMAGE_MULTIPLIER = 0.65
HOMING_NOVA_AOE_RADIUS = 50
ZERO_MOVEMENT = 0.0
PLAYER_COLOR = (80, 220, 255)
MANUAL_FIRE_DIRECTION: Direction = DEFAULT_FIRE_DIRECTION


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
        self.drone_mode = DroneMode.AUTO
        self.drones: list[Drone] = initial_drones
        self.unlocked_drones: set[type[Drone]] = {type(drone) for drone in initial_drones}
        for drone in self.drones:
            drone.owner = self
            drone.set_mode(self.drone_mode)
        self._fc_inventory = PLAYER_INITIAL_FC
        self.score = PLAYER_INITIAL_SCORE
        self.lives = PLAYER_STARTING_LIVES
        self.active_weapon_slot = PLAYER_DEFAULT_ACTIVE_WEAPON_SLOT
        self.auto_targets: list[GameObject] = []
        self.active_combo: ComboType | None = None
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
        fc_items: list[Pickup],
        enemy_bullets: list[Bullet] | None = None,
    ) -> list[Bullet]:
        """Update composed drones and return bullets emitted by drone behavior."""
        emitted_bullets: list[Bullet] = []
        for drone in self._active_drones():
            drone.set_mode(self.drone_mode)
            emitted_bullets.extend(item for item in drone.update_behavior(dt, self, enemies, fc_items) if isinstance(item, Bullet))
        self.drones = self._active_drones()
        return emitted_bullets

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
        self.active_weapon_slot = PLAYER_DEFAULT_ACTIVE_WEAPON_SLOT
        self.drone_mode = DroneMode.AUTO
        self.drones = []
        self.unlocked_drones = set()
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
        """Fire only the currently selected weapon slot."""
        weapon = self._active_weapon()
        if weapon is None:
            return []

        bullets = weapon.fire(
            self._slot_origin_x(self.active_weapon_slot),
            self.y,
            self._get_fire_direction(),
        )
        if bullets:
            play_sound("player_fire")
        for bullet in bullets:
            _mark_player_bullet(bullet)
        return bullets

    def activate_combo(self, first_slot: int, second_slot: int) -> tuple[list[Bullet], ComboType | None]:
        """Fire a slot-pair combo attack when both weapons form an unlocked combo."""
        combo = self._combo_for_slots(first_slot, second_slot)
        if combo is None:
            return [], None

        bullets: list[Bullet] = []
        for slot_index in (first_slot, second_slot):
            weapon = self.weapon_slots[slot_index]
            if weapon is None or not weapon.can_fire():
                return [], None

        for slot_index in (first_slot, second_slot):
            weapon = self.weapon_slots[slot_index]
            if weapon is None:
                continue
            fired_bullets = weapon.fire(
                self._slot_origin_x(slot_index),
                self.y,
                self._get_fire_direction(),
            )
            bullets.extend(fired_bullets)

        if not bullets:
            return [], None

        play_sound("player_fire")
        for bullet in bullets:
            _mark_player_bullet(bullet)
        self._apply_combo_to_bullets(combo, bullets)
        for bullet in bullets:
            _sync_bullet_aliases(bullet)
        self.active_combo = combo
        return bullets, combo

    def activate_skill(self) -> dict[str, object] | None:
        """Trigger the special slot skill when its weapon cooldown is ready."""
        if self.special_slot is None or not self.special_slot.can_fire():
            return None

        effect = self.special_slot.get_skill_effect()
        self.special_slot.current_cooldown = self.special_slot.cooldown
        return effect

    def equip_weapon(self, weapon: Weapon | None, slot_index: int) -> None:
        """Equip a weapon into one of the player weapon slots and recalculate combos."""
        if slot_index < MIN_HEALTH or slot_index >= PLAYER_WEAPON_SLOT_COUNT:
            raise IndexError("weapon slot index must be between 0 and 2")

        self.weapon_slots[slot_index] = weapon
        self._recalculate_combo()

    def select_weapon_slot(self, slot_index: int) -> bool:
        """Select the weapon slot that Space will fire."""
        if slot_index < MIN_HEALTH or slot_index >= len(self.weapon_slots):
            return False
        self.active_weapon_slot = slot_index
        return True

    def cycle_weapon_slot(self) -> int:
        """Cycle to the next equipped weapon slot, skipping empty slots."""
        slot_count = len(self.weapon_slots)
        for offset in range(1, slot_count + 1):
            next_slot = (self.active_weapon_slot + offset) % slot_count
            if self.weapon_slots[next_slot] is not None:
                self.active_weapon_slot = next_slot
                return next_slot
        self.active_weapon_slot = PLAYER_DEFAULT_ACTIVE_WEAPON_SLOT
        return self.active_weapon_slot

    def get_active_combo(self) -> ComboType | None:
        """Return an unlocked combo effect among equipped weapons, if any."""
        self._recalculate_combo()
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

    def upgrade_weapon(self, slot_index: int, weapon: Weapon | None = None) -> bool:
        """Spend the selected weapon's JSON-defined FC cost to upgrade it."""
        if slot_index < 0 or slot_index >= len(self.weapon_slots):
            return False
        selected_weapon = weapon or self.weapon_slots[slot_index]
        if selected_weapon is None:
            return False
        cost = selected_weapon.get_upgrade_cost()
        if cost <= 0 or not self.spend_fc(cost):
            return False
        if selected_weapon.upgrade():
            self._recalculate_combo()
            return True
        self.add_fc(cost)
        return False

    def purchase_life(self, cost: int, maximum_lives: int) -> bool:
        """Spend FC for one life while respecting the existing life cap."""
        if self.lives >= maximum_lives or not self.spend_fc(cost):
            return False
        self.lives += 1
        return True

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
        if len(self._active_drones()) >= MAX_ACTIVE_DRONES or not self.is_drone_unlocked(drone_type):
            return None
        if not self.spend_fc(DRONE_SUMMON_FC_COST):
            return None
        drone = drone_type(self)
        drone.set_mode(self.drone_mode)
        self.drones.append(drone)
        return drone

    def unlock_drone(self, drone_type: type[Drone]) -> bool:
        """Unlock a drone type by spending its unlock FC cost."""
        if self.is_drone_unlocked(drone_type):
            return True
        unlock_cost = int(getattr(drone_type, "unlock_cost", 0))
        if unlock_cost > 0 and not self.spend_fc(unlock_cost):
            return False
        self.unlocked_drones.add(drone_type)
        return True

    def apply_debuff(self, debuff_type: str, duration: float) -> None:
        """Stub — player debuff effects not implemented yet (Phase 3)."""
        pass

    def toggle_drone_mode(self) -> DroneMode:
        """Toggle all active drones between AUTO and FOLLOW mode."""
        self.drone_mode = DroneMode.FOLLOW if self.drone_mode is DroneMode.AUTO else DroneMode.AUTO
        for drone in self._active_drones():
            drone.set_mode(self.drone_mode)
        return self.drone_mode

    def set_auto_targets(self, enemies: Sequence[GameObject]) -> None:
        """Store enemies used by combo target selection."""
        self.auto_targets = [enemy for enemy in enemies if getattr(enemy, "active", True)]

    def _get_fire_direction(self) -> Direction:
        """Return the manual upward fire direction."""
        return MANUAL_FIRE_DIRECTION

    def on_fc_collected(self) -> None:
        """Advance the FC collection streak counter."""
        self.fc_streak_counter += 1

    def on_player_hit(self) -> None:
        """Break the FC streak when the player takes collision damage."""
        self.fc_streak_counter = PLAYER_INITIAL_FC

    def get_damage_multiplier(self) -> float:
        """Return the current damage multiplier (always normal, fever removed)."""
        return NORMAL_DAMAGE_MULTIPLIER

    def is_drone_unlocked(self, drone_type: type[Drone]) -> bool:
        """Return whether a drone class may be summoned by this ship."""
        return int(getattr(drone_type, "unlock_cost", 0)) == 0 or drone_type in self.unlocked_drones

    def _recalculate_combo(self) -> None:
        """Recalculate combo state from any two equipped weapon slots."""
        for first_slot in range(len(self.weapon_slots)):
            for second_slot in range(first_slot + 1, len(self.weapon_slots)):
                combo = self._combo_for_slots(first_slot, second_slot)
                if combo is not None:
                    self.active_combo = combo
                    return
        self.active_combo = None

    def _combo_for_slots(self, first_slot: int, second_slot: int) -> ComboType | None:
        """Return the combo effect for two slot indices when their weapon types differ."""
        if first_slot == second_slot:
            return None
        if first_slot < MIN_HEALTH or second_slot < MIN_HEALTH:
            return None
        if first_slot >= len(self.weapon_slots) or second_slot >= len(self.weapon_slots):
            return None

        first_weapon = self.weapon_slots[first_slot]
        second_weapon = self.weapon_slots[second_slot]
        if first_weapon is None or second_weapon is None:
            return None
        if first_weapon.weapon_type is second_weapon.weapon_type:
            return None

        if first_weapon.upgrade_level < MAX_WEAPON_LEVEL or second_weapon.upgrade_level < MAX_WEAPON_LEVEL:
            return None
        pair = frozenset((first_weapon.weapon_type, second_weapon.weapon_type))
        if pair == frozenset((WeaponType.LASER, WeaponType.PLASMA)):
            return ComboType.ION_BEAM
        if pair == frozenset((WeaponType.MISSILE, WeaponType.PLASMA)):
            return ComboType.HOMING_NOVA
        return None

    def _apply_combo_to_bullets(self, combo: ComboType, bullets: list[Bullet]) -> None:
        """Apply the original combo modifiers directly from PlayerShip ownership."""
        for bullet in bullets:
            bullet.combo_type = combo
            bullet.combo_targets = list(self.auto_targets)
            if combo is ComboType.ION_BEAM:
                bullet.is_piercing = True
                bullet.is_aoe = True
                bullet.aoe_radius = ION_BEAM_AOE_RADIUS
                bullet.damage *= ION_BEAM_DAMAGE_MULTIPLIER
            elif combo is ComboType.HOMING_NOVA:
                bullet.homing = True
                bullet.tracking_mode = "nearest_enemy"
                bullet.is_aoe = True
                bullet.aoe_radius = HOMING_NOVA_AOE_RADIUS

    def _active_drones(self) -> list[Drone]:
        """Return drones that are still active and have not been destroyed."""
        return [drone for drone in self.drones if not drone.is_destroyed and getattr(drone, "active", True)]

    def _active_weapon(self) -> Weapon | None:
        """Return the currently selected weapon, if one is equipped."""
        if self.active_weapon_slot < MIN_HEALTH or self.active_weapon_slot >= len(self.weapon_slots):
            return None
        return self.weapon_slots[self.active_weapon_slot]

    def _slot_origin_x(self, slot_index: int) -> float:
        """Return the muzzle x coordinate for a weapon slot."""
        offset = PLAYER_MUZZLE_OFFSETS[slot_index] if slot_index < len(PLAYER_MUZZLE_OFFSETS) else 0.0
        return self.x + self.width / PLAYER_CENTER_DIVISOR + offset


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
