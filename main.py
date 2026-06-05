"""Executable entrypoint for Nebula Strike: Final Sector."""

from __future__ import annotations

import pygame

from src.core.scene_manager import SceneManager
from src.ui.main_menu import MainMenuScene
from src.utils.assets import start_background_music
from src.utils.constants import FPS, GAME_TITLE, MILLISECONDS_PER_SECOND, SCREEN_HEIGHT, SCREEN_WIDTH


def main() -> None:
    """Initialize pygame, seed the scene stack, and run the main loop."""
    pygame.init()
    start_background_music()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(GAME_TITLE)
    clock = pygame.time.Clock()
    scene_manager = SceneManager()
    scene_manager.push(MainMenuScene(scene_manager))

    running = True
    while running and scene_manager.current_scene is not None:
        dt = clock.tick(FPS) / MILLISECONDS_PER_SECOND
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                scene_manager.handle_event(event)

        scene_manager.update(dt)
        scene_manager.render(screen)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
