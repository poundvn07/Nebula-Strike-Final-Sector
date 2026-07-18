"""In-game HUD renderer for Nebula Strike combat scenes."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin

import pygame

from src.entities.support_drone import SupportDrone
from src.ui.theme import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_BORDER,
    COLOR_MUTED,
    COLOR_PANEL_RAISED,
    COLOR_SUCCESS,
    COLOR_TEXT,
    COLOR_WARNING,
)
from src.utils.resource import load_font, load_sprite
from src.utils.constants import MAX_ACTIVE_DRONES, SCREEN_HEIGHT, SCREEN_WIDTH
from src.weapons.weapon import ComboType

HUD_TEXT_COLOR = COLOR_TEXT
HUD_MUTED_COLOR = COLOR_MUTED
HUD_ACTIVE_PANEL_COLOR = (22, 52, 82)
HUD_ACTIVE_BORDER_COLOR = COLOR_ACCENT_HOVER
HUD_BAR_BACK_COLOR = (38, 42, 54)
HUD_HP_GREEN = (60, 220, 100)
HUD_HP_YELLOW = (245, 210, 60)
HUD_HP_RED = (235, 70, 64)
HUD_COOLDOWN_COLOR = (255, 255, 255, 110)
HUD_COMBO_COLOR = (120, 220, 255)
HUD_WAVE_CLEAR_COLOR = (150, 255, 170)
HUD_SHADOW_COLOR = (20, 20, 28)
HUD_BOSS_GREEN = (80, 220, 110)
HUD_BOSS_ORANGE = (255, 165, 60)
HUD_BOSS_RED = (235, 70, 64)
HUD_DRONE_GRAY = (90, 92, 104)

BASE_FONT_SIZE = 18
SMALL_FONT_SIZE = 14
ALERT_FONT_SIZE = 48
BOSS_FONT_SIZE = 20
TOP_HUD_RECT = pygame.Rect(6, 6, SCREEN_WIDTH - 12, 58)
BOTTOM_HUD_RECT = pygame.Rect(6, SCREEN_HEIGHT - 66, SCREEN_WIDTH - 12, 60)
HUD_RIBBON_COLOR = (8, 18, 34, 230)
HUD_RIBBON_BORDER_COLOR = (54, 92, 132, 220)
HP_BAR_RECT = pygame.Rect(18, 42, 180, 10)
LIVES_POSITION = (252, 38)
LIVES_ICON_SIZE = (17, 17)
LIVES_ICON_SPACING = 18
WEAPON_SLOT_RECTS = (
    pygame.Rect(18, SCREEN_HEIGHT - 41, 204, 30),
    pygame.Rect(228, SCREEN_HEIGHT - 41, 204, 30),
    pygame.Rect(438, SCREEN_HEIGHT - 41, 212, 30),
)
DRONE_RADIUS = 8
BOSS_SECTION_RECT = pygame.Rect(312, 13, 372, 44)
BOSS_BAR_RECT = pygame.Rect(324, 39, 348, 10)
CENTER_ALERT_Y = SCREEN_HEIGHT // 2 - 72
ALERT_DURATION_SECONDS = 3.0
MAX_STARS = 3
WEAPON_STAR_OUTER_RADIUS = 4
WEAPON_STAR_INNER_RADIUS = 2
WEAPON_STAR_SPACING = 10
WEAPON_STAR_GAP = 3

DRONE_COLORS = {
    SupportDrone: (120, 240, 155),
}





@dataclass
class _TimedAlert:
    """Presentation-only timed alert state."""

    text: str
    color: tuple[int, int, int]
    timer: float = ALERT_DURATION_SECONDS


class HUD:
    """Read-only renderer for combat HP, resources, weapons, drones, alerts, and bosses."""

    def __init__(self) -> None:
        """Initialize presentation-only timers and cached fonts."""
        self._font: pygame.font.Font | None = None
        self._small_font: pygame.font.Font | None = None
        self._alert_font: pygame.font.Font | None = None
        self._boss_font: pygame.font.Font | None = None
        self._alerts: dict[str, _TimedAlert] = {}
        self._wave_clear_was_active = False
        self._shown_combo_names: set[str] = set()

    def update(
        self,
        dt: float,
        *,
        combo_name: object | None = None,
        wave_clear: bool = False,
    ) -> None:
        """Advance HUD timers and register transient read-only alerts."""
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
        current_wave: int | None = None,
        total_waves: int | None = None,
        boss: object | None = None,
        combo_name: object | None = None,
        wave_clear: bool = False,
    ) -> None:
        """Draw the complete HUD overlay on top of the game scene."""
        self.update(0.0, combo_name=combo_name, wave_clear=wave_clear)
        if player is not None:
            self._draw_hud_bars(surface)
            self._draw_player_status(surface, player)
            self._draw_resource_status(surface, player, current_wave, total_waves)
            self._draw_weapon_slots(surface, player)
            self._draw_drone_icons(surface, player)
        self._draw_boss_bar(surface, boss)
        self._draw_alerts(surface)

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

    def _draw_hud_bars(self, surface: pygame.Surface) -> None:
        """Draw separate translucent status and loadout bars at the screen edges."""
        for rect in (TOP_HUD_RECT, BOTTOM_HUD_RECT):
            ribbon = pygame.Surface(rect.size, pygame.SRCALPHA)
            local_rect = ribbon.get_rect()
            pygame.draw.rect(ribbon, HUD_RIBBON_COLOR, local_rect, border_radius=10)
            pygame.draw.rect(ribbon, HUD_RIBBON_BORDER_COLOR, local_rect, 1, border_radius=10)
            surface.blit(ribbon, rect.topleft)
        for divider_x in (306, 690):
            pygame.draw.line(surface, COLOR_BORDER, (divider_x, 15), (divider_x, 55), 1)
        pygame.draw.line(
            surface,
            COLOR_BORDER,
            (668, BOTTOM_HUD_RECT.y + 8),
            (668, BOTTOM_HUD_RECT.bottom - 8),
            1,
        )

    def _draw_player_status(self, surface: pygame.Surface, player: object) -> None:
        """Draw labeled HP and lives in the top bar's ship-status section."""
        hp = int(getattr(player, "hp", 0))
        max_hp = max(1, int(getattr(player, "max_hp", 1)))
        hp_ratio = _clamp_ratio(hp / max_hp)
        heading = self._get_small_font().render("SHIP STATUS", True, HUD_MUTED_COLOR)
        surface.blit(heading, heading.get_rect(left=18, centery=23))
        hp_label = self._get_small_font().render(f"{hp} / {max_hp} HP", True, HUD_TEXT_COLOR)
        surface.blit(hp_label, hp_label.get_rect(right=290, centery=23))
        pygame.draw.rect(surface, HUD_BAR_BACK_COLOR, HP_BAR_RECT, border_radius=5)
        fill_rect = pygame.Rect(HP_BAR_RECT.x, HP_BAR_RECT.y, int(HP_BAR_RECT.width * hp_ratio), HP_BAR_RECT.height)
        pygame.draw.rect(surface, _hp_color(hp_ratio), fill_rect, border_radius=5)
        self._draw_lives_icons(surface, int(getattr(player, "lives", 0)))

    def _draw_lives_icons(self, surface: pygame.Surface, lives: int) -> None:
        """Draw heart icon sprites for each remaining life."""
        icon = load_sprite("lives_icon", LIVES_ICON_SIZE)
        x, y = LIVES_POSITION
        lives_label = self._get_small_font().render("LIVES", True, HUD_MUTED_COLOR)
        surface.blit(lives_label, lives_label.get_rect(left=210, centery=y + 8))
        icon_x = x
        if icon is not None:
            for i in range(lives):
                surface.blit(icon, (icon_x + i * LIVES_ICON_SPACING, y))
        else:
            value = self._get_small_font().render(str(lives), True, HUD_TEXT_COLOR)
            surface.blit(value, (icon_x, y + 3))

    def _draw_resource_status(
        self,
        surface: pygame.Surface,
        player: object,
        current_wave: int | None,
        total_waves: int | None,
    ) -> None:
        """Draw labeled mission values in the top bar's right section."""
        mission_left = 702
        mission_right = 1000
        label_value_gap = 12
        resource_group_gap = 18
        fc_inventory = int(getattr(player, "fc_inventory", 0))
        score = int(getattr(player, "score", 0))
        heading = self._get_small_font().render("MISSION", True, HUD_MUTED_COLOR)
        surface.blit(heading, heading.get_rect(left=mission_left, centery=23))
        if current_wave is not None and total_waves is not None:
            wave = self._get_font().render(f"WAVE {current_wave} / {total_waves}", True, COLOR_ACCENT_HOVER)
            surface.blit(wave, wave.get_rect(right=mission_right, centery=23))

        score_value = self._get_font().render(f"{score:,}", True, HUD_TEXT_COLOR)
        score_value_rect = score_value.get_rect(right=mission_right, centery=48)
        score_label = self._get_small_font().render("SCORE", True, HUD_MUTED_COLOR)
        score_label_rect = score_label.get_rect(right=score_value_rect.left - label_value_gap, centery=48)

        fc_label = self._get_small_font().render("FEATHER CORES", True, HUD_MUTED_COLOR)
        fc_label_rect = fc_label.get_rect(left=mission_left, centery=48)
        fc_value = self._get_font().render(str(fc_inventory), True, COLOR_WARNING)
        fc_value_rect = fc_value.get_rect(left=fc_label_rect.right + label_value_gap, centery=48)
        if fc_value_rect.right + resource_group_gap > score_label_rect.left:
            fc_label = self._get_small_font().render("FC", True, HUD_MUTED_COLOR)
            fc_label_rect = fc_label.get_rect(left=mission_left, centery=48)
            fc_value_rect = fc_value.get_rect(left=fc_label_rect.right + label_value_gap, centery=48)

        surface.blit(fc_label, fc_label_rect)
        surface.blit(fc_value, fc_value_rect)
        surface.blit(score_label, score_label_rect)
        surface.blit(score_value, score_value_rect)

    def _draw_weapon_slots(self, surface: pygame.Surface, player: object) -> None:
        """Draw three readable weapon tabs inside the bottom loadout bar."""
        heading = self._get_small_font().render("WEAPONS", True, HUD_MUTED_COLOR)
        surface.blit(heading, heading.get_rect(left=18, centery=BOTTOM_HUD_RECT.y + 14))
        select_hint = self._get_small_font().render("1-3 SELECT", True, COLOR_ACCENT_HOVER)
        surface.blit(select_hint, select_hint.get_rect(left=104, centery=BOTTOM_HUD_RECT.y + 14))
        cycle_hint = self._get_small_font().render("TAB TO CYCLE", True, COLOR_ACCENT_HOVER)
        surface.blit(cycle_hint, cycle_hint.get_rect(left=202, centery=BOTTOM_HUD_RECT.y + 14))
        weapon_slots = list(getattr(player, "weapon_slots", []))
        active_slot = int(getattr(player, "active_weapon_slot", 0))
        for slot_index, rect in enumerate(WEAPON_SLOT_RECTS):
            weapon = weapon_slots[slot_index] if slot_index < len(weapon_slots) else None
            self._draw_weapon_slot(surface, rect, weapon, slot_index + 1, active=slot_index == active_slot)

    def _draw_weapon_slot(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        weapon: object | None,
        slot_number: int,
        *,
        active: bool = False,
    ) -> None:
        """Draw one weapon slot with stars and cooldown overlay."""
        fill_color = HUD_ACTIVE_PANEL_COLOR if active else COLOR_PANEL_RAISED
        border_color = HUD_ACTIVE_BORDER_COLOR if active else COLOR_BORDER
        pygame.draw.rect(surface, fill_color, rect, border_radius=7)
        pygame.draw.rect(surface, border_color, rect, 1, border_radius=7)
        if active:
            accent_rect = pygame.Rect(rect.x, rect.y + 6, 3, rect.height - 12)
            pygame.draw.rect(surface, COLOR_ACCENT, accent_rect, border_radius=2)

        badge_center = (rect.x + 14, rect.centery)
        pygame.draw.circle(surface, COLOR_ACCENT if active else HUD_BAR_BACK_COLOR, badge_center, 9)
        badge = self._get_small_font().render(str(slot_number), True, HUD_TEXT_COLOR)
        surface.blit(badge, badge.get_rect(center=badge_center))
        if weapon is None:
            empty = self._get_small_font().render("Empty", True, HUD_MUTED_COLOR)
            surface.blit(empty, empty.get_rect(left=rect.x + 27, centery=rect.centery))
            return

        level = int(getattr(weapon, "upgrade_level", 1))
        name = str(getattr(weapon, "name", f"Weapon {slot_number}"))
        label_surface = self._get_small_font().render(name, True, HUD_TEXT_COLOR)
        label_position = (rect.x + 27, rect.centery - label_surface.get_height() // 2)
        surface.blit(label_surface, label_position)
        label_center_y = label_position[1] + label_surface.get_height() // 2
        self._draw_weapon_stars(
            surface,
            (
                label_position[0] + label_surface.get_width() + WEAPON_STAR_GAP + WEAPON_STAR_OUTER_RADIUS,
                label_center_y,
            ),
            level,
        )
        self._draw_cooldown_pie(surface, rect, weapon)

    def _draw_weapon_stars(
        self,
        surface: pygame.Surface,
        position: tuple[int, int],
        level: int,
    ) -> None:
        """Draw weapon level stars without relying on font glyph support."""
        clamped_level = max(0, min(MAX_STARS, level))
        start_x, center_y = position
        for star_index in range(MAX_STARS):
            center = (start_x + star_index * WEAPON_STAR_SPACING, center_y)
            points = _star_points(center, WEAPON_STAR_OUTER_RADIUS, WEAPON_STAR_INNER_RADIUS)
            if star_index < clamped_level:
                pygame.draw.polygon(surface, HUD_TEXT_COLOR, points)
            else:
                pygame.draw.polygon(surface, HUD_MUTED_COLOR, points, 1)

    def _draw_cooldown_pie(self, surface: pygame.Surface, rect: pygame.Rect, weapon: object) -> None:
        """Draw a simple pie-fill overlay for weapon cooldown."""
        cooldown = float(getattr(weapon, "cooldown", 1.0))
        current = float(getattr(weapon, "current_cooldown", 0.0))
        if cooldown <= 0.0 or current <= 0.0:
            return

        cooldown_ratio = _clamp_ratio(current / cooldown)
        center = (rect.right - 10, rect.y + rect.height // 2)
        radius = 7
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
        """Draw a labeled drone status area inside the bottom loadout bar."""
        drones = list(getattr(player, "drones", []))[:MAX_ACTIVE_DRONES]
        center = (990, BOTTOM_HUD_RECT.y + 40)
        label = self._get_small_font().render("SUPPORT DRONE", True, HUD_MUTED_COLOR)
        surface.blit(label, label.get_rect(left=690, centery=BOTTOM_HUD_RECT.y + 14))
        mode_hint = self._get_small_font().render("Q MODE", True, COLOR_ACCENT_HOVER)
        surface.blit(mode_hint, mode_hint.get_rect(right=1000, centery=BOTTOM_HUD_RECT.y + 14))
        if not drones:
            pygame.draw.circle(surface, HUD_BAR_BACK_COLOR, center, DRONE_RADIUS)
            status = self._get_small_font().render("OFFLINE", True, HUD_MUTED_COLOR)
            surface.blit(status, status.get_rect(left=690, centery=center[1]))
            return
        drone = drones[0]
        is_dead = getattr(drone, "is_destroyed", False)
        sprite = getattr(drone, "_get_sprite", lambda: None)()
        status_color = HUD_BOSS_RED if is_dead else COLOR_SUCCESS
        status_text = "DESTROYED" if is_dead else "ONLINE"
        status = self._get_small_font().render(status_text, True, status_color)
        surface.blit(status, status.get_rect(left=690, centery=center[1]))
        if not is_dead:
            mode = getattr(getattr(player, "drone_mode", None), "value", "AUTO")
            mode_text = self._get_small_font().render(str(mode), True, COLOR_ACCENT_HOVER)
            surface.blit(mode_text, mode_text.get_rect(left=790, centery=center[1]))
        if sprite is not None and not is_dead:
            icon = pygame.transform.smoothscale(sprite, (DRONE_RADIUS * 2, DRONE_RADIUS * 2))
            surface.blit(icon, icon.get_rect(center=center))
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
        pygame.draw.rect(surface, COLOR_PANEL_RAISED, BOSS_SECTION_RECT, border_radius=7)
        pygame.draw.rect(surface, COLOR_BORDER, BOSS_SECTION_RECT, 1, border_radius=7)
        name_surface = self._get_small_font().render(f"BOSS  {boss_name}", True, HUD_TEXT_COLOR)
        surface.blit(name_surface, name_surface.get_rect(left=BOSS_SECTION_RECT.x + 12, centery=24))
        pygame.draw.rect(surface, HUD_BAR_BACK_COLOR, BOSS_BAR_RECT, border_radius=5)
        fill_rect = pygame.Rect(
            BOSS_BAR_RECT.x,
            BOSS_BAR_RECT.y,
            int(BOSS_BAR_RECT.width * hp_ratio),
            BOSS_BAR_RECT.height,
        )
        pygame.draw.rect(surface, _boss_color(boss, hp_ratio), fill_rect, border_radius=5)

    def _draw_alerts(self, surface: pygame.Surface) -> None:
        """Draw center alerts that fade after 3 seconds."""
        visible_alerts = list(self._alerts.values())
        for index, alert in enumerate(visible_alerts):
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
            self._font = load_font(BASE_FONT_SIZE)
        return self._font

    def _get_small_font(self) -> pygame.font.Font:
        """Create the small HUD font lazily."""
        if self._small_font is None:
            self._small_font = load_font(SMALL_FONT_SIZE)
        return self._small_font

    def _get_alert_font(self) -> pygame.font.Font:
        """Create the alert font lazily."""
        if self._alert_font is None:
            self._alert_font = load_font(ALERT_FONT_SIZE)
        return self._alert_font

    def _get_boss_font(self) -> pygame.font.Font:
        """Create the boss label font lazily."""
        if self._boss_font is None:
            self._boss_font = load_font(BOSS_FONT_SIZE)
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


def _star_points(
    center: tuple[int, int],
    outer_radius: int,
    inner_radius: int,
) -> list[tuple[int, int]]:
    """Return the ten alternating vertices of a five-point star."""
    center_x, center_y = center
    points: list[tuple[int, int]] = []
    for point_index in range(10):
        radius = outer_radius if point_index % 2 == 0 else inner_radius
        angle = radians(-90 + point_index * 36)
        points.append((
            round(center_x + radius * cos(angle)),
            round(center_y + radius * sin(angle)),
        ))
    return points


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
