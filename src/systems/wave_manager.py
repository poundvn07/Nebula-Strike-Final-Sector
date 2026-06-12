"""Wave spawning system for Nebula Strike maps."""

from __future__ import annotations

from json import load
from math import sin
from pathlib import Path
from typing import Callable, TypeAlias

from src.enemies.armored_rooster import ArmoredRooster
from src.enemies.chicken_grunt import ChickenGrunt
from src.enemies.chicken_overlord import ChickenOverlord
from src.enemies.dodge_hen import DodgeHen
from src.enemies.egg_bomber import EggBomber
from src.enemies.enemy import Enemy, FormationOffset
from src.enemies.kamikaze import KamikazeChicken
from src.enemies.space_rooster import SpaceRooster
from src.utils.constants import FINAL_MAP_INDEX, FIRST_MAP_INDEX, MIN_HEALTH, SCREEN_HEIGHT, SCREEN_WIDTH

SpawnEntry: TypeAlias = dict[str, object]
EnemyFactory: TypeAlias = Callable[[float, float, int, FormationOffset], Enemy]

ENEMY_STATS_PATH = Path(__file__).resolve().parents[2] / "data" / "enemy_stats.json"
SPAWN_Y = 96.0
MAP_ONE_WAVE_ONE_SPAWN_Y = 92.0
MAP_ONE_WAVE_ONE_ROW_SPACING = 66.0
MAP_ONE_WAVE_ONE_ENEMY_COUNT = 12
MAP_ONE_WAVE_ONE_ATTACK_COOLDOWN_SCALE = 2.6
BASE_SPAWN_DELAY_SECONDS = 0.0
SPAWN_STAGGER_SECONDS = 0.0
FORMATIONS_PER_ROW = 6
FORMATION_CENTER_INDEX_OFFSET = 1
FORMATION_CENTER_DIVISOR = 2.0
FORMATION_X_SPACING = 96.0
FORMATION_Y_SPACING = 44.0
V_FORMATION_WAVE_ARG = 1
GRID_FORMATION_WAVE_ARG = 0
SPIRAL_FORMATION_WAVE_ARG = 2
V_FORMATION_MAX_WAVE = 3
GRID_FORMATION_MAX_WAVE = 6
BASE_ENEMY_COUNT = 6
ENEMY_COUNT_PER_WAVE = 2
ENEMY_COUNT_PER_MAP = 2
MIN_TWO_ROW_ENEMY_COUNT = FORMATIONS_PER_ROW * 2
BASE_WAVE_REWARD = 10
WAVE_REWARD_SCALE = 4
MAP_REWARD_SCALE = 2
TIER_TWO_START_WAVE = 4
MAP_TWO_ARMORED_PERCENT = 20
PERCENT_MAX = 100
MAP_THREE_TIER_TWO_PERCENT = 35
MAP_FOUR_TIER_TWO_PERCENT = 70
MAP_FIVE_TIER_TWO_PERCENT = 50
FORMATION_SWAY_X = 52.0
FORMATION_SWAY_Y = 28.0
FORMATION_SWAY_X_RATE = 1.25
FORMATION_SWAY_Y_RATE = 0.85
FORMATION_TOP_MARGIN = 42.0
FORMATION_BOTTOM_RATIO = 0.55
FORMATION_LEFT_MARGIN = 12.0
FORMATION_RIGHT_MARGIN = 12.0
BASE_ATTACK_COOLDOWN_SCALE = 1.45
MAP_ATTACK_COOLDOWN_SCALE = 0.08
WAVE_ATTACK_COOLDOWN_SCALE = 0.04
MAX_ATTACK_COOLDOWN_SCALE = 2.25

CHICKEN_GRUNT_TYPE = "chicken_grunt"
EGG_BOMBER_TYPE = "egg_bomber"
KAMIKAZE_TYPE = "kamikaze"
ARMORED_ROOSTER_TYPE = "armored_rooster"
DODGE_HEN_TYPE = "dodge_hen"
SPACE_ROOSTER_TYPE = "space_rooster"
CHICKEN_OVERLORD_TYPE = "chicken_overlord"

