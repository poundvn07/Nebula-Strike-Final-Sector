"""Short-lived visual GameObject effects."""

from __future__ import annotations

import pygame

from src.entities.game_object import GameObject
from src.utils.resource import load_sprite

EXPLOSION = "explosion"
EXPLOSION_FRAME_KEYS = ("explosion_1", "explosion_2", "explosion_3", "explosion_4", "explosion_5")


class Effect(GameObject):
    """A generic visual effect; ``type='explosion'`` renders explosion frames."""

    def __init__(self, x: float, y: float, width: int = 58, height: int = 58, duration: float = 0.35, type: str = EXPLOSION) -> None:
        super().__init__(x=x, y=y, width=width, height=height, hp=1)
        self.type = type
        self.duration = max(0.01, duration)
        self.elapsed = 0.0

    def update(self, dt: float) -> None:
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.on_death()

    def render(self, surface: pygame.Surface) -> None:
        if self.type == EXPLOSION:
            sprite = load_sprite(self._current_frame_key(), (int(self.width), int(self.height)))
            if sprite is not None:
                surface.blit(sprite, self.get_rect())
                return
            pygame.draw.circle(surface, (255, 190, 90), (int(self.x + self.width / 2), int(self.y + self.height / 2)), max(1, self.width // 2))

    def on_death(self) -> None:
        self.active = False

    def _current_frame_key(self) -> str:
        progress = min(0.999, max(0.0, self.elapsed / self.duration))
        return EXPLOSION_FRAME_KEYS[int(progress * len(EXPLOSION_FRAME_KEYS))]
