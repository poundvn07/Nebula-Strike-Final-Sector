"""Main pygame loop for Nebula Strike: Final Sector."""

from __future__ import annotations

from typing import Protocol

import pygame

from src.utils.constants import (
    BACKGROUND_COLOR,
    FPS,
    GAME_TITLE,
    MILLISECONDS_PER_SECOND,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)


class Scene(Protocol):
    """Protocol for scenes that can be managed by the main game loop."""

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle a pygame event."""

    def update(self, dt: float) -> None:
        """Advance scene state by delta time."""

    def render(self, surface: pygame.Surface) -> None:
        """Draw the scene to the provided surface."""


class Game:
    """Coordinates pygame startup, frame timing, and active scene execution."""

    def __init__(self) -> None:
        """Create a game instance with pygame initialized and a display ready."""
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(GAME_TITLE)
        self.clock = pygame.time.Clock()
        self.running = False
        self.current_scene: Scene | None = None

    def switch_scene(self, scene: Scene | None) -> None:
        """Switch the active scene used by event, update, and render steps."""
        self.current_scene = scene

    def run(self) -> None:
        """Run the capped 60 FPS game loop until the player quits."""
        self.running = True

        while self.running:
            dt = self.clock.tick(FPS) / MILLISECONDS_PER_SECOND

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif self.current_scene is not None:
                    self.current_scene.handle_event(event)

            if self.current_scene is not None:
                self.current_scene.update(dt)

            self.screen.fill(BACKGROUND_COLOR)
            if self.current_scene is not None:
                self.current_scene.render(self.screen)
            pygame.display.flip()

        pygame.quit()
