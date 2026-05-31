"""Scene stack manager for Nebula Strike."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pygame


class Scene(ABC):
    """Abstract base class for all stack-managed game scenes."""

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle one pygame event."""

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance scene state by delta time."""

    @abstractmethod
    def render(self, surface: pygame.Surface) -> None:
        """Draw this scene to the provided surface."""


class SceneManager:
    """Maintains a simple stack of active scenes with push, pop, and replace."""

    def __init__(self) -> None:
        """Initialize an empty scene stack."""
        self._scene_stack: list[Scene] = []

    @property
    def current_scene(self) -> Scene | None:
        """Return the scene at the top of the stack."""
        if not self._scene_stack:
            return None
        return self._scene_stack[-1]

    def push(self, scene: Scene) -> None:
        """Push a new scene on top of the stack."""
        self._scene_stack.append(scene)

    def pop(self) -> Scene | None:
        """Pop and return the current scene."""
        if not self._scene_stack:
            return None
        return self._scene_stack.pop()

    def replace(self, scene: Scene) -> None:
        """Replace the current scene with a new scene."""
        if self._scene_stack:
            self._scene_stack.pop()
        self._scene_stack.append(scene)

    def handle_event(self, event: pygame.event.Event) -> None:
        """Forward an event to the current scene."""
        if self.current_scene is not None:
            self.current_scene.handle_event(event)

    def update(self, dt: float) -> None:
        """Update the current scene."""
        if self.current_scene is not None:
            self.current_scene.update(dt)

    def render(self, surface: pygame.Surface) -> None:
        """Render the current scene."""
        if self.current_scene is not None:
            self.current_scene.render(surface)