TIER_ONE_TYPES = (CHICKEN_GRUNT_TYPE, EGG_BOMBER_TYPE, KAMIKAZE_TYPE)
TIER_TWO_TYPES = (ARMORED_ROOSTER_TYPE, DODGE_HEN_TYPE)
FORMATION_ENEMY_TYPES = (CHICKEN_GRUNT_TYPE, EGG_BOMBER_TYPE)

MAP_CONFIGS = {
    1: {
        "waves": 5,
        "boss": SPACE_ROOSTER_TYPE,
        "tier_two_percent": 0,
        "allowed_types": TIER_ONE_TYPES,
        "boss_phases": 1,
    },
    2: {
        "waves": 6,
        "boss": SPACE_ROOSTER_TYPE,
        "tier_two_percent": MAP_TWO_ARMORED_PERCENT,
        "allowed_types": TIER_ONE_TYPES + (ARMORED_ROOSTER_TYPE,),
        "boss_phases": 1,
    },
    3: {
        "waves": 7,
        "boss": SPACE_ROOSTER_TYPE,
        "tier_two_percent": MAP_THREE_TIER_TWO_PERCENT,
        "allowed_types": TIER_ONE_TYPES + TIER_TWO_TYPES,
        "boss_phases": 3,
    },
    4: {
        "waves": 7,
        "boss": CHICKEN_OVERLORD_TYPE,
        "tier_two_percent": MAP_FOUR_TIER_TWO_PERCENT,
        "allowed_types": TIER_ONE_TYPES + TIER_TWO_TYPES,
        "boss_phases": 1,
    },
    5: {
        "waves": 8,
        "boss": CHICKEN_OVERLORD_TYPE,
        "tier_two_percent": MAP_FIVE_TIER_TWO_PERCENT,
        "allowed_types": TIER_ONE_TYPES + TIER_TWO_TYPES,
        "boss_phases": 2,
    },
}


