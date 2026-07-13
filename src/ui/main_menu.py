"""Main menu scene for Nebula Strike."""

from __future__ import annotations

import pygame

from src.core.scene_manager import Scene, SceneManager
from src.entities.player_ship import PlayerShip
from src.systems.save_manager import SaveManager
from src.ui.preparation_screen import PreparationScene
from src.utils.resource import play_sound
from src.utils.constants import SCREEN_WIDTH

MENU_BG_COLOR = (6, 10, 20)
MENU_TEXT_COLOR = (230, 240, 255)
MENU_STATS_TEXT_COLOR = (158, 176, 205)
MENU_BUTTON_COLOR = (34, 70, 110)
MENU_BUTTON_TEXT_COLOR = (255, 255, 255)
MENU_FONT_SIZE = 34
MENU_STATS_FONT_SIZE = 22
MENU_TITLE_FONT_SIZE = 56
MENU_BUTTON_WIDTH = 220
MENU_BUTTON_HEIGHT = 44
MENU_CENTER_X = SCREEN_WIDTH // 2
MENU_TITLE_Y = 84
NEW_GAME_BUTTON_RECT = pygame.Rect(MENU_CENTER_X - MENU_BUTTON_WIDTH // 2, 224, MENU_BUTTON_WIDTH, MENU_BUTTON_HEIGHT)
CONTINUE_BUTTON_RECT = pygame.Rect(MENU_CENTER_X - MENU_BUTTON_WIDTH // 2, 284, MENU_BUTTON_WIDTH, MENU_BUTTON_HEIGHT)
MENU_SUMMARY_Y = 352
MENU_SUMMARY_LINE_HEIGHT = 26


class MainMenuScene(Scene):
    """Scene that shows New Game and Continue entry points."""

    def __init__(self, scene_manager: SceneManager, save_manager: SaveManager | None = None) -> None:
        """Initialize the menu with save summary access."""
        self.scene_manager = scene_manager
        self.save_manager = save_manager or SaveManager()
        self._font: pygame.font.Font | None = None
        self._stats_font: pygame.font.Font | None = None
        self._title_font: pygame.font.Font | None = None
        self._buttons: list[tuple[pygame.Rect, str, object]] = []

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle menu button clicks."""
        if event.type != pygame.MOUSEBUTTONDOWN:
            return

        for rect, _label, action in self._buttons:
            if rect.collidepoint(event.pos):
                play_sound("menu_select")
                action()
                return

    def update(self, dt: float) -> None:
        """No animated state is needed for the current main menu."""
        return None

    def render(self, surface: pygame.Surface) -> None:
        """Render title, save summary, and menu buttons."""
        surface.fill(MENU_BG_COLOR)
        title = self._get_title_font().render("Nebula Strike", True, MENU_TEXT_COLOR)
        _blit_centered(surface, title, MENU_CENTER_X, MENU_TITLE_Y)
        self._buttons = [
            (NEW_GAME_BUTTON_RECT, "New Game", self._new_game),
            (CONTINUE_BUTTON_RECT, "Continue", self._continue_game),
        ]
        for rect, label, _action in self._buttons:
            _draw_button(surface, rect, label, self._get_font())
        self._render_summary(surface)

    def _render_summary(self, surface: pygame.Surface) -> None:
        """Render compact save summary for Continue."""
        summary = self.save_manager.get_save_summary()
        if not summary:
            lines = ["No save found"]
        else:
            lines = [
                f"Map {summary['current_map']}  |  HP {int(summary['ship_hp_percent'])}%",
                f"Score {summary['score']}  |  FC {summary['fc_inventory']}",
            ]
        for line_index, text in enumerate(lines):
            rendered = self._get_stats_font().render(text, True, MENU_STATS_TEXT_COLOR)
            _blit_centered(
                surface,
                rendered,
                MENU_CENTER_X,
                MENU_SUMMARY_Y + line_index * MENU_SUMMARY_LINE_HEIGHT,
            )

    def _continue_game(self) -> None:
        """Load saved data into a player and continue at preparation."""
        data = self.save_manager.load()
        player = PlayerShip()
        game_state = data or {"current_map": 1, "highest_wave_reached": 1}
        if data is not None:
            self.save_manager.apply_to_player(data, player)
        else:
            self.save_manager.apply_starting_loadout(player)
        self.scene_manager.replace(PreparationScene(player, self.scene_manager, self.save_manager, game_state))

    def _new_game(self) -> None:
        """Start a fresh preparation scene."""
        player = PlayerShip()
        self.save_manager.apply_starting_loadout(player)
        game_state = {"current_map": 1, "highest_wave_reached": 1}
        self.scene_manager.replace(PreparationScene(player, self.scene_manager, self.save_manager, game_state))

    def _get_font(self) -> pygame.font.Font:
        """Create the menu font lazily."""
        if self._font is None:
            self._font = pygame.font.Font(None, MENU_FONT_SIZE)
        return self._font

    def _get_stats_font(self) -> pygame.font.Font:
        """Create the compact save-summary font lazily."""
        if self._stats_font is None:
            self._stats_font = pygame.font.Font(None, MENU_STATS_FONT_SIZE)
        return self._stats_font

    def _get_title_font(self) -> pygame.font.Font:
        """Create the title font lazily."""
        if self._title_font is None:
            self._title_font = pygame.font.Font(None, MENU_TITLE_FONT_SIZE)
        return self._title_font


def _draw_button(surface: pygame.Surface, rect: pygame.Rect, label: str, font: pygame.font.Font) -> None:
    """Draw a menu button."""
    pygame.draw.rect(surface, MENU_BUTTON_COLOR, rect)
    text = font.render(label, True, MENU_BUTTON_TEXT_COLOR)
    _blit_centered(surface, text, rect.centerx, rect.centery)


def _blit_centered(surface: pygame.Surface, rendered: pygame.Surface, center_x: int, center_y: int) -> None:
    """Blit rendered text centered around the given coordinate."""
    surface.blit(rendered, rendered.get_rect(center=(center_x, center_y)))
