"""Wave spawning system for Nebula Strike maps."""

from __future__ import annotations

from json import JSONDecodeError, load
from math import sin
from pathlib import Path
from typing import Callable, TypeAlias

from src.enemies.armored_rooster import ArmoredRooster
from src.enemies.chicken_grunt import ChickenGrunt
from src.enemies.chicken_overlord import ChickenOverlord
from src.enemies.dodge_hen import DodgeHen
from src.enemies.egg_bomber import EggBomber
from src.enemies.enemy import (
    GRID_FORMATION_PATTERN,
    SPIRAL_FORMATION_PATTERN,
    V_FORMATION_PATTERN,
    Enemy,
    FormationOffset,
)
from src.enemies.kamikaze import KamikazeChicken
from src.enemies.space_rooster import SpaceRooster
from src.utils.constants import FINAL_MAP_INDEX, FIRST_MAP_INDEX, MIN_HEALTH, SCREEN_HEIGHT, SCREEN_WIDTH

SpawnEntry: TypeAlias = dict[str, object]
WaveConfig: TypeAlias = dict[str, object]
EnemyFactory: TypeAlias = Callable[[float, float, int, FormationOffset], Enemy]

ENEMY_STATS_PATH = Path(__file__).resolve().parents[2] / "data" / "enemy_stats.json"
WAVE_CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "wave_config.json"
BASE_SPAWN_DELAY_SECONDS = 0.0
FORMATION_SPRITE_GAP = 6.0
BASE_WAVE_REWARD = 10
WAVE_REWARD_SCALE = 4
MAP_REWARD_SCALE = 2

CHICKEN_GRUNT_TYPE = "chicken_grunt"
EGG_BOMBER_TYPE = "egg_bomber"
KAMIKAZE_TYPE = "kamikaze"
ARMORED_ROOSTER_TYPE = "armored_rooster"
DODGE_HEN_TYPE = "dodge_hen"
SPACE_ROOSTER_TYPE = "space_rooster"
CHICKEN_OVERLORD_TYPE = "chicken_overlord"

KNOWN_ENEMY_TYPES = {
    CHICKEN_GRUNT_TYPE,
    EGG_BOMBER_TYPE,
    KAMIKAZE_TYPE,
    ARMORED_ROOSTER_TYPE,
    DODGE_HEN_TYPE,
    SPACE_ROOSTER_TYPE,
    CHICKEN_OVERLORD_TYPE,
}
FORMATION_MOVEMENT_ARGS = {
    "grid": GRID_FORMATION_PATTERN,
    "v": V_FORMATION_PATTERN,
    "spiral": SPIRAL_FORMATION_PATTERN,
}
FORMATION_LAYOUTS = {"grid", "chevron", "staggered", "wave", "diamond"}


def _load_json_object(path: Path) -> dict[str, object]:
    """Load a JSON object and report configuration errors clearly."""
    try:
        with path.open("r", encoding="utf-8") as config_file:
            data = load(config_file)
    except (OSError, JSONDecodeError) as exc:
        raise ValueError(f"Unable to load wave configuration from {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Wave configuration root must be an object: {path}")
    return data


_DEFAULT_WAVE_DATA = _load_json_object(WAVE_CONFIG_PATH)
_DEFAULT_FORMATIONS = _DEFAULT_WAVE_DATA["formations"]
_DEFAULT_OPENING_FORMATION = _DEFAULT_FORMATIONS["opening_grid"]  # type: ignore[index]
_DEFAULT_MAP_ONE = _DEFAULT_WAVE_DATA["maps"]["map_1"]  # type: ignore[index]
_DEFAULT_MAP_ONE_WAVE_ONE = _DEFAULT_MAP_ONE["waves"][0]  # type: ignore[index]

# Backward-compatible public values are derived from JSON instead of driving spawn logic.
FORMATIONS_PER_ROW = int(_DEFAULT_OPENING_FORMATION["columns"])  # type: ignore[index]
MAP_ONE_WAVE_ONE_SPAWN_Y = float(_DEFAULT_OPENING_FORMATION["origin"][1])  # type: ignore[index]
MAP_ONE_WAVE_ONE_ENEMY_COUNT = int(_DEFAULT_MAP_ONE_WAVE_ONE["enemy_count"])  # type: ignore[index]


