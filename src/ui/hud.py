"""In-game HUD renderer for Nebula Strike combat scenes."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin
from typing import Protocol

import pygame

from src.entities.support_drone import SupportDrone
from src.utils.resource import load_sprite
from src.utils.constants import MAX_ACTIVE_DRONES, SCREEN_HEIGHT, SCREEN_WIDTH
from src.weapons.weapon import ComboType

HUD_TEXT_COLOR = (235, 244, 255)
HUD_MUTED_COLOR = (145, 155, 175)
HUD_PANEL_COLOR = (8, 12, 24)
HUD_ACTIVE_PANEL_COLOR = (18, 42, 72)
HUD_ACTIVE_BORDER_COLOR = (120, 205, 255)
HUD_BAR_BACK_COLOR = (38, 42, 54)
HUD_HP_GREEN = (60, 220, 100)
HUD_HP_YELLOW = (245, 210, 60)
HUD_HP_RED = (235, 70, 64)
HUD_COOLDOWN_COLOR = (255, 255, 255, 110)
HUD_SPECIAL_COLOR = (120, 190, 255)
HUD_FEVER_COLOR = (255, 190, 40)
HUD_COMBO_COLOR = (120, 220, 255)
HUD_WAVE_CLEAR_COLOR = (150, 255, 170)
HUD_SHADOW_COLOR = (20, 20, 28)
HUD_BOSS_GREEN = (80, 220, 110)
HUD_BOSS_ORANGE = (255, 165, 60)
HUD_BOSS_RED = (235, 70, 64)
HUD_DRONE_GRAY = (90, 92, 104)

BASE_FONT_SIZE = 22
SMALL_FONT_SIZE = 18
ALERT_FONT_SIZE = 56
BOSS_FONT_SIZE = 24
TOP_MARGIN = 14
LEFT_MARGIN = 16
RIGHT_X = SCREEN_WIDTH - 238
HP_BAR_RECT = pygame.Rect(18, 18, 230, 18)
HP_TEXT_POSITION = (18, 42)
LIVES_POSITION = (18, 66)
LIVES_ICON_SIZE = (28, 28)
LIVES_ICON_SPACING = 32
FC_POSITION = (RIGHT_X, 18)
SCORE_POSITION = (RIGHT_X, 42)
WAVE_POSITION = (RIGHT_X, 66)
WEAPON_SLOT_RECTS = (
    pygame.Rect(18, SCREEN_HEIGHT - 158, 260, 38),
    pygame.Rect(18, SCREEN_HEIGHT - 112, 260, 38),
    pygame.Rect(18, SCREEN_HEIGHT - 66, 260, 38),
)
SPECIAL_SLOT_RECT = pygame.Rect(SCREEN_WIDTH - 278, SCREEN_HEIGHT - 64, 260, 40)
DRONE_START_X = SCREEN_WIDTH - 134
DRONE_Y = SCREEN_HEIGHT - 96
DRONE_SPACING = 36
DRONE_RADIUS = 13
BOSS_BAR_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 220, 26, 440, 16)
BOSS_NAME_POSITION = (SCREEN_WIDTH // 2 - 220, 6)
CENTER_ALERT_Y = SCREEN_HEIGHT // 2 - 72
ALERT_DURATION_SECONDS = 3.0
FEVER_FLASH_INTERVAL_SECONDS = 0.2
STAR_FILLED = "★"
STAR_EMPTY = "☆"
MAX_STARS = 3
FC_ICON = "⚙"

DRONE_COLORS = {
    SupportDrone: (120, 240, 155),
}


class FeverStatus(Protocol):
    """Protocol for read-only Fever Mode state exposed by PlayerShip."""

    fever_active: bool


@dataclass
class _TimedAlert:
    """Presentation-only timed alert state."""

    text: str
    color: tuple[int, int, int]
    timer: float = ALERT_DURATION_SECONDS
    flashing: bool = False


class HUD:
    """Read-only renderer for combat HP, resources, weapons, drones, alerts, and bosses."""

    def __init__(self) -> None:
        """Initialize presentation-only timers and cached fonts."""
        self._font: pygame.font.Font | None = None
        self._small_font: pygame.font.Font | None = None
        self._alert_font: pygame.font.Font | None = None
        self._boss_font: pygame.font.Font | None = None
        self._alerts: dict[str, _TimedAlert] = {}
        self._fever_was_active = False
        self._wave_clear_was_active = False
        self._shown_combo_names: set[str] = set()
        self._fever_flash_timer = 0.0
        self._fever_flash_visible = True

    def update(
        self,
        dt: float,
        *,
        fever_status: FeverStatus | None = None,
        combo_name: object | None = None,
        wave_clear: bool = False,
    ) -> None:
        """Advance HUD timers and register transient read-only alerts."""
        self._update_fever_alert(dt, fever_status)
        self._update_combo_alert(combo_name)
        if wave_clear and not self._wave_clear_was_active:
            self.show_wave_clear()
        self._wave_clear_was_active = wave_clear
        self._tick_alerts(dt)

    def render(
        self,
        surface: pygame.Surface,
        player: object | None = None,
        *,
        fever_status: FeverStatus | None = None,
        current_wave: int | None = None,
        total_waves: int | None = None,
        boss: object | None = None,
        combo_name: object | None = None,
        wave_clear: bool = False,
    ) -> None:
        """Draw the complete HUD overlay on top of the game scene."""
        self.update(0.0, fever_status=fever_status, combo_name=combo_name, wave_clear=wave_clear)
        if player is not None:
            self._draw_player_status(surface, player)
            self._draw_resource_status(surface, player, current_wave, total_waves)
            self._draw_weapon_slots(surface, player)
            self._draw_drone_icons(surface, player)
        self._draw_boss_bar(surface, boss)
        self._draw_alerts(surface)

    def show_fever(self) -> None:
        """Show the Fever Mode alert for 3 seconds."""
        self._alerts["fever"] = _TimedAlert("FEVER MODE!", HUD_FEVER_COLOR, flashing=True)

    def show_combo(self, combo_name: object) -> None:
        """Show the first-time combo alert for this HUD session."""
        formatted_combo_name = _format_combo_name(combo_name)
        if formatted_combo_name in self._shown_combo_names:
            return
        self._shown_combo_names.add(formatted_combo_name)
        self._alerts["combo"] = _TimedAlert(f"COMBO: {formatted_combo_name}!", HUD_COMBO_COLOR)

    def show_wave_clear(self) -> None:
        """Show the wave clear alert for 3 seconds."""
        self._alerts["wave_clear"] = _TimedAlert("WAVE CLEAR!", HUD_WAVE_CLEAR_COLOR)

    def _update_fever_alert(self, dt: float, fever_status: FeverStatus | None) -> None:
        """Register Fever alert when Fever becomes active and tick its flash."""
        fever_active = bool(getattr(fever_status, "fever_active", False)) if fever_status is not None else False
        if fever_active and not self._fever_was_active:
            self.show_fever()
        self._fever_was_active = fever_active

        self._fever_flash_timer += dt
        if self._fever_flash_timer >= FEVER_FLASH_INTERVAL_SECONDS:
            self._fever_flash_timer = 0.0
            self._fever_flash_visible = not self._fever_flash_visible

    def _update_combo_alert(self, combo_name: object | None) -> None:
        """Register combo text once per combo name."""
        if combo_name:
            self.show_combo(combo_name)

    def _tick_alerts(self, dt: float) -> None:
        """Tick down active alert timers."""
        expired_keys: list[str] = []
        for key, alert in self._alerts.items():
            alert.timer -= dt
            if alert.timer <= 0.0:
                expired_keys.append(key)
        for key in expired_keys:
            del self._alerts[key]

    def _draw_player_status(self, surface: pygame.Surface, player: object) -> None:
        """Draw top-left HP bar and HP text."""
        hp = int(getattr(player, "hp", 0))
        max_hp = max(1, int(getattr(player, "max_hp", 1)))
        hp_ratio = _clamp_ratio(hp / max_hp)
        pygame.draw.rect(surface, HUD_BAR_BACK_COLOR, HP_BAR_RECT)
        fill_rect = pygame.Rect(HP_BAR_RECT.x, HP_BAR_RECT.y, int(HP_BAR_RECT.width * hp_ratio), HP_BAR_RECT.height)
        pygame.draw.rect(surface, _hp_color(hp_ratio), fill_rect)
        self._draw_text(surface, f"HP: {hp} / {max_hp}", HP_TEXT_POSITION)
        self._draw_lives_icons(surface, int(getattr(player, "lives", 0)))

    def _draw_lives_icons(self, surface: pygame.Surface, lives: int) -> None:
        """Draw heart icon sprites for each remaining life."""
        icon = load_sprite("lives_icon", LIVES_ICON_SIZE)
        x, y = LIVES_POSITION
        if icon is not None:
            for i in range(lives):
                surface.blit(icon, (x + i * LIVES_ICON_SPACING, y))
        else:
            self._draw_text(surface, f"Lives: {lives}", LIVES_POSITION, small=True)

    def _draw_resource_status(
        self,
        surface: pygame.Surface,
        player: object,
        current_wave: int | None,
        total_waves: int | None,
    ) -> None:
        """Draw top-right FC, score, and wave status."""
        fc_inventory = int(getattr(player, "fc_inventory", 0))
        score = int(getattr(player, "score", 0))
        self._draw_text(surface, f"{FC_ICON} {fc_inventory} FC", FC_POSITION)
        self._draw_text(surface, f"Score: {score:,}", SCORE_POSITION)
        if current_wave is not None and total_waves is not None:
            self._draw_text(surface, f"Wave {current_wave} / {total_waves}", WAVE_POSITION)

    def _draw_weapon_slots(self, surface: pygame.Surface, player: object) -> None:
        """Draw bottom-left weapon slots and special skill slot."""
        weapon_slots = list(getattr(player, "weapon_slots", []))
        active_slot = int(getattr(player, "active_weapon_slot", 0))
        for slot_index, rect in enumerate(WEAPON_SLOT_RECTS):
            weapon = weapon_slots[slot_index] if slot_index < len(weapon_slots) else None
            self._draw_weapon_slot(surface, rect, weapon, f"Weapon {slot_index + 1}", active=slot_index == active_slot)
        self._draw_special_slot(surface, SPECIAL_SLOT_RECT, getattr(player, "special_slot", None))

    def _draw_weapon_slot(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        weapon: object | None,
        empty_label: str,
        *,
        active: bool = False,
    ) -> None:
        """Draw one weapon slot with stars and cooldown overlay."""
        pygame.draw.rect(surface, HUD_ACTIVE_PANEL_COLOR if active else HUD_PANEL_COLOR, rect)
        if active:
            pygame.draw.rect(surface, HUD_ACTIVE_BORDER_COLOR, rect, 2)
        if weapon is None:
            prefix = "ACTIVE " if active else ""
            self._draw_text(surface, f"{prefix}{empty_label}: Empty", (rect.x + 8, rect.y + 9), small=True)
            return

        level = int(getattr(weapon, "upgrade_level", 1))
        name = str(getattr(weapon, "name", empty_label))
        prefix = "ACTIVE " if active else ""
        self._draw_text(surface, f"{prefix}{name} {_stars(level)}", (rect.x + 8, rect.y + 7), small=True)
        self._draw_cooldown_pie(surface, rect, weapon)

    def _draw_special_slot(self, surface: pygame.Surface, rect: pygame.Rect, special: object | None) -> None:
        """Draw special skill name and cooldown bar."""
        pygame.draw.rect(surface, HUD_PANEL_COLOR, rect)
        if special is None:
            self._draw_text(surface, "Special: Empty", (rect.x + 8, rect.y + 8), small=True)
            return

        name = str(getattr(special, "name", "Special"))
        self._draw_text(surface, name, (rect.x + 8, rect.y + 6), small=True)
        cooldown = float(getattr(special, "cooldown", 1.0))
        current = float(getattr(special, "current_cooldown", 0.0))
        ready_ratio = 1.0 - _clamp_ratio(current / cooldown) if cooldown > 0.0 else 1.0
        bar_rect = pygame.Rect(rect.x + 8, rect.y + 28, rect.width - 16, 6)
        pygame.draw.rect(surface, HUD_BAR_BACK_COLOR, bar_rect)
        pygame.draw.rect(surface, HUD_SPECIAL_COLOR, pygame.Rect(bar_rect.x, bar_rect.y, int(bar_rect.width * ready_ratio), bar_rect.height))

    def _draw_cooldown_pie(self, surface: pygame.Surface, rect: pygame.Rect, weapon: object) -> None:
        """Draw a simple pie-fill overlay for weapon cooldown."""
        cooldown = float(getattr(weapon, "cooldown", 1.0))
        current = float(getattr(weapon, "current_cooldown", 0.0))
        if cooldown <= 0.0 or current <= 0.0:
            return

        cooldown_ratio = _clamp_ratio(current / cooldown)
        center = (rect.right - 23, rect.y + rect.height // 2)
        radius = 14
        pygame.draw.circle(surface, HUD_BAR_BACK_COLOR, center, radius)
        points = [center]
        steps = max(2, int(18 * cooldown_ratio))
        for step in range(steps + 1):
            angle = -90 + 360 * cooldown_ratio * step / steps
            angle_radians = radians(angle)
            points.append((
                int(center[0] + radius * cos(angle_radians)),
                int(center[1] + radius * sin(angle_radians)),
            ))
        if len(points) >= 3:
            pygame.draw.polygon(surface, HUD_COOLDOWN_COLOR, points)

    def _draw_drone_icons(self, surface: pygame.Surface, player: object) -> None:
        """Draw the single bottom-right drone icon using sprite; grayed when destroyed."""
        drones = list(getattr(player, "drones", []))[:MAX_ACTIVE_DRONES]
        center = (DRONE_START_X, DRONE_Y)
        if not drones:
            # Draw an empty slot indicator
            pygame.draw.circle(surface, HUD_BAR_BACK_COLOR, center, DRONE_RADIUS)
            return
        drone = drones[0]
        is_dead = getattr(drone, "is_destroyed", False)
        sprite = getattr(drone, "_get_sprite", lambda: None)()
        if sprite is not None and not is_dead:
            icon_size = DRONE_RADIUS * 2
            icon_rect = (center[0] - DRONE_RADIUS, center[1] - DRONE_RADIUS)
            surface.blit(sprite, icon_rect)
        else:
            color = HUD_DRONE_GRAY if is_dead else _drone_color(drone)
            pygame.draw.circle(surface, color, center, DRONE_RADIUS)

    def _draw_boss_bar(self, surface: pygame.Surface, boss: object | None) -> None:
        """Draw a top-center boss HP bar when a boss is alive."""
        if boss is None or not getattr(boss, "health_bar_visible", False) or not getattr(boss, "active", True):
            return

        hp = float(getattr(boss, "hp", 0.0))
        max_hp = max(1.0, float(getattr(boss, "max_hp", 1.0)))
        hp_ratio = _clamp_ratio(hp / max_hp)
        boss_name = _display_name(type(boss).__name__)
        self._draw_text(surface, boss_name, BOSS_NAME_POSITION, boss=True)
        pygame.draw.rect(surface, HUD_BAR_BACK_COLOR, BOSS_BAR_RECT)
        fill_rect = pygame.Rect(BOSS_BAR_RECT.x, BOSS_BAR_RECT.y, int(BOSS_BAR_RECT.width * hp_ratio), BOSS_BAR_RECT.height)
        pygame.draw.rect(surface, _boss_color(boss, hp_ratio), fill_rect)

    def _draw_alerts(self, surface: pygame.Surface) -> None:
        """Draw center alerts that fade after 3 seconds."""
        visible_alerts = list(self._alerts.values())
        for index, alert in enumerate(visible_alerts):
            if alert.flashing and not self._fever_flash_visible:
                continue
            alpha_ratio = _clamp_ratio(alert.timer / ALERT_DURATION_SECONDS)
            y = CENTER_ALERT_Y + index * 54
            self._draw_centered_alert(surface, alert.text, alert.color, y, alpha_ratio)

    def _draw_centered_alert(
        self,
        surface: pygame.Surface,
        text: str,
        color: tuple[int, int, int],
        y: int,
        alpha_ratio: float,
    ) -> None:
        """Draw centered text with a simple shadow and alpha fade."""
        font = self._get_alert_font()
        alpha = int(255 * alpha_ratio)
        text_surface = font.render(text, True, color)
        shadow_surface = font.render(text, True, HUD_SHADOW_COLOR)
        _set_alpha(text_surface, alpha)
        _set_alpha(shadow_surface, alpha)
        rect = text_surface.get_rect(center=(SCREEN_WIDTH // 2, y))
        shadow_rect = shadow_surface.get_rect(center=(SCREEN_WIDTH // 2 + 3, y + 3))
        surface.blit(shadow_surface, shadow_rect)
        surface.blit(text_surface, rect)

    def _draw_text(
        self,
        surface: pygame.Surface,
        text: str,
        position: tuple[int, int],
        *,
        small: bool = False,
        boss: bool = False,
    ) -> None:
        """Draw HUD text."""
        font = self._get_boss_font() if boss else self._get_small_font() if small else self._get_font()
        surface.blit(font.render(text, True, HUD_TEXT_COLOR), position)

    def _get_font(self) -> pygame.font.Font:
        """Create the base HUD font lazily."""
        if self._font is None:
            self._font = pygame.font.Font(None, BASE_FONT_SIZE)
        return self._font

    def _get_small_font(self) -> pygame.font.Font:
        """Create the small HUD font lazily."""
        if self._small_font is None:
            self._small_font = pygame.font.Font(None, SMALL_FONT_SIZE)
        return self._small_font

    def _get_alert_font(self) -> pygame.font.Font:
        """Create the alert font lazily."""
        if self._alert_font is None:
            self._alert_font = pygame.font.Font(None, ALERT_FONT_SIZE)
        return self._alert_font

    def _get_boss_font(self) -> pygame.font.Font:
        """Create the boss label font lazily."""
        if self._boss_font is None:
            self._boss_font = pygame.font.Font(None, BOSS_FONT_SIZE)
        return self._boss_font


def _hp_color(hp_ratio: float) -> tuple[int, int, int]:
    """Return green, yellow, or red HP color by threshold."""
    if hp_ratio > 0.60:
        return HUD_HP_GREEN
    if hp_ratio > 0.30:
        return HUD_HP_YELLOW
    return HUD_HP_RED


def _boss_color(boss: object, hp_ratio: float) -> tuple[int, int, int]:
    """Return boss bar color using boss phase when available, otherwise HP thresholds."""
    phase = getattr(boss, "phase", None)
    if phase == 2:
        return HUD_BOSS_ORANGE
    if phase == 3:
        return HUD_BOSS_RED
    if hp_ratio > 0.60:
        return HUD_BOSS_GREEN
    if hp_ratio > 0.30:
        return HUD_BOSS_ORANGE
    return HUD_BOSS_RED


def _stars(level: int) -> str:
    """Return three level stars for a weapon."""
    clamped_level = max(0, min(MAX_STARS, level))
    return STAR_FILLED * clamped_level + STAR_EMPTY * (MAX_STARS - clamped_level)


def _drone_color(drone: object) -> tuple[int, int, int]:
    """Return the configured color for a drone type."""
    for drone_type, color in DRONE_COLORS.items():
        if isinstance(drone, drone_type):
            return color
    return HUD_TEXT_COLOR


def _display_name(class_name: str) -> str:
    """Convert class names like SpaceRooster into Space Rooster."""
    display_chars: list[str] = []
    for index, char in enumerate(class_name):
        if index > 0 and char.isupper():
            display_chars.append(" ")
        display_chars.append(char)
    return "".join(display_chars)


def _format_combo_name(combo_name: object) -> str:
    """Return display text such as Ion Beam for ComboType or save-style names."""
    if isinstance(combo_name, ComboType):
        raw_name = combo_name.value
    else:
        raw_name = str(combo_name)
    return raw_name.replace("_", " ").title()


def _clamp_ratio(value: float) -> float:
    """Clamp a numeric ratio to 0..1."""
    return max(0.0, min(1.0, value))


def _set_alpha(surface: object, alpha: int) -> None:
    """Apply alpha when the pygame surface supports it."""
    set_alpha = getattr(surface, "set_alpha", None)
    if callable(set_alpha):
        set_alpha(alpha)
