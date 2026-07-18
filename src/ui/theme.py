"""Shared visual language for Nebula Strike menus and preparation screens."""

from __future__ import annotations

import pygame

from src.utils.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from src.utils.resource import load_sprite

COLOR_BG = (5, 9, 19)
COLOR_PANEL = (11, 18, 32)
COLOR_PANEL_RAISED = (16, 27, 46)
COLOR_BORDER = (39, 59, 84)
COLOR_BORDER_ACTIVE = (82, 169, 235)
COLOR_ACCENT = (48, 132, 201)
COLOR_ACCENT_HOVER = (66, 157, 226)
COLOR_TEXT = (235, 243, 255)
COLOR_MUTED = (145, 162, 189)
COLOR_SUCCESS = (75, 222, 148)
COLOR_WARNING = (255, 194, 92)
COLOR_DANGER = (255, 105, 113)
COLOR_DISABLED = (42, 49, 64)
COLOR_SHADOW = (2, 5, 12)

PANEL_RADIUS = 14
BUTTON_RADIUS = 8


def draw_space_background(surface: pygame.Surface) -> None:
    """Draw a reusable star-field backdrop with a subtle blue atmosphere."""
    surface.fill(COLOR_BG)
    background = load_sprite("background", (SCREEN_WIDTH, SCREEN_HEIGHT))
    if background is not None:
        surface.blit(background, (0, 0))

    tint = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    tint.fill((4, 10, 24, 205))
    pygame.draw.circle(tint, (29, 111, 180, 34), (SCREEN_WIDTH // 2, -80), 390)
    pygame.draw.circle(tint, (53, 67, 156, 20), (SCREEN_WIDTH - 80, SCREEN_HEIGHT), 310)
    surface.blit(tint, (0, 0))


def draw_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    *,
    raised: bool = False,
    active: bool = False,
    shadow: bool = True,
) -> None:
    """Draw a rounded card with optional elevation and active border."""
    if shadow:
        shadow_rect = pygame.Rect(rect.x, rect.y + 5, rect.width, rect.height)
        pygame.draw.rect(surface, COLOR_SHADOW, shadow_rect, border_radius=PANEL_RADIUS)
    fill = COLOR_PANEL_RAISED if raised else COLOR_PANEL
    border = COLOR_BORDER_ACTIVE if active else COLOR_BORDER
    pygame.draw.rect(surface, fill, rect, border_radius=PANEL_RADIUS)
    pygame.draw.rect(surface, border, rect, 1, border_radius=PANEL_RADIUS)


def draw_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    *,
    enabled: bool = True,
    primary: bool = False,
    hovered: bool = False,
) -> None:
    """Draw a rounded button with clear primary, hover, and disabled states."""
    if not enabled:
        fill = COLOR_DISABLED
        border = COLOR_BORDER
        text_color = COLOR_MUTED
    elif primary:
        fill = COLOR_ACCENT_HOVER if hovered else COLOR_ACCENT
        border = COLOR_BORDER_ACTIVE
        text_color = COLOR_TEXT
    else:
        fill = (29, 48, 73) if hovered else COLOR_PANEL_RAISED
        border = COLOR_BORDER_ACTIVE if hovered else COLOR_BORDER
        text_color = COLOR_TEXT

    shadow_rect = pygame.Rect(rect.x, rect.y + 3, rect.width, rect.height)
    pygame.draw.rect(surface, COLOR_SHADOW, shadow_rect, border_radius=BUTTON_RADIUS)
    pygame.draw.rect(surface, fill, rect, border_radius=BUTTON_RADIUS)
    pygame.draw.rect(surface, border, rect, 1, border_radius=BUTTON_RADIUS)
    rendered = font.render(label, True, text_color)
    surface.blit(rendered, rendered.get_rect(center=(rect.centerx, rect.centery)))


def mouse_over(rect: pygame.Rect) -> bool:
    """Return whether the mouse is over a rectangle when mouse support exists."""
    mouse = getattr(pygame, "mouse", None)
    get_pos = getattr(mouse, "get_pos", None)
    return bool(callable(get_pos) and rect.collidepoint(get_pos()))