class WaveManager:
    """Manages map-local waves by queuing and spawning polymorphic Enemy objects."""

    def __init__(self, map_number: int, wave_config_path: str | Path | None = None) -> None:
        """Load map enemy stats and initialize wave progression state."""
        if map_number < FIRST_MAP_INDEX or map_number > FINAL_MAP_INDEX:
            raise ValueError("map_number must be between 1 and 5")

        self.map_number = map_number
        config_path = Path(wave_config_path) if wave_config_path is not None else WAVE_CONFIG_PATH
        self.wave_data = _load_json_object(config_path)
        self.formations = self._load_formations(config_path)
        self.wave_definitions = self._load_map_waves(config_path)
        final_boss = self.wave_definitions[-1].get("boss", {})
        if not isinstance(final_boss, dict):
            final_boss = {}
        self.map_config = {
            "waves": len(self.wave_definitions),
            "boss": str(final_boss.get("type", "")),
            "boss_phases": int(final_boss.get("phases", 1)),
        }
        self.enemy_config = self._load_enemy_config(map_number)
        self.current_wave = MIN_HEALTH
        self.enemies_alive: list[Enemy] = []
        self.spawn_queue: list[SpawnEntry] = []
        self.wave_complete = False
        self.map_complete = False
        self.formation_time = BASE_SPAWN_DELAY_SECONDS
        self._last_formation_sway_offset = (0.0, 0.0)
        self.active_wave_config: WaveConfig = {}
        self.active_formation: WaveConfig = {}

    def start_wave(self, wave_num: int) -> None:
        """Build the spawn queue for the requested wave number."""
        max_waves = int(self.map_config["waves"])
        if wave_num < FIRST_MAP_INDEX or wave_num > max_waves:
            raise ValueError(f"wave_num must be between 1 and {max_waves}")

        self.current_wave = wave_num
        self.active_wave_config = self.wave_definitions[wave_num - FIRST_MAP_INDEX]
        formation_name = str(self.active_wave_config["formation"])
        self.active_formation = self.formations[formation_name]
        self.enemies_alive.clear()
        self.spawn_queue = self._build_spawn_queue(wave_num)
        self.wave_complete = False
        self.map_complete = False
        self.formation_time = BASE_SPAWN_DELAY_SECONDS
        self._last_formation_sway_offset = (0.0, 0.0)

    def spawn_pending_now(self) -> None:
        """Move every queued spawn into play so intro gating starts with a full wave."""
        ready_entries = list(self.spawn_queue)
        self.spawn_queue.clear()
        for entry in ready_entries:
            self.enemies_alive.append(self._spawn_enemy(entry))
        coordinated_enemies = [
            enemy
            for enemy in self.enemies_alive
            if getattr(enemy, "active", False)
            and getattr(enemy, "coordinated_formation_enemy", False)
        ]
        self._last_formation_sway_offset = self._move_enemies_in_coordinated_formation(coordinated_enemies)

    def should_spawn_all_on_intro(self) -> bool:
        """Return the active formation's JSON-configured intro spawn behavior."""
        return bool(self.active_formation["spawn_all_on_intro"])

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
        """Create spawn entries entirely from the selected JSON wave definition."""
        wave_config = self.wave_definitions[wave_num - FIRST_MAP_INDEX]
        enemy_types = self._expand_enemy_types(wave_config)
        queue = [
            self._create_spawn_entry(enemy_type, spawn_index, wave_config)
            for spawn_index, enemy_type in enumerate(enemy_types)
        ]

        boss_config = wave_config.get("boss")
        if isinstance(boss_config, dict):
            boss_type = str(boss_config["type"])
            boss_entry = self._create_spawn_entry(boss_type, len(queue), wave_config)
            boss_entry["boss_phases"] = int(boss_config.get("phases", 1))
            queue.append(boss_entry)

        return queue

    def _expand_enemy_types(self, wave_config: WaveConfig) -> list[str]:
        """Expand explicit enemy groups or a repeating JSON enemy pattern."""
        configured_enemies = wave_config.get("enemies")
        if configured_enemies is not None and not isinstance(configured_enemies, list):
            raise ValueError("enemies must be an array")
        if isinstance(configured_enemies, list):
            enemy_types: list[str] = []
            for configured_enemy in configured_enemies:
                if isinstance(configured_enemy, str):
                    enemy_types.append(configured_enemy)
                    continue
                if not isinstance(configured_enemy, dict):
                    raise ValueError("Each configured enemy must be a type name or an object")
                enemy_type = str(configured_enemy["type"])
                enemy_count = int(configured_enemy.get("count", 1))
                if enemy_count < 0:
                    raise ValueError("configured enemy count cannot be negative")
                enemy_types.extend([enemy_type] * enemy_count)
            return enemy_types

        enemy_count = int(wave_config["enemy_count"])
        if enemy_count < 0:
            raise ValueError("enemy_count cannot be negative")
        pattern = wave_config["enemy_pattern"]
        if not isinstance(pattern, list) or not pattern:
            raise ValueError("enemy_pattern must be a non-empty array")
        return [str(pattern[index % len(pattern)]) for index in range(enemy_count)]

    def _create_spawn_entry(self, enemy_type: str, spawn_index: int, wave_config: WaveConfig) -> SpawnEntry:
        """Create one spawn record using JSON coordinates and timing."""
        formation = self.formations[str(wave_config["formation"])]
        origin_x, origin_y = _number_pair(formation["origin"], "formation origin")
        positions = wave_config.get("positions")
        if positions is not None:
            if not isinstance(positions, list) or spawn_index >= len(positions):
                raise ValueError("wave positions must include one [x, y] pair for every enemy and boss")
            spawn_x, spawn_y = _number_pair(positions[spawn_index], "wave position")
            formation_offset = (spawn_x - origin_x, spawn_y - origin_y)
        else:
            formation_offset = _configured_formation_offset(formation, spawn_index)
            spawn_x = origin_x + formation_offset[0]
            spawn_y = origin_y + formation_offset[1]

        spawn_delay = float(formation["spawn_delay"])
        spawn_stagger = float(formation["spawn_stagger"])
        coordinated_types = formation["coordinated_types"]
        if not isinstance(coordinated_types, list):
            raise ValueError("formation coordinated_types must be an array")
        return {
            "timer": spawn_delay + spawn_index * spawn_stagger,
            "enemy_type": enemy_type,
            "x": spawn_x,
            "base_x": origin_x,
            "y": spawn_y,
            "formation_offset": formation_offset,
            "formation_wave_arg": FORMATION_MOVEMENT_ARGS[str(formation["movement"])],
            "coordinated": enemy_type in coordinated_types,
            "attack_cooldown_scale": float(wave_config.get("attack_cooldown_scale", 1.0)),
            "wave_num": self.current_wave,
            "spawn_index": spawn_index,
            **self._configured_attack_cooldown(wave_config, spawn_index, int(formation["columns"])),
        }

    def _configured_attack_cooldown(
        self,
        wave_config: WaveConfig,
        spawn_index: int,
        columns: int,
    ) -> SpawnEntry:
        """Return an optional per-column attack cooldown from JSON."""
        sequence = wave_config.get("attack_cooldown_sequence")
        if not isinstance(sequence, dict):
            return {}
        base = float(sequence["base"])
        step = float(sequence["step"])
        return {"attack_cooldown": base + (spawn_index % columns) * step}

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
            bool(entry["coordinated"])
            and not getattr(enemy, "health_bar_visible", False)
        )
        attack_cooldown_scale = float(entry["attack_cooldown_scale"])
        enemy.attack_cooldown_scale = attack_cooldown_scale
        if float(getattr(enemy, "attack_cooldown", 0.0)) > BASE_SPAWN_DELAY_SECONDS:
            enemy.attack_cooldown *= attack_cooldown_scale
        if "attack_cooldown" in entry:
            enemy.attack_cooldown = float(entry["attack_cooldown"])
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
        coordinated_enemies = [
            enemy
            for enemy in self.enemies_alive
            if getattr(enemy, "active", False)
            and getattr(enemy, "coordinated_formation_enemy", False)
        ]
        sway_offset = self._move_enemies_in_coordinated_formation(coordinated_enemies)
        self._translate_independent_enemies_with_sway(sway_offset)
        for enemy in list(self.enemies_alive):
            if not getattr(enemy, "active", False):
                continue

            if getattr(enemy, "coordinated_formation_enemy", False):
                enemy.update_debuffs(dt)
                enemy.last_attack_bullets = enemy.attack(dt)
            else:
                if self._despawn_if_missed_dive(enemy):
                    continue
                enemy.update(dt)
                if self._despawn_if_missed_dive(enemy):
                    continue
                self._clamp_enemy_to_formation_lane(enemy, sway_offset[0])
                self._clamp_enemy_to_screen(enemy)
            if isinstance(enemy, ChickenOverlord):
                spawned_minions.extend(enemy.newly_summoned_minions)
                enemy.newly_summoned_minions = []

        for minion in spawned_minions:
            self._prepare_summoned_minion(minion)
            self._place_summoned_minion_in_free_space(minion)
            self.enemies_alive.append(minion)
        if spawned_minions:
            coordinated_enemies = [
                enemy
                for enemy in self.enemies_alive
                if getattr(enemy, "active", False)
                and getattr(enemy, "coordinated_formation_enemy", False)
            ]
            self._move_enemies_in_coordinated_formation(coordinated_enemies)

    def _prepare_summoned_minion(self, minion: Enemy) -> None:
        """Attach wave metadata so summoned minions enter the normal enemy lifecycle."""
        minion.map_number = self.map_number
        minion.wave_num = self.current_wave
        minion.spawn_x = minion.x
        minion.spawn_y = minion.y
        minion.formation_offset = (0.0, 0.0)
        minion.stationary_wave_enemy = True
        sway_x, sway_y = self._last_formation_sway_offset
        minion.formation_anchor_x = minion.x - sway_x
        minion.formation_anchor_y = minion.y - sway_y
        minion.coordinated_formation_enemy = False

    def _place_summoned_minion_in_free_space(self, minion: Enemy) -> None:
        """Move a boss-summoned minion to the nearest unoccupied sprite position."""
        other_enemies = [
            enemy
            for enemy in self.enemies_alive
            if getattr(enemy, "active", False)
            and not getattr(enemy, "health_bar_visible", False)
        ]
        if not other_enemies:
            return
        original_x = float(minion.x)
        original_y = float(minion.y)
        x_candidates = {original_x}
        y_candidates = {original_y}
        for enemy in other_enemies:
            x_candidates.add(float(enemy.x) - FORMATION_SPRITE_GAP - minion.width)
            x_candidates.add(float(enemy.x) + enemy.width + FORMATION_SPRITE_GAP)
            y_candidates.add(float(enemy.y) - FORMATION_SPRITE_GAP - minion.height)
            y_candidates.add(float(enemy.y) + enemy.height + FORMATION_SPRITE_GAP)
        candidates = sorted(
            ((x, y) for x in x_candidates for y in y_candidates),
            key=lambda position: (position[0] - original_x) ** 2 + (position[1] - original_y) ** 2,
        )
        for candidate_x, candidate_y in candidates:
            if not (
                MIN_HEALTH <= candidate_x <= SCREEN_WIDTH - minion.width
                and MIN_HEALTH <= candidate_y <= SCREEN_HEIGHT - minion.height
            ):
                continue
            candidate_rect = (candidate_x, candidate_y, minion.width, minion.height)
            if any(
                _formation_rects_overlap(
                    candidate_rect,
                    (enemy.x, enemy.y, enemy.width, enemy.height),
                    FORMATION_SPRITE_GAP,
                )
                for enemy in other_enemies
            ):
                continue
            minion.x = candidate_x
            minion.y = candidate_y
            minion.spawn_x = candidate_x
            minion.spawn_y = candidate_y
            sway_x, sway_y = self._last_formation_sway_offset
            minion.formation_anchor_x = candidate_x - sway_x
            minion.formation_anchor_y = candidate_y - sway_y
            return

    def _move_enemies_in_coordinated_formation(self, enemies: list[Enemy]) -> tuple[float, float]:
        """Sway a formation as one group so boundary clamping cannot stack enemies."""
        if not enemies:
            return self._last_formation_sway_offset
        self._ensure_non_overlapping_formation_anchors(enemies)
        sway = self.active_formation["sway"]
        bounds = self.active_formation["bounds"]
        if not isinstance(sway, dict) or not isinstance(bounds, dict):
            raise ValueError("formation sway and bounds must be objects")

        desired_x_offset = sin(self.formation_time * float(sway["x_rate"])) * float(sway["x"])
        desired_y_offset = sin(self.formation_time * float(sway["y_rate"])) * float(sway["y"])
        left_bound = float(bounds["left"])
        right_bound = SCREEN_WIDTH - float(bounds["right"])
        top_bound = float(bounds["top"])
        bottom_bound = SCREEN_HEIGHT * float(bounds["bottom_ratio"])

        minimum_x_offset = max(
            left_bound - float(getattr(enemy, "formation_anchor_x", enemy.x))
            for enemy in enemies
        )
        maximum_x_offset = min(
            right_bound - enemy.width - float(getattr(enemy, "formation_anchor_x", enemy.x))
            for enemy in enemies
        )
        minimum_y_offset = max(
            top_bound - float(getattr(enemy, "formation_anchor_y", enemy.y))
            for enemy in enemies
        )
        maximum_y_offset = min(
            bottom_bound - enemy.height - float(getattr(enemy, "formation_anchor_y", enemy.y))
            for enemy in enemies
        )
        x_offset = _clamp_group_offset(desired_x_offset, minimum_x_offset, maximum_x_offset)
        y_offset = _clamp_group_offset(desired_y_offset, minimum_y_offset, maximum_y_offset)

        for enemy in enemies:
            anchor_x = float(getattr(enemy, "formation_anchor_x", enemy.x))
            anchor_y = float(getattr(enemy, "formation_anchor_y", enemy.y))
            enemy.x = anchor_x + x_offset
            enemy.y = anchor_y + y_offset
        return x_offset, y_offset

    def _translate_independent_enemies_with_sway(self, sway_offset: tuple[float, float]) -> None:
        """Apply the same sway delta to specialists without replacing their behavior."""
        previous_x, previous_y = self._last_formation_sway_offset
        sway_x, sway_y = sway_offset
        delta_x = sway_x - previous_x
        delta_y = sway_y - previous_y
        for enemy in self.enemies_alive:
            if (
                not getattr(enemy, "active", False)
                or getattr(enemy, "coordinated_formation_enemy", False)
                or getattr(enemy, "health_bar_visible", False)
                or hasattr(enemy, "source_boss")
            ):
                continue
            enemy.x += delta_x
            enemy.y += delta_y
            if hasattr(enemy, "patrol_origin_x"):
                enemy.patrol_origin_x = float(enemy.patrol_origin_x) + delta_x
        self._last_formation_sway_offset = sway_offset

    def _clamp_enemy_to_formation_lane(self, enemy: Enemy, sway_x: float) -> None:
        """Keep specialist patrol motion inside its non-overlapping formation lane."""
        if (
            getattr(enemy, "health_bar_visible", False)
            or getattr(enemy, "coordinated_formation_enemy", False)
            or hasattr(enemy, "source_boss")
        ):
            return
        if int(getattr(enemy, "collision_damage", MIN_HEALTH)) > MIN_HEALTH and abs(float(enemy.vy)) > 0.0:
            return
        spacing_x, _ = _number_pair(self.active_formation["spacing"], "formation spacing")
        regular_enemies = [
            other_enemy
            for other_enemy in self.enemies_alive
            if getattr(other_enemy, "active", False)
            and not getattr(other_enemy, "health_bar_visible", False)
        ]
        widest_sprite = max((float(other_enemy.width) for other_enemy in regular_enemies), default=float(enemy.width))
        lane_drift = max(0.0, (spacing_x - widest_sprite - FORMATION_SPRITE_GAP) / 2.0)
        anchor_x = float(getattr(enemy, "formation_anchor_x", enemy.x - sway_x))
        local_x = enemy.x - sway_x
        clamped_local_x = _clamp(local_x, anchor_x - lane_drift, anchor_x + lane_drift)
        if clamped_local_x != local_x:
            enemy.vx = -float(enemy.vx)
        enemy.x = clamped_local_x + sway_x
        if hasattr(enemy, "patrol_origin_x"):
            enemy.patrol_origin_x = anchor_x + sway_x

    def _ensure_non_overlapping_formation_anchors(self, enemies: list[Enemy]) -> None:
        """Separate invalid or newly added anchors once before applying shared sway."""
        placed: list[tuple[float, float, float, float]] = []
        ordered_enemies = sorted(
            enemies,
            key=lambda enemy: (
                float(getattr(enemy, "formation_anchor_y", enemy.y)),
                float(getattr(enemy, "formation_anchor_x", enemy.x)),
            ),
        )
        for enemy in ordered_enemies:
            anchor_x = float(getattr(enemy, "formation_anchor_x", enemy.x))
            anchor_y = float(getattr(enemy, "formation_anchor_y", enemy.y))
            while True:
                overlapping = [
                    placed_rect
                    for placed_rect in placed
                    if _formation_rects_overlap(
                        (anchor_x, anchor_y, enemy.width, enemy.height),
                        placed_rect,
                        FORMATION_SPRITE_GAP,
                    )
                ]
                if not overlapping:
                    break
                anchor_y = max(rect_y + rect_height + FORMATION_SPRITE_GAP for _, rect_y, _, rect_height in overlapping)
            enemy.formation_anchor_x = anchor_x
            enemy.formation_anchor_y = anchor_y
            placed.append((anchor_x, anchor_y, enemy.width, enemy.height))


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

    def _load_formations(self, config_path: Path) -> dict[str, WaveConfig]:
        """Validate and return named formation presets from JSON."""
        raw_formations = self.wave_data.get("formations")
        if not isinstance(raw_formations, dict) or not raw_formations:
            raise ValueError(f"wave configuration must define formations: {config_path}")

        formations: dict[str, WaveConfig] = {}
        required_keys = {
            "columns",
            "origin",
            "spacing",
            "movement",
            "spawn_delay",
            "spawn_stagger",
            "spawn_all_on_intro",
            "coordinated_types",
            "sway",
            "bounds",
        }
        for formation_name, raw_formation in raw_formations.items():
            if not isinstance(raw_formation, dict):
                raise ValueError(f"formation {formation_name!r} must be an object")
            missing_keys = required_keys.difference(raw_formation)
            if missing_keys:
                raise ValueError(f"formation {formation_name!r} is missing: {', '.join(sorted(missing_keys))}")
            if int(raw_formation["columns"]) <= 0:
                raise ValueError(f"formation {formation_name!r} columns must be positive")
            movement = str(raw_formation["movement"])
            if movement not in FORMATION_MOVEMENT_ARGS:
                raise ValueError(f"formation {formation_name!r} has unknown movement {movement!r}")
            layout = str(raw_formation.get("layout", "grid"))
            if layout not in FORMATION_LAYOUTS:
                raise ValueError(f"formation {formation_name!r} has unknown layout {layout!r}")
            layout_options = raw_formation.get("layout_options", {})
            if not isinstance(layout_options, dict):
                raise ValueError(f"formation {formation_name!r} layout_options must be an object")
            for option_value in layout_options.values():
                float(option_value)
            spawn_delay = float(raw_formation["spawn_delay"])
            spawn_stagger = float(raw_formation["spawn_stagger"])
            if spawn_delay < 0.0 or spawn_stagger < 0.0:
                raise ValueError(f"formation {formation_name!r} spawn timing cannot be negative")
            if not isinstance(raw_formation["spawn_all_on_intro"], bool):
                raise ValueError(f"formation {formation_name!r} spawn_all_on_intro must be true or false")
            _number_pair(raw_formation["origin"], f"formation {formation_name} origin")
            _number_pair(raw_formation["spacing"], f"formation {formation_name} spacing")
            coordinated_types = raw_formation["coordinated_types"]
            if not isinstance(coordinated_types, list):
                raise ValueError(f"formation {formation_name!r} coordinated_types must be an array")
            unknown_types = {str(enemy_type) for enemy_type in coordinated_types}.difference(KNOWN_ENEMY_TYPES)
            if unknown_types:
                raise ValueError(f"formation {formation_name!r} has unknown enemy types: {sorted(unknown_types)}")
            self._validate_motion_config(formation_name, raw_formation)
            formation = dict(raw_formation)
            formation["layout"] = layout
            formation["layout_options"] = dict(layout_options)
            formations[str(formation_name)] = formation
        return formations

    def _validate_motion_config(self, formation_name: object, formation: WaveConfig) -> None:
        """Validate formation sway and screen bounds objects."""
        sway = formation["sway"]
        bounds = formation["bounds"]
        if not isinstance(sway, dict) or not {"x", "y", "x_rate", "y_rate"}.issubset(sway):
            raise ValueError(f"formation {formation_name!r} has an invalid sway object")
        if not isinstance(bounds, dict) or not {"top", "bottom_ratio", "left", "right"}.issubset(bounds):
            raise ValueError(f"formation {formation_name!r} has an invalid bounds object")
        for value in (*sway.values(), *bounds.values()):
            float(value)

    def _load_map_waves(self, config_path: Path) -> list[WaveConfig]:
        """Validate and return this map's ordered JSON wave definitions."""
        maps = self.wave_data.get("maps")
        map_key = f"map_{self.map_number}"
        if not isinstance(maps, dict) or not isinstance(maps.get(map_key), dict):
            raise ValueError(f"wave configuration does not define {map_key}: {config_path}")
        raw_waves = maps[map_key].get("waves")
        if not isinstance(raw_waves, list) or not raw_waves:
            raise ValueError(f"{map_key} must contain a non-empty waves array")

        waves: list[WaveConfig] = []
        for wave_number, raw_wave in enumerate(raw_waves, start=FIRST_MAP_INDEX):
            if not isinstance(raw_wave, dict):
                raise ValueError(f"{map_key} wave {wave_number} must be an object")
            wave = dict(raw_wave)
            formation_name = str(wave.get("formation", ""))
            if formation_name not in self.formations:
                raise ValueError(f"{map_key} wave {wave_number} references unknown formation {formation_name!r}")
            enemy_types = self._expand_enemy_types(wave)
            unknown_types = set(enemy_types).difference(KNOWN_ENEMY_TYPES)
            if unknown_types:
                raise ValueError(f"{map_key} wave {wave_number} has unknown enemy types: {sorted(unknown_types)}")
            boss = wave.get("boss")
            if boss is not None:
                if not isinstance(boss, dict) or str(boss.get("type", "")) not in KNOWN_ENEMY_TYPES:
                    raise ValueError(f"{map_key} wave {wave_number} has an invalid boss")
                if int(boss.get("phases", 1)) <= 0:
                    raise ValueError(f"{map_key} wave {wave_number} boss phases must be positive")
            float(wave.get("attack_cooldown_scale", 1.0))
            attack_sequence = wave.get("attack_cooldown_sequence")
            if attack_sequence is not None:
                if not isinstance(attack_sequence, dict) or not {"base", "step"}.issubset(attack_sequence):
                    raise ValueError(f"{map_key} wave {wave_number} has an invalid attack cooldown sequence")
                float(attack_sequence["base"])
                float(attack_sequence["step"])
            positions = wave.get("positions")
            required_positions = len(enemy_types) + (1 if isinstance(boss, dict) else 0)
            if positions is not None:
                if not isinstance(positions, list) or len(positions) < required_positions:
                    raise ValueError(f"{map_key} wave {wave_number} needs {required_positions} positions")
                for position in positions[:required_positions]:
                    _number_pair(position, f"{map_key} wave {wave_number} position")
            waves.append(wave)
        return waves

    def _load_enemy_config(self, map_number: int) -> dict[str, dict[str, int | float]]:
        """Load map-specific enemy stats from the JSON data file."""
        with ENEMY_STATS_PATH.open("r", encoding="utf-8") as stats_file:
            all_stats = load(stats_file)
        return dict(all_stats[f"map_{map_number}"])


