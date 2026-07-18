"""Result scene shown after map win or loss."""

from __future__ import annotations

import pygame

from src.core.game_scene import GameScene
from src.core.scene_manager import Scene, SceneManager
from src.entities.player_ship import PlayerShip
from src.systems.save_manager import SaveManager
from src.ui.preparation_screen import PreparationScene
from src.utils.constants import MAP_COUNT, SCREEN_HEIGHT, SCREEN_WIDTH
from src.utils.resource import load_font, load_sprite

RESULT_BG_COLOR = (8, 12, 24)
RESULT_TEXT_COLOR = (235, 242, 255)
RESULT_LOSE_COLOR = (255, 110, 110)
RESULT_WIN_COLOR = (120, 240, 170)
RESULT_BUTTON_COLOR = (42, 84, 126)
RESULT_FONT_SIZE = 30
RESULT_TITLE_FONT_SIZE = 46
RESULT_CENTER_X = SCREEN_WIDTH // 2
RESULT_TITLE_Y = 110
RESULT_LINE_ONE_Y = 178
RESULT_LINE_TWO_Y = 222
RESULT_BUTTON_RECT = pygame.Rect(RESULT_CENTER_X - 95, 292, 190, 44)
FIRST_MAP = 1
RETRY_MIN_HP = 1


class ResultScene(Scene):
    """Scene that displays map result, saves state, and routes Continue or Retry."""

    def __init__(
        self,
        player: PlayerShip,
        scene_manager: SceneManager,
        save_manager: SaveManager | None = None,
        game_state: dict | None = None,
        *,
        won: bool,
        fc_earned: int = 0,
    ) -> None:
        """Initialize result data and save before showing action buttons.

        Loss FC penalties are applied only by GameScene.on_map_lose() before
        this scene is shown; ResultScene does not modify FC for retries.
        """
        self.player = player
        self.scene_manager = scene_manager
        self.save_manager = save_manager or SaveManager()
        self.game_state = dict(game_state or {"current_map": FIRST_MAP})
        self.won = won
        self.fc_earned = fc_earned
        self._font: pygame.font.Font | None = None
        self._title_font: pygame.font.Font | None = None
        if self.won and self.fc_earned > 0:
            self.player.add_fc(self.fc_earned)
        self.save_manager.save(self.player, self.game_state)

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle Continue or Retry clicks."""
        if event.type == pygame.MOUSEBUTTONDOWN and RESULT_BUTTON_RECT.collidepoint(event.pos):
            if self.won:
                self._continue()
            else:
                self._retry()

    def update(self, dt: float) -> None:
        """No animated result state is needed."""
        return None

    def render(self, surface: pygame.Surface) -> None:
        """Render win/loss copy and the next action button."""
        surface.fill(RESULT_BG_COLOR)
        self._render_outcome_background(surface)
        title_text = f"Map {self.game_state.get('current_map', FIRST_MAP)} complete!" if self.won else "Map failed"
        title_color = RESULT_WIN_COLOR if self.won else RESULT_LOSE_COLOR
        _blit_centered(surface, self._get_title_font().render(title_text, True, title_color), RESULT_CENTER_X, RESULT_TITLE_Y)
        if self.won:
            line_one = f"+{self.fc_earned} FC earned"
            button_label = "Continue"
        else:
            line_one = "All lives lost. Progress reset."
            button_label = "Retry"
        line_two = f"FC remaining: {self.player.fc_inventory}"
        _blit_centered(surface, self._get_font().render(line_one, True, RESULT_TEXT_COLOR), RESULT_CENTER_X, RESULT_LINE_ONE_Y)
        _blit_centered(surface, self._get_font().render(line_two, True, RESULT_TEXT_COLOR), RESULT_CENTER_X, RESULT_LINE_TWO_Y)
        _draw_button(surface, RESULT_BUTTON_RECT, button_label, self._get_font())

    def _render_outcome_background(self, surface: pygame.Surface) -> None:
        """Draw the final-victory or full-reset defeat background when applicable."""
        asset_key: str | None = None
        if self.won and int(self.game_state.get("current_map", FIRST_MAP)) >= MAP_COUNT:
            asset_key = "victory_background"
        elif not self.won:
            asset_key = "defeat_background"

        if asset_key is None:
            return
        background = load_sprite(asset_key, (SCREEN_WIDTH, SCREEN_HEIGHT))
        if background is not None:
            surface.blit(background, (0, 0))

    def _continue(self) -> None:
        """Continue to the next preparation scene."""
        current_map = int(self.game_state.get("current_map", FIRST_MAP))
        self.game_state["current_map"] = current_map + 1
        self.scene_manager.replace(PreparationScene(self.player, self.scene_manager, self.save_manager, self.game_state))

    def _retry(self) -> None:
        """Retry from the reset player and initial wave state."""
        self.player.active = True
        if int(self.player.hp) <= 0:
            self.player.hp = max(RETRY_MIN_HP, int(getattr(self.player, "max_hp", RETRY_MIN_HP)))
        self.scene_manager.replace(
            GameScene(
                self.player,
                self.save_manager,
                self.game_state,
                scene_manager=self.scene_manager,
            )
        )

    def _get_font(self) -> pygame.font.Font:
        """Create the result font lazily."""
        if self._font is None:
            self._font = load_font(RESULT_FONT_SIZE)
        return self._font

    def _get_title_font(self) -> pygame.font.Font:
        """Create the result title font lazily."""
        if self._title_font is None:
            self._title_font = load_font(RESULT_TITLE_FONT_SIZE)
        return self._title_font


def _draw_button(surface: pygame.Surface, rect: pygame.Rect, label: str, font: pygame.font.Font) -> None:
    """Draw a result scene button."""
    pygame.draw.rect(surface, RESULT_BUTTON_COLOR, rect)
    text = font.render(label, True, RESULT_TEXT_COLOR)
    _blit_centered(surface, text, rect.centerx, rect.centery)


def _blit_centered(surface: pygame.Surface, rendered: pygame.Surface, center_x: int, center_y: int) -> None:
    """Blit rendered text centered around the given coordinate."""
    surface.blit(rendered, rendered.get_rect(center=(center_x, center_y)))
