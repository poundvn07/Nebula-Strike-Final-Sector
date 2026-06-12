"""Feather Core resource pickup entity."""

from __future__ import annotations

from math import sin

import pygame

from src.entities.game_object import GameObject

FEATHER_CORE_WIDTH = 24
FEATHER_CORE_HEIGHT = 24
FEATHER_CORE_COLLISION_SIZE = 24
FEATHER_CORE_COLLISION_HALF_SIZE = FEATHER_CORE_COLLISION_SIZE // 2
FEATHER_CORE_HP = 1
FEATHER_CORE_LIFETIME_SECONDS = 8.0
FEATHER_CORE_WARNING_SECONDS = 3.0
FEATHER_CORE_PULSE_START = 0.0
FEATHER_CORE_PULSE_SPEED = 4.0
FEATHER_CORE_BASE_RADIUS = 10.0
FEATHER_CORE_RADIUS_AMPLITUDE = 2.5
FEATHER_CORE_MIN_RADIUS = 8
FEATHER_CORE_MAX_RADIUS = 12
FEATHER_CORE_COLOR = (255, 220, 50)
FEATHER_CORE_EXPIRY_COLOR = (255, 80, 50)
FEATHER_CORE_DROP_SPEED = 70.0
ZERO_TIME = 0.0
FULL_WARNING_TINT = 1.0


class FeatherCore(GameObject):
    """GameObject pickup that represents collectible Feather Core currency."""

    def __init__(self, x: float, y: float, value: int) -> None:
        """Create a Feather Core pickup with a countdown lifetime."""
        super().__init__(
            x=x,
            y=y,
            width=FEATHER_CORE_WIDTH,
            height=FEATHER_CORE_HEIGHT,
            hp=FEATHER_CORE_HP,
        )
        self._value = value
        self._lifetime = FEATHER_CORE_LIFETIME_SECONDS
        self._pulse_timer = FEATHER_CORE_PULSE_START
        self.collected = False

    @property
    def value(self) -> int:
        """Return how many Feather Cores this pickup is worth."""
        return self._value

    @property
    def lifetime(self) -> float:
        """Return the remaining lifetime before this pickup expires."""
        return self._lifetime

    def update(self, dt: float) -> None:
        """Fall toward the player while lifetime counts down."""
        self._lifetime -= dt
        self._pulse_timer += dt
        self.y += FEATHER_CORE_DROP_SPEED * dt
        if self._lifetime <= ZERO_TIME and not self.collected:
            self.active = False

    def render(self, surface: pygame.Surface) -> None:
        """Draw a pulsing circle that tints red as expiry approaches."""
        pulse = sin(self._pulse_timer * FEATHER_CORE_PULSE_SPEED)
        radius = int(FEATHER_CORE_BASE_RADIUS + FEATHER_CORE_RADIUS_AMPLITUDE * pulse)
        radius = max(FEATHER_CORE_MIN_RADIUS, min(FEATHER_CORE_MAX_RADIUS, radius))
        color = self._get_render_color()
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), radius)

    def on_death(self) -> None:
        """Do nothing because Feather Cores expire or are collected."""
        pass

    def get_rect(self) -> pygame.Rect:
        """Return a 20x20 pickup rectangle centered on the core position."""
        return pygame.Rect(
            int(self.x) - FEATHER_CORE_COLLISION_HALF_SIZE,
            int(self.y) - FEATHER_CORE_COLLISION_HALF_SIZE,
            FEATHER_CORE_COLLISION_SIZE,
            FEATHER_CORE_COLLISION_SIZE,
        )

    def collect(self) -> int:
        """Collect this pickup and return its Feather Core value."""
        self.collected = True
        self.active = False
        return self._value

    def _get_render_color(self) -> tuple[int, int, int]:
        """Return normal or warning-tinted color based on remaining lifetime."""
        if self._lifetime >= FEATHER_CORE_WARNING_SECONDS:
            return FEATHER_CORE_COLOR

        t = FULL_WARNING_TINT - max(ZERO_TIME, self._lifetime) / FEATHER_CORE_WARNING_SECONDS
        return tuple(
            int(start + (end - start) * t)
            for start, end in zip(FEATHER_CORE_COLOR, FEATHER_CORE_EXPIRY_COLOR)
        )
