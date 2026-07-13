"""Space Rooster boss enemy implementation."""

from __future__ import annotations

from math import cos, sin
from random import randint

from src.entities.bullet import Bullet
from src.entities.pickup import Pickup
from src.enemies.enemy import Enemy
from src.utils.constants import SCREEN_WIDTH

SPACE_ROOSTER_WIDTH = 122
SPACE_ROOSTER_HEIGHT = 122
SPACE_ROOSTER_HP = 350
SPACE_ROOSTER_BASE_SPEED = 26.0
SPACE_ROOSTER_SCORE_VALUE = 1500
SPACE_ROOSTER_FC_DROP_MIN = 30
SPACE_ROOSTER_FC_DROP_MAX = 50
SPACE_ROOSTER_PHASE_TWO_HP_RATIO = 0.66
SPACE_ROOSTER_PHASE_THREE_HP_RATIO = 0.33
SPACE_ROOSTER_PHASE_ONE_SPEED_MULTIPLIER = 1.0
SPACE_ROOSTER_PHASE_TWO_SPEED_MULTIPLIER = 1.15
SPACE_ROOSTER_PHASE_THREE_SPEED_MULTIPLIER = 1.25
SPACE_ROOSTER_PHASE_ONE_ATTACK_INTERVAL_SECONDS = 2.4
SPACE_ROOSTER_PHASE_TWO_ATTACK_INTERVAL_SECONDS = 2.4
SPACE_ROOSTER_PHASE_THREE_ATTACK_INTERVAL_SECONDS = 1.4
SPACE_ROOSTER_PATROL_RADIUS = 160.0
SPACE_ROOSTER_ERRATIC_X_RADIUS = 140.0
SPACE_ROOSTER_ERRATIC_Y_RADIUS = 28.0
SPACE_ROOSTER_ERRATIC_X_FREQUENCY = 2.5
SPACE_ROOSTER_ERRATIC_Y_FREQUENCY = 4.0
SPACE_ROOSTER_PROJECTILE_SPEED = 130.0
SPACE_ROOSTER_DIAGONAL_SPEED = 72.0
SPACE_ROOSTER_BEAM_SPEED = 190.0
SPACE_ROOSTER_RAPID_SPEED = 155.0
SPACE_ROOSTER_SPREAD_DAMAGE = 12
SPACE_ROOSTER_BEAM_DAMAGE = 20
SPACE_ROOSTER_RAPID_DAMAGE = 8
SPACE_ROOSTER_BEAM_WIDTH = 18
SPACE_ROOSTER_BEAM_HEIGHT = 72
SPACE_ROOSTER_RAPID_WIDTH = 6
SPACE_ROOSTER_RAPID_HEIGHT = 12
SPACE_ROOSTER_CENTER_VX = 0.0
PHASE_ONE = 1
PHASE_TWO = 2
PHASE_THREE = 3
ATTACK_SPREAD = 0
ATTACK_BEAM = 1
ATTACK_RAPID = 2
PHASE_THREE_ATTACK_TYPE_COUNT = 3


