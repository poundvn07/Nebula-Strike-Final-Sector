"""Event handling helpers for player input."""

from __future__ import annotations

from typing import Protocol

import pygame


class InputToggleTarget(Protocol):
    """Protocol for objects that can toggle keyboard-driven player modes."""

    def toggle_aiming_mode(self) -> object:
        """Toggle the target aiming mode."""

    def toggle_drone_mode(self) -> object:
        """Toggle the target drone mode."""


class EventHandler:
    """Routes pygame events to gameplay systems such as player mode toggles."""

    def __init__(self, player: InputToggleTarget | None = None) -> None:
        """Initialize the event handler with an optional player target."""
        self.player = player

    def handle_event(self, event: pygame.event.Event) -> None:
        """Toggle player aiming mode with Tab and drone mode with Q."""
        if event.type != pygame.KEYDOWN or self.player is None:
            return

        if event.key == pygame.K_TAB:
            self.player.toggle_aiming_mode()
        elif event.key == pygame.K_q:
            self.player.toggle_drone_mode()
