"""Explosion visual effect entity backed by sprite frames."""

from __future__ import annotations

import pygame

from src.entities.game_object import GameObject
from src.utils.assets import load_sprite

EXPLOSION_FRAME_KEYS = ("explosion_1", "explosion_2", "explosion_3", "explosion_4", "explosion_5")
EXPLOSION_DEFAULT_SIZE = 58
EXPLOSION_DURATION_SECONDS = 0.35
EXPLOSION_HP = 1
EXPLOSION_FALLBACK_COLOR = (255, 190, 90)


class ExplosionEffect(GameObject):
    """Short-lived GameObject that renders enemy hit or death explosion sprites."""

    def __init__(
        self,
        x: float,
        y: float,
        width: int = EXPLOSION_DEFAULT_SIZE,
        height: int = EXPLOSION_DEFAULT_SIZE,
        duration: float = EXPLOSION_DURATION_SECONDS,
    ) -> None:
        """Initialize an animated explosion centered near a destroyed object."""
        super().__init__(x=x, y=y, width=width, height=height, hp=EXPLOSION_HP)
        self.duration = max(0.01, duration)
        self.elapsed = 0.0

    def update(self, dt: float) -> None:
        """Advance the animation and deactivate when the sprite sequence ends."""
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.on_death()

    def render(self, surface: pygame.Surface) -> None:
        """Draw the current explosion frame, with a circle fallback."""
        frame_key = self._current_frame_key()
        sprite = load_sprite(frame_key, (int(self.width), int(self.height)))
        if sprite is not None:
            surface.blit(sprite, self.get_rect())
            return

        center = (int(self.x + self.width / 2), int(self.y + self.height / 2))
        pygame.draw.circle(surface, EXPLOSION_FALLBACK_COLOR, center, max(1, self.width // 2))

    def on_death(self) -> None:
        """Deactivate this visual effect."""
        self.active = False

    def _current_frame_key(self) -> str:
        """Return the sprite key matching the current animation progress."""
        progress = min(0.999, max(0.0, self.elapsed / self.duration))
        frame_index = int(progress * len(EXPLOSION_FRAME_KEYS))
        return EXPLOSION_FRAME_KEYS[frame_index]