class SpaceRooster(Enemy):
    """Tier 3 boss Enemy that overrides movement and attacks across three phases."""

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        """Initialize the map 1-3 boss with phase thresholds and visible boss HP."""
        super().__init__(
            x=x,
            y=y,
            width=SPACE_ROOSTER_WIDTH,
            height=SPACE_ROOSTER_HEIGHT,
            hp=SPACE_ROOSTER_HP,
            vx=SPACE_ROOSTER_BASE_SPEED,
            vy=0.0,
            fc_drop_min=SPACE_ROOSTER_FC_DROP_MIN,
            fc_drop_max=SPACE_ROOSTER_FC_DROP_MAX,
            score_value=SPACE_ROOSTER_SCORE_VALUE,
        )
        self.phase = PHASE_ONE
        self.phase_hp_thresholds = self._build_phase_hp_thresholds()
        self._phase_threshold_hp_reference = self.max_hp
        self.health_bar_visible = True
        self.boss_death_explosion_triggered = False
        self.patrol_origin_x = x
        self.movement_timer = 0.0
        self.phase_three_attack_index = ATTACK_SPREAD
        self._spawn_reference_synced = False
        self._start_attack_cooldown(SPACE_ROOSTER_PHASE_ONE_ATTACK_INTERVAL_SECONDS)

    def move(self, dt: float) -> None:
        """Override move() to switch boss movement behavior by current phase."""
        self._sync_spawn_reference()
        self._update_phase()
        self.movement_timer += dt
        if self.phase == PHASE_THREE:
            self._move_erratically()
            return

        speed_multiplier = (
            SPACE_ROOSTER_PHASE_TWO_SPEED_MULTIPLIER
            if self.phase == PHASE_TWO
            else SPACE_ROOSTER_PHASE_ONE_SPEED_MULTIPLIER
        )
        self.x += self._current_base_speed() * speed_multiplier * self._patrol_direction() * dt
        self._bounce_inside_patrol_radius()

    def attack(self, dt: float) -> list[Bullet]:
        """Override attack() to switch boss projectile patterns by current phase."""
        self._update_phase()
        self._update_attack_cooldown(dt)
        if not self._can_attack():
            return []

        if self.phase == PHASE_ONE:
            self._start_attack_cooldown(SPACE_ROOSTER_PHASE_ONE_ATTACK_INTERVAL_SECONDS)
            return self._spread_shots()
        if self.phase == PHASE_TWO:
            self._start_attack_cooldown(SPACE_ROOSTER_PHASE_TWO_ATTACK_INTERVAL_SECONDS)
            return self._spread_shots() + self._diagonal_shots()

        self._start_attack_cooldown(SPACE_ROOSTER_PHASE_THREE_ATTACK_INTERVAL_SECONDS)
        return self._next_phase_three_attack()

    def take_damage(self, amount: int) -> list[Pickup]:
        """Apply damage and update the active boss phase immediately."""
        drops = super().take_damage(amount)
        self._update_phase()
        return drops

    def on_death(self) -> list[Pickup]:
        """Override on_death() to trigger the boss explosion flag and drop configured FC."""
        self.boss_death_explosion_triggered = True
        drop_count = randint(int(self.fc_drop_min), int(self.fc_drop_max))
        return [self._create_feather_core(drop_index) for drop_index in range(drop_count)]

    def _update_phase(self) -> None:
        """Update the active phase when HP crosses 66% or 33% thresholds."""
        self._sync_phase_hp_thresholds()
        phase_two_threshold, phase_three_threshold = self.phase_hp_thresholds
        if self.hp <= phase_three_threshold:
            self.phase = PHASE_THREE
        elif self.hp <= phase_two_threshold:
            self.phase = PHASE_TWO
        else:
            self.phase = PHASE_ONE

    def _sync_phase_hp_thresholds(self) -> None:
        """Rebuild thresholds when map stats replace max_hp after construction."""
        if self.max_hp == self._phase_threshold_hp_reference:
            return

        self.phase_hp_thresholds = self._build_phase_hp_thresholds()
        self._phase_threshold_hp_reference = self.max_hp

    def _sync_spawn_reference(self) -> None:
        """Use the final spawned position as the patrol origin."""
        if self._spawn_reference_synced:
            return

        self.patrol_origin_x = float(getattr(self, "spawn_x", self.x))
        self.spawn_y = self.y
        self._spawn_reference_synced = True

    def _build_phase_hp_thresholds(self) -> tuple[float, float]:
        """Return HP values for phase 2 and phase 3 transitions."""
        return (
            self.max_hp * SPACE_ROOSTER_PHASE_TWO_HP_RATIO,
            self.max_hp * SPACE_ROOSTER_PHASE_THREE_HP_RATIO,
        )

    def _current_base_speed(self) -> float:
        """Return map-configured speed when present, otherwise the default speed."""
        return float(getattr(self, "map_speed", SPACE_ROOSTER_BASE_SPEED))

    def _patrol_direction(self) -> float:
        """Return the current horizontal patrol direction."""
        return 1.0 if self.vx >= 0.0 else -1.0

    def _bounce_inside_patrol_radius(self) -> None:
        """Reverse patrol direction at the patrol radius or screen edge."""
        left_bound = max(0.0, self.patrol_origin_x - SPACE_ROOSTER_PATROL_RADIUS)
        right_bound = min(SCREEN_WIDTH - self.width, self.patrol_origin_x + SPACE_ROOSTER_PATROL_RADIUS)
        if self.x <= left_bound:
            self.x = left_bound
            self.vx = abs(self._current_base_speed())
        elif self.x >= right_bound:
            self.x = right_bound
            self.vx = -abs(self._current_base_speed())

    def _move_erratically(self) -> None:
        """Move in a faster sinusoidal pattern during phase 3."""
        speed = self._current_base_speed() * SPACE_ROOSTER_PHASE_THREE_SPEED_MULTIPLIER
        x_offset = sin(self.movement_timer * SPACE_ROOSTER_ERRATIC_X_FREQUENCY) * SPACE_ROOSTER_ERRATIC_X_RADIUS
        y_offset = cos(self.movement_timer * SPACE_ROOSTER_ERRATIC_Y_FREQUENCY) * SPACE_ROOSTER_ERRATIC_Y_RADIUS
        self.x = self.patrol_origin_x + x_offset * speed / SPACE_ROOSTER_BASE_SPEED
        self.y = self.spawn_y + y_offset
        self.x = max(0.0, min(SCREEN_WIDTH - self.width, self.x))

    def _spread_shots(self) -> list[Bullet]:
        """Create the downward spread pattern used in every phase."""
        return [
            self._create_enemy_bullet(
                vx=-SPACE_ROOSTER_DIAGONAL_SPEED,
                vy=SPACE_ROOSTER_PROJECTILE_SPEED,
                damage=SPACE_ROOSTER_SPREAD_DAMAGE,
                metadata={"pattern": "boss_spread_left", "phase": self.phase},
            ),
            self._create_enemy_bullet(
                vx=SPACE_ROOSTER_CENTER_VX,
                vy=SPACE_ROOSTER_PROJECTILE_SPEED,
                damage=SPACE_ROOSTER_SPREAD_DAMAGE,
                metadata={"pattern": "boss_spread_center", "phase": self.phase},
            ),
            self._create_enemy_bullet(
                vx=SPACE_ROOSTER_DIAGONAL_SPEED,
                vy=SPACE_ROOSTER_PROJECTILE_SPEED,
                damage=SPACE_ROOSTER_SPREAD_DAMAGE,
                metadata={"pattern": "boss_spread_right", "phase": self.phase},
            ),
        ]

    def _diagonal_shots(self) -> list[Bullet]:
        """Create the extra diagonal shots added in phase 2."""
        return [
            self._create_enemy_bullet(
                vx=-SPACE_ROOSTER_DIAGONAL_SPEED * 1.5,
                vy=SPACE_ROOSTER_PROJECTILE_SPEED,
                damage=SPACE_ROOSTER_SPREAD_DAMAGE,
                metadata={"pattern": "boss_diagonal_left", "phase": self.phase},
            ),
            self._create_enemy_bullet(
                vx=SPACE_ROOSTER_DIAGONAL_SPEED * 1.5,
                vy=SPACE_ROOSTER_PROJECTILE_SPEED,
                damage=SPACE_ROOSTER_SPREAD_DAMAGE,
                metadata={"pattern": "boss_diagonal_right", "phase": self.phase},
            ),
        ]

    def _next_phase_three_attack(self) -> list[Bullet]:
        """Cycle phase 3 through spread, beam, and rapid-fire attacks."""
        attack_type = self.phase_three_attack_index
        self.phase_three_attack_index = (self.phase_three_attack_index + 1) % PHASE_THREE_ATTACK_TYPE_COUNT
        if attack_type == ATTACK_BEAM:
            return self._beam_attack()
        if attack_type == ATTACK_RAPID:
            return self._rapid_fire_attack()
        return self._spread_shots() + self._diagonal_shots()

    def _beam_attack(self) -> list[Bullet]:
        """Create the phase 3 beam projectile."""
        return [
            self._create_enemy_bullet(
                vx=SPACE_ROOSTER_CENTER_VX,
                vy=SPACE_ROOSTER_BEAM_SPEED,
                damage=SPACE_ROOSTER_BEAM_DAMAGE,
                width=SPACE_ROOSTER_BEAM_WIDTH,
                height=SPACE_ROOSTER_BEAM_HEIGHT,
                metadata={"pattern": "boss_beam", "phase": self.phase},
            )
        ]

    def _rapid_fire_attack(self) -> list[Bullet]:
        """Create a compact phase 3 rapid-fire volley."""
        bullets = [
            self._create_enemy_bullet(
                vx=SPACE_ROOSTER_CENTER_VX,
                vy=SPACE_ROOSTER_RAPID_SPEED,
                damage=SPACE_ROOSTER_RAPID_DAMAGE,
                width=SPACE_ROOSTER_RAPID_WIDTH,
                height=SPACE_ROOSTER_RAPID_HEIGHT,
                metadata={"pattern": "boss_rapid_fire", "phase": self.phase},
            )
            for _ in range(3)
        ]
        for bullet_index, bullet in enumerate(bullets):
            bullet.x += (bullet_index - 1) * SPACE_ROOSTER_BEAM_WIDTH
        return bullets