def _clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a formation coordinate into the visible combat region."""
    return max(minimum, min(maximum, value))


def _clamp_group_offset(value: float, minimum: float, maximum: float) -> float:
    """Clamp one shared offset, preserving spacing even if a group exceeds its bounds."""
    if minimum > maximum:
        return (minimum + maximum) / 2.0
    return _clamp(value, minimum, maximum)


def _formation_rects_overlap(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
    gap: float,
) -> bool:
    """Return whether two formation sprite bounds violate the requested gap."""
    first_x, first_y, first_width, first_height = first
    second_x, second_y, second_width, second_height = second
    return (
        first_x < second_x + second_width + gap
        and first_x + first_width + gap > second_x
        and first_y < second_y + second_height + gap
        and first_y + first_height + gap > second_y
    )


def _number_pair(value: object, label: str) -> tuple[float, float]:
    """Validate and convert a JSON [x, y] numeric pair."""
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must be a two-number array")
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a two-number array") from exc


def _configured_formation_offset(formation: WaveConfig, spawn_index: int) -> tuple[float, float]:
    """Return a JSON-selected non-overlapping layout offset for one spawn."""
    columns = int(formation["columns"])
    spacing_x, spacing_y = _number_pair(formation["spacing"], "formation spacing")
    layout = str(formation.get("layout", "grid"))
    options = formation.get("layout_options", {})
    if not isinstance(options, dict):
        raise ValueError("formation layout_options must be an object")
    column = spawn_index % columns
    row = spawn_index // columns
    centered_column = column - (columns - 1) / 2.0

    if layout == "chevron":
        depth = float(options.get("depth", 0.55))
        return centered_column * spacing_x, row * spacing_y + abs(centered_column) * spacing_y * depth
    if layout == "staggered":
        row_offset = float(options.get("row_offset", 0.5))
        stagger = spacing_x * row_offset if row % 2 else 0.0
        return centered_column * spacing_x + stagger, row * spacing_y
    if layout == "wave":
        amplitude = float(options.get("amplitude", spacing_y * 0.35))
        cycles = float(options.get("cycles", 1.0))
        progress = column / max(1, columns - 1)
        wave_y = sin(progress * cycles * 6.283185307179586) * amplitude
        return centered_column * spacing_x, row * spacing_y + wave_y
    if layout == "diamond":
        diamond_x, diamond_y = _diamond_lattice_position(spawn_index)
        return diamond_x * spacing_x, diamond_y * spacing_y
    return centered_column * spacing_x, row * spacing_y


def _diamond_lattice_position(spawn_index: int) -> tuple[int, int]:
    """Return the indexed point of an expanding Manhattan-distance diamond."""
    if spawn_index == 0:
        return 0, 0
    points: list[tuple[int, int]] = [(0, 0)]
    radius = 1
    while len(points) <= spawn_index:
        ring: list[tuple[int, int]] = []
        for x_position in range(-radius, radius + 1):
            y_distance = radius - abs(x_position)
            ring.append((x_position, -y_distance))
            if y_distance:
                ring.append((x_position, y_distance))
        ring.sort(key=lambda point: (point[1], point[0]))
        points.extend(ring)
        radius += 1
    return points[spawn_index]
