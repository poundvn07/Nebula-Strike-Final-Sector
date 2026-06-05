"""Shared pytest fixtures and pygame fallback for Nebula Strike tests."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest


try:
    import pygame  # noqa: F401
except ModuleNotFoundError:

    class Rect:
        """Minimal pygame.Rect substitute for unit tests without pygame installed."""

        def __init__(self, x: int, y: int, width: int, height: int) -> None:
            self.x = x
            self.y = y
            self.width = width
            self.height = height

        @property
        def right(self) -> int:
            """Return the right edge."""
            return self.x + self.width

        @property
        def centerx(self) -> int:
            """Return the horizontal center."""
            return self.x + self.width // 2

        @property
        def centery(self) -> int:
            """Return the vertical center."""
            return self.y + self.height // 2

        def colliderect(self, other: "Rect") -> bool:
            """Return whether two rectangles overlap."""
            return not (
                self.x + self.width <= other.x
                or other.x + other.width <= self.x
                or self.y + self.height <= other.y
                or other.y + other.height <= self.y
            )

        def collidepoint(self, pos: tuple[int, int]) -> bool:
            """Return whether a point is inside this rectangle."""
            px, py = pos
            return self.x <= px <= self.x + self.width and self.y <= py <= self.y + self.height

        def inflate(self, dx: int, dy: int) -> "Rect":
            """Return an inflated rectangle."""
            return Rect(self.x - dx // 2, self.y - dy // 2, self.width + dx, self.height + dy)

    pygame_stub = types.SimpleNamespace(
        Rect=Rect,
        Surface=object,
        KEYDOWN=1,
        MOUSEBUTTONDOWN=2,
        QUIT=3,
        K_TAB=9,
        K_q=113,
        K_SPACE=32,
        K_a=97,
        K_LEFT=276,
        K_d=100,
        K_RIGHT=275,
        K_w=119,
        K_UP=273,
        K_s=115,
        K_DOWN=274,
        draw=types.SimpleNamespace(
            rect=lambda *args, **kwargs: None,
            circle=lambda *args, **kwargs: None,
            polygon=lambda *args, **kwargs: None,
        ),
        font=types.SimpleNamespace(Font=lambda *args, **kwargs: None),
        event=types.SimpleNamespace(Event=object, get=lambda: []),
        display=types.SimpleNamespace(set_mode=lambda *args, **kwargs: object(), set_caption=lambda *args, **kwargs: None, flip=lambda: None),
        time=types.SimpleNamespace(Clock=lambda: types.SimpleNamespace(tick=lambda fps: 16)),
        key=types.SimpleNamespace(get_pressed=lambda: {}),
        init=lambda: None,
        quit=lambda: None,
    )
    sys.modules["pygame"] = pygame_stub


@pytest.fixture
def save_path(tmp_path: Path) -> Path:
    """Return an isolated save path for SaveManager tests."""
    return tmp_path / "save_state.json"
