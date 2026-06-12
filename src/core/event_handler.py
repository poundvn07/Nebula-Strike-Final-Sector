"""Event handling helpers for player input."""

from __future__ import annotations

from typing import Protocol

import pygame


class InputToggleTarget(Protocol):
    """Protocol for objects that can toggle keyboard-driven player modes."""

    def toggle_drone_mode(self) -> object:
        """Toggle the target drone mode."""

    def select_weapon_slot(self, slot_index: int) -> bool:
        """Select which weapon slot fires when Space is held."""

    def cycle_weapon_slot(self) -> int:
        """Cycle to the next equipped weapon slot."""


class EventHandler:
    """Routes pygame events to gameplay systems such as player mode toggles."""

    def __init__(self, player: InputToggleTarget | None = None) -> None:
        """Initialize the event handler with an optional player target."""
        self.player = player

    def handle_event(self, event: pygame.event.Event) -> None:
        """Toggle player modes and select the active weapon slot."""
        if event.type != pygame.KEYDOWN or self.player is None:
            return

        if event.key == pygame.K_TAB:
            self.player.cycle_weapon_slot()
        elif event.key == pygame.K_q:
            self.player.toggle_drone_mode()
        elif event.key == pygame.K_1:
            self.player.select_weapon_slot(0)
        elif event.key == pygame.K_2:
            self.player.select_weapon_slot(1)
        elif event.key == pygame.K_3:
            self.player.select_weapon_slot(2)
