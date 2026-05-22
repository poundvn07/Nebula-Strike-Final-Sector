"""Event handling helpers for player input."""

from __future__ import annotations

from typing import Protocol

import pygame


class AimToggleTarget(Protocol):
    """Protocol for objects that can toggle aiming mode from keyboard events."""

    def toggle_aiming_mode(self) -> object:
        """Toggle the target aiming mode."""


class EventHandler:
    """Routes pygame events to gameplay systems such as player aim toggling."""

    def __init__(self, player: AimToggleTarget | None = None) -> None:
        """Initialize the event handler with an optional player target."""
        self.player = player

    def handle_event(self, event: pygame.event.Event) -> None:
        """Toggle player aiming mode when Tab is pressed."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB and self.player is not None:
            self.player.toggle_aiming_mode()