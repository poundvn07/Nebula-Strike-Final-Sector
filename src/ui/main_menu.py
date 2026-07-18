"""Main menu scene for Nebula Strike."""

from __future__ import annotations

import pygame

from src.core.scene_manager import Scene, SceneManager
from src.entities.player_ship import PlayerShip
from src.systems.save_manager import SaveManager
from src.ui.preparation_screen import PreparationScene
from src.ui.theme import (
    COLOR_ACCENT_HOVER,
    COLOR_MUTED,
    COLOR_TEXT,
    draw_button,
    draw_panel,
    draw_space_background,
    mouse_over,
)
from src.utils.resource import load_font, play_sound
from src.utils.constants import SCREEN_WIDTH

MENU_FONT_SIZE = 34
MENU_STATS_FONT_SIZE = 22
MENU_TITLE_FONT_SIZE = 56
MENU_CENTER_X = SCREEN_WIDTH // 2
MENU_EYEBROW_Y = 58
MENU_TITLE_Y = 112
MENU_SUBTITLE_Y = 166
MENU_PANEL_RECT = pygame.Rect(MENU_CENTER_X - 194, 218, 388, 374)
NEW_GAME_BUTTON_RECT = pygame.Rect(MENU_CENTER_X - 150, 292, 300, 58)
CONTINUE_BUTTON_RECT = pygame.Rect(MENU_CENTER_X - 150, 370, 300, 58)
MENU_SUMMARY_RECT = pygame.Rect(MENU_CENTER_X - 150, 458, 300, 96)
MENU_FOOTER_Y = 716


class MainMenuScene(Scene):
    """Scene that shows New Game and Continue entry points."""

    def __init__(self, scene_manager: SceneManager, save_manager: SaveManager | None = None) -> None:
        """Initialize the menu with save summary access."""
        self.scene_manager = scene_manager
        self.save_manager = save_manager or SaveManager()
        self._font: pygame.font.Font | None = None
        self._stats_font: pygame.font.Font | None = None
        self._title_font: pygame.font.Font | None = None
        self._buttons: list[tuple[pygame.Rect, str, object, bool]] = []

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle menu button clicks."""
        if event.type != pygame.MOUSEBUTTONDOWN:
            return

        for rect, _label, action, enabled in self._buttons:
            if enabled and rect.collidepoint(event.pos):
                play_sound("menu_select")
                action()
                return

    def update(self, dt: float) -> None:
        """No animated state is needed for the current main menu."""
        return None

    def render(self, surface: pygame.Surface) -> None:
        """Render title, save summary, and menu buttons."""
        draw_space_background(surface)
        eyebrow = self._get_stats_font().render("NEBULA COMMAND", True, COLOR_ACCENT_HOVER)
        _blit_centered(surface, eyebrow, MENU_CENTER_X, MENU_EYEBROW_Y)
        title = self._get_title_font().render("Nebula Strike", True, COLOR_TEXT)
        _blit_centered(surface, title, MENU_CENTER_X, MENU_TITLE_Y)
        subtitle = self._get_stats_font().render("FINAL SECTOR", True, COLOR_MUTED)
        _blit_centered(surface, subtitle, MENU_CENTER_X, MENU_SUBTITLE_Y)

        draw_panel(surface, MENU_PANEL_RECT, raised=True)
        prompt = self._get_stats_font().render("SELECT MISSION", True, COLOR_MUTED)
        _blit_centered(surface, prompt, MENU_CENTER_X, MENU_PANEL_RECT.y + 38)
        summary = self.save_manager.get_save_summary()
        has_save = bool(summary)
        self._buttons = [
            (NEW_GAME_BUTTON_RECT, "New Game", self._new_game, True),
            (CONTINUE_BUTTON_RECT, "Continue", self._continue_game, has_save),
        ]
        for index, (rect, label, _action, enabled) in enumerate(self._buttons):
            draw_button(
                surface,
                rect,
                label,
                self._get_font(),
                enabled=enabled,
                primary=index == 0,
                hovered=enabled and mouse_over(rect),
            )
        self._render_summary(surface, summary)
        footer = self._get_stats_font().render("ARROW KEYS / WASD TO FLY    |    SPACE TO FIRE", True, COLOR_MUTED)
        _blit_centered(surface, footer, MENU_CENTER_X, MENU_FOOTER_Y)

    def _render_summary(self, surface: pygame.Surface, summary: dict[str, object] | None) -> None:
        """Render compact save summary for Continue."""
        draw_panel(surface, MENU_SUMMARY_RECT, raised=False, shadow=False)
        if not summary:
            heading = "NO ACTIVE RUN"
            lines = ["Start a new game to begin your mission"]
        else:
            heading = "CURRENT RUN"
            lines = [
                f"Map {summary['current_map']}  |  HP {int(summary['ship_hp_percent'])}%",
                f"Score {summary['score']}  |  FC {summary['fc_inventory']}",
            ]
        heading_surface = self._get_stats_font().render(heading, True, COLOR_ACCENT_HOVER)
        _blit_centered(surface, heading_surface, MENU_CENTER_X, MENU_SUMMARY_RECT.y + 24)
        for line_index, text in enumerate(lines):
            rendered = self._get_stats_font().render(text, True, COLOR_MUTED)
            _blit_centered(
                surface,
                rendered,
                MENU_CENTER_X,
                MENU_SUMMARY_RECT.y + 55 + line_index * 24,
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
            self._font = load_font(MENU_FONT_SIZE)
        return self._font

    def _get_stats_font(self) -> pygame.font.Font:
        """Create the compact save-summary font lazily."""
        if self._stats_font is None:
            self._stats_font = load_font(MENU_STATS_FONT_SIZE)
        return self._stats_font

    def _get_title_font(self) -> pygame.font.Font:
        """Create the title font lazily."""
        if self._title_font is None:
            self._title_font = load_font(MENU_TITLE_FONT_SIZE)
        return self._title_font

def _blit_centered(surface: pygame.Surface, rendered: pygame.Surface, center_x: int, center_y: int) -> None:
    """Blit rendered text centered around the given coordinate."""
    surface.blit(rendered, rendered.get_rect(center=(center_x, center_y)))
