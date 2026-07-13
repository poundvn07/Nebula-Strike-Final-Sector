"""Chicken Overlord boss enemy implementation."""

from __future__ import annotations

from random import randint

from src.entities.bullet import Bullet
from src.entities.pickup import Pickup
from src.enemies.chicken_grunt import ChickenGrunt
from src.enemies.enemy import Enemy
from src.utils.constants import SCREEN_WIDTH

CHICKEN_OVERLORD_WIDTH = 143
CHICKEN_OVERLORD_HEIGHT = 154
CHICKEN_OVERLORD_HP = 900
CHICKEN_OVERLORD_SPEED = 26.0
CHICKEN_OVERLORD_SCORE_VALUE = 2500
CHICKEN_OVERLORD_FC_DROP_MIN = 30
CHICKEN_OVERLORD_FC_DROP_MAX = 50
CHICKEN_OVERLORD_MAX_MINIONS = 4
CHICKEN_OVERLORD_HEAL_PER_MINION_ALIVE = 2.0
CHICKEN_OVERLORD_SUMMON_INTERVAL_SECONDS = 30.0
CHICKEN_OVERLORD_ATTACK_INTERVAL_SECONDS = 2.6
CHICKEN_OVERLORD_SPREAD_SPEED = 135.0
CHICKEN_OVERLORD_SPREAD_SIDE_VX = 72.0
CHICKEN_OVERLORD_SPREAD_DAMAGE = 14
CHICKEN_OVERLORD_BEAM_SPEED = 205.0
CHICKEN_OVERLORD_BEAM_DAMAGE = 22
CHICKEN_OVERLORD_BEAM_WIDTH = 20
CHICKEN_OVERLORD_BEAM_HEIGHT = 78
CHICKEN_OVERLORD_BEAM_MINION_THRESHOLD = 2
CHICKEN_OVERLORD_PATROL_RADIUS = 150.0
CHICKEN_OVERLORD_CENTER_VX = 0.0
CHICKEN_OVERLORD_STRATEGY_HINT = "Killing minions first stops the healing."
MINION_WAVE_NUM = 1
MINION_FORMATION_OFFSETS = (
    (-64.0, 42.0),
    (64.0, 42.0),
    (-104.0, 92.0),
    (104.0, 92.0),
)


