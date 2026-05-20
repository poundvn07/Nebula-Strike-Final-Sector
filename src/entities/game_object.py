"""Abstract base object used by all gameplay entities."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pygame

from src.utils.constants import DEFAULT_VELOCITY, MIN_HEALTH


class GameObject(ABC):
    """Abstract base class for visible, updateable objects in the game world."""

    def __init__(
        self,
        x: float,
        y: float,
        width: int,
        height: int,
        hp: int,
        vx: float = DEFAULT_VELOCITY,
        vy: float = DEFAULT_VELOCITY,
    ) -> None:
        """Initialize shared position, velocity, health, size, and active state."""
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.hp = hp
        self.max_hp = hp
        self.width = width
        self.height = height
        self.active = True

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance the object by delta time."""

    @abstractmethod
    def render(self, surface: pygame.Surface) -> None:
        """Draw the object to the provided surface."""

    @abstractmethod
    def on_death(self) -> None:
        """Run object-specific death behavior."""

    def take_damage(self, amount: int) -> None:
        """Apply damage and trigger death behavior if health reaches zero."""
        if amount <= MIN_HEALTH or not self.active:
            return

        self.hp = max(MIN_HEALTH, self.hp - amount)
        if self.hp == MIN_HEALTH:
            self.active = False
            self.on_death()

    def is_alive(self) -> bool:
        """Return whether the object is active and has health remaining."""
        return self.active and self.hp > MIN_HEALTH

    def get_rect(self) -> pygame.Rect:
        """Return a pygame rectangle for collision checks."""
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)
