"""Generic collectible GameObject used for all resource drops."""

from __future__ import annotations

from math import sin

import pygame

from src.entities.game_object import GameObject

PICKUP_WIDTH = 24
PICKUP_HEIGHT = 24
PICKUP_COLLISION_SIZE = 24
PICKUP_HP = 1
PICKUP_LIFETIME_SECONDS = 8.0
PICKUP_WARNING_SECONDS = 3.0
PICKUP_DROP_SPEED = 70.0
FC_RESOURCE_TYPE = "FC"


class Pickup(GameObject):
    """Collectible GameObject whose resource type describes its reward."""

    def __init__(self, x: float, y: float, value: int, resource_type: str = FC_RESOURCE_TYPE) -> None:
        """Create a timed pickup while preserving Feather Core behaviour."""
        super().__init__(x=x, y=y, width=PICKUP_WIDTH, height=PICKUP_HEIGHT, hp=PICKUP_HP)
        self.resource_type = resource_type
        self._value = value
        self._lifetime = PICKUP_LIFETIME_SECONDS
        self._pulse_timer = 0.0
        self.collected = False

    @property
    def value(self) -> int:
        return self._value

    @property
    def lifetime(self) -> float:
        return self._lifetime

    def update(self, dt: float) -> None:
        self._lifetime -= dt
        self._pulse_timer += dt
        self.y += PICKUP_DROP_SPEED * dt
        if self._lifetime <= 0.0 and not self.collected:
            self.active = False

    def render(self, surface: pygame.Surface) -> None:
        pulse = sin(self._pulse_timer * 4.0)
        radius = max(8, min(12, int(10.0 + 2.5 * pulse)))
        color = self._render_color()
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), radius)

    def on_death(self) -> None:
        self.active = False

    def get_rect(self) -> pygame.Rect:
        half_size = PICKUP_COLLISION_SIZE // 2
        return pygame.Rect(int(self.x) - half_size, int(self.y) - half_size, PICKUP_COLLISION_SIZE, PICKUP_COLLISION_SIZE)

    def collect(self) -> int:
        self.collected = True
        self.active = False
        return self._value

    def _render_color(self) -> tuple[int, int, int]:
        if self.resource_type != FC_RESOURCE_TYPE:
            return (180, 220, 255)
        if self._lifetime >= PICKUP_WARNING_SECONDS:
            return (255, 220, 50)
        tint = 1.0 - max(0.0, self._lifetime) / PICKUP_WARNING_SECONDS
        return tuple(int(start + (end - start) * tint) for start, end in zip((255, 220, 50), (255, 80, 50)))