class ChickenOverlord(Enemy):
    """Tier 3 boss Enemy that composes ChickenGrunt minions for healing pressure."""

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        """Initialize the map 4-5 boss with minion tracking and visible boss HP."""
        super().__init__(
            x=x,
            y=y,
            width=CHICKEN_OVERLORD_WIDTH,
            height=CHICKEN_OVERLORD_HEIGHT,
            hp=CHICKEN_OVERLORD_HP,
            vx=CHICKEN_OVERLORD_SPEED,
            vy=0.0,
            fc_drop_min=CHICKEN_OVERLORD_FC_DROP_MIN,
            fc_drop_max=CHICKEN_OVERLORD_FC_DROP_MAX,
            score_value=CHICKEN_OVERLORD_SCORE_VALUE,
        )
        self.minions_alive: list[Enemy] = []
        self.max_minions = CHICKEN_OVERLORD_MAX_MINIONS
        self.heal_per_minion_alive = CHICKEN_OVERLORD_HEAL_PER_MINION_ALIVE
        self.health_bar_visible = True
        self.strategy_hint = CHICKEN_OVERLORD_STRATEGY_HINT
        self.patrol_origin_x = x
        self.summon_timer = 0.0
        self._initial_minions_summoned = False
        self.newly_summoned_minions: list[Enemy] = []
        self._spawn_reference_synced = False
        self._start_attack_cooldown(CHICKEN_OVERLORD_ATTACK_INTERVAL_SECONDS)

    def update(self, dt: float) -> None:
        """Advance movement, healing, summoning, and attacks for this boss."""
        self.update_debuffs(dt)
        self._sync_spawn_reference()
        if not self._initial_minions_summoned:
            self.newly_summoned_minions.extend(self.summon_minions())
            self._initial_minions_summoned = True

        self.summon_timer += dt
        if self.summon_timer >= CHICKEN_OVERLORD_SUMMON_INTERVAL_SECONDS:
            self.newly_summoned_minions.extend(self.summon_minions())
            self.summon_timer = 0.0

        self.move(dt)
        self.update_healing(dt)
        self.last_attack_bullets = self.attack(dt)

    def move(self, dt: float) -> None:
        """Override move() to keep the Overlord on a slow horizontal patrol."""
        self._sync_spawn_reference()
        self.x += self._current_base_speed() * self._patrol_direction() * dt
        self._bounce_inside_patrol_radius()

    def summon_minions(self) -> list[Enemy]:
        """Spawn ChickenGrunt minions in formation around the boss."""
        self._prune_minions()
        open_slots = max(0, self.max_minions - len(self.minions_alive))
        spawned_minions: list[Enemy] = []
        for offset in MINION_FORMATION_OFFSETS[:open_slots]:
            minion = ChickenGrunt(
                x=self.x + offset[0],
                y=self.y + offset[1],
                wave_num=MINION_WAVE_NUM,
                formation_offset=offset,
            )
            minion.source_boss = self.__class__.__name__
            spawned_minions.append(minion)

        self.minions_alive.extend(spawned_minions)
        return spawned_minions

    def update_healing(self, dt: float) -> None:
        """Heal based on living minions, capped at max HP."""
        self._prune_minions()
        healing = self.heal_per_minion_alive * len(self.minions_alive) * dt
        self.hp = min(self.max_hp, self.hp + healing)

    def attack(self, dt: float) -> list[Bullet]:
        """Override attack() to fire spread shots and a beam while minions live."""
        self._update_attack_cooldown(dt)
        if not self._can_attack():
            return []

        self._start_attack_cooldown(CHICKEN_OVERLORD_ATTACK_INTERVAL_SECONDS)
        bullets = self._spread_shots()
        if len(self.minions_alive) > CHICKEN_OVERLORD_BEAM_MINION_THRESHOLD:
            bullets.extend(self._beam_attack())
        return bullets

    def on_minion_death(self, minion: Enemy) -> None:
        """Remove a defeated minion from the healing list."""
        if minion in self.minions_alive:
            self.minions_alive.remove(minion)

    def on_death(self) -> list[Pickup]:
        """Override on_death() to drop configured Feather Cores."""
        drop_count = randint(int(self.fc_drop_min), int(self.fc_drop_max))
        return [self._create_feather_core(drop_index) for drop_index in range(drop_count)]

    def _current_base_speed(self) -> float:
        """Return map-configured speed when present, otherwise the default speed."""
        return float(getattr(self, "map_speed", CHICKEN_OVERLORD_SPEED))

    def _sync_spawn_reference(self) -> None:
        """Use the final spawned position as the patrol origin."""
        if self._spawn_reference_synced:
            return

        self.patrol_origin_x = float(getattr(self, "spawn_x", self.x))
        self.spawn_y = self.y
        self._spawn_reference_synced = True

    def _patrol_direction(self) -> float:
        """Return the current horizontal patrol direction."""
        return 1.0 if self.vx >= 0.0 else -1.0

    def _bounce_inside_patrol_radius(self) -> None:
        """Reverse patrol direction at the patrol radius or screen edge."""
        left_bound = max(0.0, self.patrol_origin_x - CHICKEN_OVERLORD_PATROL_RADIUS)
        right_bound = min(SCREEN_WIDTH - self.width, self.patrol_origin_x + CHICKEN_OVERLORD_PATROL_RADIUS)
        if self.x <= left_bound:
            self.x = left_bound
            self.vx = abs(self._current_base_speed())
        elif self.x >= right_bound:
            self.x = right_bound
            self.vx = -abs(self._current_base_speed())

    def _spread_shots(self) -> list[Bullet]:
        """Create the Overlord's standard spread attack."""
        return [
            self._create_enemy_bullet(
                vx=-CHICKEN_OVERLORD_SPREAD_SIDE_VX,
                vy=CHICKEN_OVERLORD_SPREAD_SPEED,
                damage=CHICKEN_OVERLORD_SPREAD_DAMAGE,
                metadata={"pattern": "overlord_spread_left"},
            ),
            self._create_enemy_bullet(
                vx=CHICKEN_OVERLORD_CENTER_VX,
                vy=CHICKEN_OVERLORD_SPREAD_SPEED,
                damage=CHICKEN_OVERLORD_SPREAD_DAMAGE,
                metadata={"pattern": "overlord_spread_center"},
            ),
            self._create_enemy_bullet(
                vx=CHICKEN_OVERLORD_SPREAD_SIDE_VX,
                vy=CHICKEN_OVERLORD_SPREAD_SPEED,
                damage=CHICKEN_OVERLORD_SPREAD_DAMAGE,
                metadata={"pattern": "overlord_spread_right"},
            ),
        ]

    def _beam_attack(self) -> list[Bullet]:
        """Create the minion-backed beam attack."""
        return [
            self._create_enemy_bullet(
                vx=CHICKEN_OVERLORD_CENTER_VX,
                vy=CHICKEN_OVERLORD_BEAM_SPEED,
                damage=CHICKEN_OVERLORD_BEAM_DAMAGE,
                width=CHICKEN_OVERLORD_BEAM_WIDTH,
                height=CHICKEN_OVERLORD_BEAM_HEIGHT,
                metadata={"pattern": "overlord_minion_beam"},
            )
        ]

    def _prune_minions(self) -> None:
        """Keep only active minions in the healing list."""
        self.minions_alive = [minion for minion in self.minions_alive if minion.is_alive()]