class WaveManager:
    """Manages map-local waves by queuing and spawning polymorphic Enemy objects."""

    def __init__(self, map_number: int) -> None:
        """Load map enemy stats and initialize wave progression state."""
        if map_number < FIRST_MAP_INDEX or map_number > FINAL_MAP_INDEX:
            raise ValueError("map_number must be between 1 and 5")

        self.map_number = map_number
        self.map_config = MAP_CONFIGS[map_number]
        self.enemy_config = self._load_enemy_config(map_number)
        self.current_wave = MIN_HEALTH
        self.enemies_alive: list[Enemy] = []
        self.spawn_queue: list[SpawnEntry] = []
        self.wave_complete = False
        self.map_complete = False
        self.formation_time = BASE_SPAWN_DELAY_SECONDS

    def start_wave(self, wave_num: int) -> None:
        """Build the spawn queue for the requested wave number."""
        max_waves = int(self.map_config["waves"])
        if wave_num < FIRST_MAP_INDEX or wave_num > max_waves:
            raise ValueError(f"wave_num must be between 1 and {max_waves}")

        self.current_wave = wave_num
        self.enemies_alive.clear()
        self.spawn_queue = self._build_spawn_queue(wave_num)
        self.wave_complete = False
        self.map_complete = False
        self.formation_time = BASE_SPAWN_DELAY_SECONDS

    def spawn_pending_now(self) -> None:
        """Move every queued spawn into play so intro gating starts with a full wave."""
        ready_entries = list(self.spawn_queue)
        self.spawn_queue.clear()
        for entry in ready_entries:
            self.enemies_alive.append(self._spawn_enemy(entry))

    def update(self, dt: float) -> None:
        """Tick spawn timers and move ready enemies from the queue into play."""
        self._prune_inactive_enemies()
        if dt < BASE_SPAWN_DELAY_SECONDS:
            dt = BASE_SPAWN_DELAY_SECONDS

        ready_entries: list[SpawnEntry] = []
        pending_entries: list[SpawnEntry] = []
        for entry in self.spawn_queue:
            entry["timer"] = float(entry["timer"]) - dt
            if float(entry["timer"]) <= BASE_SPAWN_DELAY_SECONDS:
                ready_entries.append(entry)
            else:
                pending_entries.append(entry)

        self.spawn_queue = pending_entries
        for entry in ready_entries:
            spawned_enemy = self._spawn_enemy(entry)
            self.enemies_alive.append(spawned_enemy)

        self.formation_time += dt
        self._update_alive_enemies(dt)

        self.wave_complete = self.is_wave_clear()
        self.map_complete = self.wave_complete and self.current_wave == int(self.map_config["waves"])

    def is_wave_clear(self) -> bool:
        """Return whether no enemies remain alive and no queued spawns remain."""
        self._prune_inactive_enemies()
        return not self.enemies_alive and not self.spawn_queue

    def get_wave_reward(self) -> int:
        """Return the base FC reward for clearing the current wave."""
        return BASE_WAVE_REWARD + self.current_wave * WAVE_REWARD_SCALE + self.map_number * MAP_REWARD_SCALE

    def _build_spawn_queue(self, wave_num: int) -> list[SpawnEntry]:
        """Create spawn entries for enemies and a final-wave boss when needed."""
        enemy_types = self._get_enemy_types_for_wave(wave_num)
        formation_wave_arg = self._get_formation_wave_arg(wave_num)
        queue = [
            self._create_spawn_entry(enemy_type, spawn_index, formation_wave_arg)
            for spawn_index, enemy_type in enumerate(enemy_types)
        ]

        if wave_num == int(self.map_config["waves"]):
            boss_type = str(self.map_config["boss"])
            boss_entry = self._create_spawn_entry(boss_type, len(queue), formation_wave_arg)
            boss_entry["boss_phases"] = int(self.map_config["boss_phases"])
            queue.append(boss_entry)

        return queue

    def _get_enemy_types_for_wave(self, wave_num: int) -> list[str]:
        """Choose a deterministic enemy mix for this map and wave."""
        if self._is_map_one_wave_one(wave_num):
            return [CHICKEN_GRUNT_TYPE for _ in range(MAP_ONE_WAVE_ONE_ENEMY_COUNT)]

        map_bonus = (self.map_number - FIRST_MAP_INDEX) * ENEMY_COUNT_PER_MAP
        raw_enemy_count = max(MIN_TWO_ROW_ENEMY_COUNT, BASE_ENEMY_COUNT + wave_num * ENEMY_COUNT_PER_WAVE + map_bonus)
        enemy_count = _fill_grid_count(raw_enemy_count)
        allowed_types = tuple(self.map_config["allowed_types"])
        tier_two_percent = self._get_tier_two_percent(wave_num)
        enemy_types: list[str] = []

        for spawn_index in range(enemy_count):
            if self._should_spawn_tier_two(spawn_index, tier_two_percent, allowed_types):
                enemy_types.append(self._pick_tier_two_type(spawn_index, allowed_types))
            else:
                enemy_types.append(TIER_ONE_TYPES[spawn_index % len(TIER_ONE_TYPES)])

        return enemy_types

    def _get_tier_two_percent(self, wave_num: int) -> int:
        """Return the Tier 2 spawn percentage after higher waves unlock them."""
        if wave_num < TIER_TWO_START_WAVE:
            return MIN_HEALTH
        return int(self.map_config["tier_two_percent"])

    def _should_spawn_tier_two(self, spawn_index: int, tier_two_percent: int, allowed_types: tuple[str, ...]) -> bool:
        """Return whether a spawn slot should use a Tier 2 enemy."""
        if tier_two_percent <= MIN_HEALTH:
            return False
        if not any(enemy_type in allowed_types for enemy_type in TIER_TWO_TYPES):
            return False
        return (spawn_index * PERCENT_MAX // max(FIRST_MAP_INDEX, BASE_ENEMY_COUNT)) % PERCENT_MAX < tier_two_percent

    def _pick_tier_two_type(self, spawn_index: int, allowed_types: tuple[str, ...]) -> str:
        """Pick an allowed Tier 2 type while respecting map-specific restrictions."""
        available_tier_two = [enemy_type for enemy_type in TIER_TWO_TYPES if enemy_type in allowed_types]
        if not available_tier_two:
            return TIER_ONE_TYPES[spawn_index % len(TIER_ONE_TYPES)]
        return available_tier_two[spawn_index % len(available_tier_two)]

    def _create_spawn_entry(self, enemy_type: str, spawn_index: int, formation_wave_arg: int) -> SpawnEntry:
        """Create one spawn queue record with staggered formation coordinates."""
        base_x = self._get_base_spawn_x()
        formation_offset = self._get_formation_offset(spawn_index)
        spawn_x = base_x + formation_offset[0]
        if self._is_map_one_wave_one(self.current_wave):
            spawn_y = MAP_ONE_WAVE_ONE_SPAWN_Y + (spawn_index // FORMATIONS_PER_ROW) * MAP_ONE_WAVE_ONE_ROW_SPACING
        else:
            spawn_y = SPAWN_Y + (spawn_index // FORMATIONS_PER_ROW) * FORMATION_Y_SPACING
        return {
            "timer": BASE_SPAWN_DELAY_SECONDS + spawn_index * SPAWN_STAGGER_SECONDS,
            "enemy_type": enemy_type,
            "x": spawn_x,
            "base_x": base_x,
            "y": spawn_y,
            "formation_offset": formation_offset,
            "formation_wave_arg": formation_wave_arg,
            "wave_num": self.current_wave,
            "spawn_index": spawn_index,
        }

    def _spawn_enemy(self, entry: SpawnEntry) -> Enemy:
        """Instantiate an enemy for a ready spawn queue entry."""
        enemy_type = str(entry["enemy_type"])
        factory = self._get_enemy_factory(enemy_type)
        enemy = factory(
            float(entry["x"]),
            float(entry["y"]),
            int(entry["formation_wave_arg"]),
            entry["formation_offset"],  # type: ignore[arg-type]
        )
        self._apply_map_stats(enemy, enemy_type)
        enemy.map_number = self.map_number
        enemy.wave_num = self.current_wave
        enemy.spawn_x = float(entry["base_x"])
        enemy.spawn_y = float(entry["y"])
        enemy.formation_anchor_x = float(entry["x"])
        enemy.formation_anchor_y = float(entry["y"])
        enemy.formation_offset = entry["formation_offset"]
        enemy.coordinated_formation_enemy = (
            enemy_type in FORMATION_ENEMY_TYPES
            and not getattr(enemy, "health_bar_visible", False)
        )
        attack_cooldown_scale = self._get_attack_cooldown_scale()
        if self._is_map_one_wave_one(self.current_wave):
            attack_cooldown_scale = max(attack_cooldown_scale, MAP_ONE_WAVE_ONE_ATTACK_COOLDOWN_SCALE)
        enemy.attack_cooldown_scale = attack_cooldown_scale
        if float(getattr(enemy, "attack_cooldown", 0.0)) > BASE_SPAWN_DELAY_SECONDS:
            enemy.attack_cooldown *= attack_cooldown_scale
        if self._is_map_one_wave_one(self.current_wave):
            enemy.attack_cooldown = 0.75 + (int(entry["spawn_index"]) % FORMATIONS_PER_ROW) * 0.18
        if "boss_phases" in entry:
            enemy.phase_count = int(entry["boss_phases"])
        return enemy

    def _get_enemy_factory(self, enemy_type: str) -> EnemyFactory:
        """Return the constructor wrapper for a configured enemy type."""
        factories: dict[str, EnemyFactory] = {
            CHICKEN_GRUNT_TYPE: lambda x, y, wave_num, offset: ChickenGrunt(x, y, wave_num, offset),
            EGG_BOMBER_TYPE: lambda x, y, wave_num, offset: EggBomber(x, y, wave_num, offset),
            KAMIKAZE_TYPE: lambda x, y, wave_num, offset: KamikazeChicken(x, y),
            ARMORED_ROOSTER_TYPE: lambda x, y, wave_num, offset: ArmoredRooster(x, y),
            DODGE_HEN_TYPE: lambda x, y, wave_num, offset: DodgeHen(x, y),
            SPACE_ROOSTER_TYPE: lambda x, y, wave_num, offset: SpaceRooster(x, y),
            CHICKEN_OVERLORD_TYPE: lambda x, y, wave_num, offset: ChickenOverlord(x, y),
        }
        return factories[enemy_type]

    def _apply_map_stats(self, enemy: object, enemy_type: str) -> None:
        """Apply map-specific JSON stats to spawned enemies."""
        stats = self.enemy_config.get(enemy_type, {})
        hp = stats.get("hp")
        speed = stats.get("speed")
        fc_drop = stats.get("fc_drop")

        if hp is not None:
            enemy.hp = int(hp)
            enemy.max_hp = int(hp)
        if speed is not None:
            enemy.map_speed = float(speed)
        if fc_drop is not None:
            enemy.fc_drop_min = int(fc_drop)
            enemy.fc_drop_max = int(fc_drop)

    def _prune_inactive_enemies(self) -> None:
        """Remove enemies that have been marked inactive by combat systems."""
        self.enemies_alive = [enemy for enemy in self.enemies_alive if getattr(enemy, "active", False)]

    def _update_alive_enemies(self, dt: float) -> None:
        """Update live enemies and enroll newly summoned boss minions."""
        spawned_minions: list[Enemy] = []
        for enemy in list(self.enemies_alive):
            if not getattr(enemy, "active", False):
                continue

            if getattr(enemy, "coordinated_formation_enemy", False):
                enemy.update_debuffs(dt)
                self._move_enemy_in_coordinated_formation(enemy)
                enemy.last_attack_bullets = enemy.attack(dt)
            else:
                if self._despawn_if_missed_dive(enemy):
                    continue
                enemy.update(dt)
                if self._despawn_if_missed_dive(enemy):
                    continue
                self._clamp_enemy_to_screen(enemy)
            if isinstance(enemy, ChickenOverlord):
                spawned_minions.extend(enemy.newly_summoned_minions)
                enemy.newly_summoned_minions = []

        for minion in spawned_minions:
            self._prepare_summoned_minion(minion)
            self.enemies_alive.append(minion)

    def _prepare_summoned_minion(self, minion: Enemy) -> None:
        """Attach wave metadata so summoned minions enter the normal enemy lifecycle."""
        minion.map_number = self.map_number
        minion.wave_num = self.current_wave
        minion.spawn_x = minion.x
        minion.spawn_y = minion.y
        minion.formation_anchor_x = minion.x
        minion.formation_anchor_y = minion.y
        minion.coordinated_formation_enemy = isinstance(minion, (ChickenGrunt, EggBomber))

    def _move_enemy_in_coordinated_formation(self, enemy: Enemy) -> None:
        """Move a regular enemy with the wave group, clamped inside the screen."""
        anchor_x = float(getattr(enemy, "formation_anchor_x", enemy.x))
        anchor_y = float(getattr(enemy, "formation_anchor_y", enemy.y))
        x_offset = sin(self.formation_time * FORMATION_SWAY_X_RATE) * FORMATION_SWAY_X
        y_offset = sin(self.formation_time * FORMATION_SWAY_Y_RATE) * FORMATION_SWAY_Y
        max_x = SCREEN_WIDTH - FORMATION_RIGHT_MARGIN - enemy.width
        max_y = SCREEN_HEIGHT * FORMATION_BOTTOM_RATIO
        enemy.x = _clamp(anchor_x + x_offset, FORMATION_LEFT_MARGIN, max_x)
        enemy.y = _clamp(anchor_y + y_offset, FORMATION_TOP_MARGIN, max_y)

    def _clamp_enemy_to_screen(self, enemy: Enemy) -> None:
        """Keep enemy-specific movement inside the visible play area."""
        max_x = SCREEN_WIDTH - enemy.width
        max_y = SCREEN_HEIGHT - enemy.height
        enemy.x = _clamp(enemy.x, MIN_HEALTH, max_x)
        enemy.y = _clamp(enemy.y, MIN_HEALTH, max_y)

    def _despawn_if_missed_dive(self, enemy: Enemy) -> bool:
        """Deactivate ramming enemies that dive past the bottom edge."""
        if int(getattr(enemy, "collision_damage", MIN_HEALTH)) <= MIN_HEALTH:
            return False
        if enemy.y < SCREEN_HEIGHT:
            return False

        enemy.hp = MIN_HEALTH
        enemy.active = False
        return True

    def _get_formation_wave_arg(self, wave_num: int) -> int:
        """Convert wave ranges into the formation selector used by enemy movement."""
        if wave_num <= V_FORMATION_MAX_WAVE:
            return V_FORMATION_WAVE_ARG
        if wave_num <= GRID_FORMATION_MAX_WAVE:
            return GRID_FORMATION_WAVE_ARG
        return SPIRAL_FORMATION_WAVE_ARG

    def _get_formation_offset(self, spawn_index: int) -> FormationOffset:
        """Return staggered formation offset for V, grid, or spiral layouts."""
        column = spawn_index % FORMATIONS_PER_ROW
        row = spawn_index // FORMATIONS_PER_ROW
        centered_column = column - (FORMATIONS_PER_ROW - FORMATION_CENTER_INDEX_OFFSET) / FORMATION_CENTER_DIVISOR
        return centered_column * FORMATION_X_SPACING, row * FORMATION_Y_SPACING

    def _get_base_spawn_x(self) -> float:
        """Return the horizontal center used as the base spawn position."""
        return SCREEN_WIDTH / FORMATION_CENTER_DIVISOR

    def _get_attack_cooldown_scale(self) -> float:
        """Return the wave/map-based multiplier that spaces out enemy shots."""
        scale = (
            BASE_ATTACK_COOLDOWN_SCALE
            + (self.map_number - FIRST_MAP_INDEX) * MAP_ATTACK_COOLDOWN_SCALE
            + (self.current_wave - FIRST_MAP_INDEX) * WAVE_ATTACK_COOLDOWN_SCALE
        )
        return min(MAX_ATTACK_COOLDOWN_SCALE, scale)

    def _load_enemy_config(self, map_number: int) -> dict[str, dict[str, int | float]]:
        """Load map-specific enemy stats from the JSON data file."""
        with ENEMY_STATS_PATH.open("r", encoding="utf-8") as stats_file:
            all_stats = load(stats_file)
        return dict(all_stats[f"map_{map_number}"])

    def _is_map_one_wave_one(self, wave_num: int) -> bool:
        """Return whether the requested wave uses the opening encounter tuning."""
        return self.map_number == FIRST_MAP_INDEX and wave_num == FIRST_MAP_INDEX


def _clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a formation coordinate into the visible combat region."""
    return max(minimum, min(maximum, value))


def _fill_grid_count(enemy_count: int) -> int:
    """Round enemy count up so the final formation row is fully populated."""
    remainder = enemy_count % FORMATIONS_PER_ROW
    if remainder == 0:
        return enemy_count
    return enemy_count + FORMATIONS_PER_ROW - remainder
