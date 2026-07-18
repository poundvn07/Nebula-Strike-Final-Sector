"""Preparation scene for pre-map repairs, upgrades, and drone management."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pygame

from src.core.game_scene import GameScene
from src.core.scene_manager import Scene, SceneManager
from src.systems.save_manager import SaveManager
from src.ui.theme import (
    COLOR_ACCENT_HOVER,
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_PANEL_RAISED,
    COLOR_SUCCESS,
    COLOR_TEXT,
    COLOR_WARNING,
    draw_button,
    draw_panel,
    draw_space_background,
    mouse_over,
)
from src.utils.constants import SCREEN_WIDTH
from src.utils.resource import load_font
from src.weapons.laser_cannon import LaserCannon
from src.weapons.missile_salvo import MissileSalvo
from src.weapons.plasma_spread import PlasmaSpread

if TYPE_CHECKING:
    from src.entities.drone import Drone
    from src.entities.player_ship import PlayerShip
    from src.weapons.weapon import Weapon

PREP_TEXT_COLOR = COLOR_TEXT
PREP_MUTED_TEXT_COLOR = COLOR_MUTED
PREP_ERROR_COLOR = COLOR_DANGER
PREP_HP_BACK_COLOR = (60, 26, 34)
PREP_HP_FILL_COLOR = COLOR_SUCCESS
PREP_FONT_SIZE = 18
PREP_SMALL_FONT_SIZE = 14
PREP_TITLE_FONT_SIZE = 42
PREP_CENTER_X = SCREEN_WIDTH // 2
PREP_TITLE_POSITION = (44, 24)
STATUS_CARD_RECT = pygame.Rect(36, 96, SCREEN_WIDTH - 72, 114)
HP_BAR_RECT = pygame.Rect(58, 153, 450, 18)
LIVES_CARD_RECT = pygame.Rect(548, 119, 168, 66)
FC_CARD_RECT = pygame.Rect(734, 119, 232, 66)
LOADOUT_CARD_RECT = pygame.Rect(36, 228, 300, 418)
SHOP_CARD_RECT = pygame.Rect(354, 228, 320, 418)
SERVICES_CARD_RECT = pygame.Rect(692, 228, 296, 418)
SECTION_HEADING_Y = 258
LOADOUT_SLOT_X = 52
LOADOUT_SLOT_WIDTH = 268
LOADOUT_SLOT_HEIGHT = 96
LOADOUT_SLOT_START_Y = 290
LOADOUT_SLOT_SPACING = 112
SHOP_ROW_X = 370
SHOP_ROW_WIDTH = 288
SHOP_ROW_HEIGHT = 94
SHOP_ROW_START_Y = 290
SHOP_ROW_SPACING = 108
SLOT_BUTTON_WIDTH = 52
SLOT_BUTTON_HEIGHT = 32
SLOT_BUTTON_GAP = 6
DRONE_PANEL_RECT = pygame.Rect(708, 290, 264, 142)
SERVICE_BUTTON_WIDTH = 264
SERVICE_BUTTON_HEIGHT = 40
DRONE_BUTTON_Y = 374
REPAIR_BUTTON_RECT = pygame.Rect(708, 514, SERVICE_BUTTON_WIDTH, SERVICE_BUTTON_HEIGHT)
LIFE_BUTTON_RECT = pygame.Rect(708, 568, SERVICE_BUTTON_WIDTH, SERVICE_BUTTON_HEIGHT)
BEGIN_BUTTON_RECT = pygame.Rect(PREP_CENTER_X - 142, 698, 284, 48)
FEEDBACK_Y = 674
DRONE_SUMMON_COST = 30
LIFE_PURCHASE_COST = 160
MAX_PURCHASED_LIVES = 5
REPAIR_FC_CHUNK = 10
WEAPON_SHOP_ORDER = ("LASER_CANNON", "PLASMA_SPREAD", "MISSILE_SALVO")
WEAPON_SHOP_TYPES = {
    "LASER_CANNON": LaserCannon,
    "PLASMA_SPREAD": PlasmaSpread,
    "MISSILE_SALVO": MissileSalvo,
}
WEAPON_PURCHASE_COSTS = {"LASER_CANNON": 60, "PLASMA_SPREAD": 95, "MISSILE_SALVO": 130}
WEAPON_UNLOCK_MAPS = {"LASER_CANNON": 1, "PLASMA_SPREAD": 1, "MISSILE_SALVO": 3}


ButtonAction = Callable[[], bool]


class PreparationScene(Scene):
    """Scene shown between maps for FC spending before starting combat."""

    def __init__(
        self,
        player: PlayerShip,
        scene_manager: SceneManager,
        save_manager: SaveManager | None = None,
        game_state: dict | None = None,
    ) -> None:
        """Initialize the preparation scene with player state and scene transition hooks."""
        self.player = player
        self.scene_manager = scene_manager
        self.save_manager = save_manager or SaveManager()
        self.game_state = dict(game_state or {"current_map": 1, "highest_wave_reached": 1})
        self.feedback_text = ""
        self.feedback_color = PREP_ERROR_COLOR
        self._buttons: list[dict[str, object]] = []
        self._font: pygame.font.Font | None = None
        self._small_font: pygame.font.Font | None = None
        self._title_font: pygame.font.Font | None = None

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle preparation button clicks."""
        if event.type != pygame.MOUSEBUTTONDOWN:
            return

        for button in self._buttons:
            rect = button["rect"]
            if isinstance(rect, pygame.Rect) and rect.collidepoint(event.pos):
                self._handle_button(button)
                return

    def update(self, dt: float) -> None:
        """No animated state is needed for the current preparation screen."""
        return None

    def render(self, surface: pygame.Surface) -> None:
        """Render ship status, weapons, drones, unlocks, repairs, and mission start."""
        draw_space_background(surface)
        self._buttons = []
        self._draw_title(surface)
        self._draw_ship_status(surface)
        self._draw_progression_tip(surface)
        self._draw_section_panels(surface)
        self._draw_weapon_section(surface)
        self._draw_weapon_shop(surface)
        self._draw_drone_section(surface)
        self._draw_repair_section(surface)
        self._draw_begin_button(surface)
        self._draw_feedback(surface)

    def _handle_button(self, button: dict[str, object]) -> None:
        """Run a button action after checking FC affordability."""
        cost = int(button.get("cost", 0))
        label = str(button.get("label", ""))
        action = button.get("action")
        if not bool(button.get("enabled", True)):
            self.feedback_text = "Unavailable"
            self.feedback_color = PREP_ERROR_COLOR
            return
        if cost > self.player.fc_inventory:
            self.feedback_text = "Not enough FC"
            self.feedback_color = PREP_ERROR_COLOR
            return
        if not callable(action):
            return

        success = bool(action())
        if success:
            self.feedback_text = _success_message(label)
            self.feedback_color = PREP_TEXT_COLOR
        elif cost > 0:
            self.feedback_text = "Action unavailable"
            self.feedback_color = PREP_ERROR_COLOR

    def _draw_title(self, surface: pygame.Surface) -> None:
        """Draw the preparation title."""
        title = self._get_title_font().render("Preparation Bay", True, PREP_TEXT_COLOR)
        surface.blit(title, PREP_TITLE_POSITION)
        subtitle = self._get_small_font().render("Configure your ship before deployment", True, PREP_MUTED_TEXT_COLOR)
        surface.blit(subtitle, (PREP_TITLE_POSITION[0] + 2, PREP_TITLE_POSITION[1] + 49))
        current_map = int(self.game_state.get("current_map", 1))
        map_label = self._get_font().render(f"MAP {current_map}", True, COLOR_ACCENT_HOVER)
        surface.blit(map_label, map_label.get_rect(right=SCREEN_WIDTH - 44, centery=52))

    def _draw_ship_status(self, surface: pygame.Surface) -> None:
        """Draw HP, lives, and FC inventory."""
        draw_panel(surface, STATUS_CARD_RECT, raised=True)
        font = self._get_font()
        small_font = self._get_small_font()
        status_label = small_font.render("SHIP INTEGRITY", True, PREP_MUTED_TEXT_COLOR)
        surface.blit(status_label, (58, 117))
        hp_label = font.render(f"{int(self.player.hp)} / {int(self.player.max_hp)} HP", True, PREP_TEXT_COLOR)
        surface.blit(hp_label, hp_label.get_rect(right=HP_BAR_RECT.right, centery=125))
        pygame.draw.rect(surface, PREP_HP_BACK_COLOR, HP_BAR_RECT, border_radius=9)
        hp_ratio = self.player.hp / self.player.max_hp if self.player.max_hp > 0 else 0.0
        fill_rect = pygame.Rect(HP_BAR_RECT.x, HP_BAR_RECT.y, int(HP_BAR_RECT.width * hp_ratio), HP_BAR_RECT.height)
        pygame.draw.rect(surface, PREP_HP_FILL_COLOR, fill_rect, border_radius=9)

        draw_panel(surface, LIVES_CARD_RECT, raised=False, shadow=False)
        lives_label = small_font.render("LIVES", True, PREP_MUTED_TEXT_COLOR)
        lives_value = font.render(str(int(getattr(self.player, "lives", 0))), True, PREP_TEXT_COLOR)
        surface.blit(lives_label, (LIVES_CARD_RECT.x + 16, LIVES_CARD_RECT.y + 11))
        surface.blit(lives_value, (LIVES_CARD_RECT.x + 16, LIVES_CARD_RECT.y + 31))

        draw_panel(surface, FC_CARD_RECT, raised=False, shadow=False)
        fc_label = small_font.render("FEATHER CORES", True, PREP_MUTED_TEXT_COLOR)
        fc_value = font.render(f"{self.player.fc_inventory} FC", True, COLOR_WARNING)
        surface.blit(fc_label, (FC_CARD_RECT.x + 16, FC_CARD_RECT.y + 11))
        surface.blit(fc_value, (FC_CARD_RECT.x + 16, FC_CARD_RECT.y + 31))

    def _draw_progression_tip(self, surface: pygame.Surface) -> None:
        """Draw map-specific weapon guidance for upcoming enemy mechanics."""
        current_map = int(self.game_state.get("current_map", 1))
        if current_map == 2:
            tip = "Map 2: Missile AOE bypasses Armored Rooster armor"
        elif current_map >= 3:
            tip = "Map 3+: Missile AOE can damage Dodge Hen"
        else:
            tip = "Buy a second weapon before harder maps"
        tip_surface = self._get_small_font().render(tip, True, PREP_MUTED_TEXT_COLOR)
        surface.blit(tip_surface, (58, 181))

    def _draw_section_panels(self, surface: pygame.Surface) -> None:
        """Draw the three task-focused preparation cards."""
        draw_panel(surface, LOADOUT_CARD_RECT, raised=True)
        draw_panel(surface, SHOP_CARD_RECT, raised=True)
        draw_panel(surface, SERVICES_CARD_RECT, raised=True)

    def _draw_weapon_section(self, surface: pygame.Surface) -> None:
        """Draw weapon slots and upgrade buttons."""
        font = self._get_font()
        small_font = self._get_small_font()
        heading = font.render("Weapon Loadout", True, PREP_TEXT_COLOR)
        _blit_centered(surface, heading, LOADOUT_CARD_RECT.centerx, SECTION_HEADING_Y)
        for slot_index, weapon in enumerate(self.player.weapon_slots):
            y = LOADOUT_SLOT_START_Y + slot_index * LOADOUT_SLOT_SPACING
            slot_rect = pygame.Rect(LOADOUT_SLOT_X, y, LOADOUT_SLOT_WIDTH, LOADOUT_SLOT_HEIGHT)
            draw_panel(surface, slot_rect, raised=False, active=weapon is not None, shadow=False)
            slot_label = small_font.render(f"SLOT {slot_index + 1}", True, PREP_MUTED_TEXT_COLOR)
            surface.blit(slot_label, (slot_rect.x + 14, slot_rect.y + 10))
            if weapon is None:
                empty_text = font.render("Empty hardpoint", True, PREP_MUTED_TEXT_COLOR)
                surface.blit(empty_text, (slot_rect.x + 14, slot_rect.y + 40))
                continue

            name = font.render(str(weapon.name), True, PREP_TEXT_COLOR)
            surface.blit(name, (slot_rect.x + 14, slot_rect.y + 32))
            level = small_font.render(f"LV {weapon.upgrade_level}", True, COLOR_ACCENT_HOVER)
            surface.blit(level, level.get_rect(right=slot_rect.right - 14, centery=slot_rect.y + 43))
            cost = int(weapon.get_upgrade_cost())
            if cost > 0:
                rect = pygame.Rect(slot_rect.x + 12, slot_rect.y + 61, slot_rect.width - 24, 27)
                self._add_button(
                    surface,
                    rect,
                    f"Upgrade - {cost} FC",
                    cost,
                    lambda i=slot_index: self._upgrade_slot(i),
                )
            else:
                max_level = small_font.render("MAX LEVEL", True, COLOR_SUCCESS)
                surface.blit(max_level, (slot_rect.x + 14, slot_rect.y + 68))

    def _draw_weapon_shop(self, surface: pygame.Surface) -> None:
        """Draw map-gated weapon purchase buttons for each weapon slot."""
        font = self._get_font()
        small_font = self._get_small_font()
        current_map = int(self.game_state.get("current_map", 1))
        shop_heading = font.render("Weapon Shop", True, PREP_TEXT_COLOR)
        _blit_centered(surface, shop_heading, SHOP_CARD_RECT.centerx, SECTION_HEADING_Y)
        for row_index, item in enumerate(get_weapon_shop_items(current_map)):
            y = SHOP_ROW_START_Y + row_index * SHOP_ROW_SPACING
            row_rect = pygame.Rect(SHOP_ROW_X, y, SHOP_ROW_WIDTH, SHOP_ROW_HEIGHT)
            unlocked = bool(item["unlocked"])
            draw_panel(surface, row_rect, raised=False, active=unlocked, shadow=False)
            name = str(item["name"])
            cost = int(item["cost"])
            unlock_map = int(item["unlock_map"])
            color = PREP_TEXT_COLOR if unlocked else PREP_MUTED_TEXT_COLOR
            surface.blit(font.render(name, True, color), (row_rect.x + 14, row_rect.y + 12))
            if not unlocked:
                lock_text = small_font.render(f"Unlocks on Map {unlock_map}", True, PREP_MUTED_TEXT_COLOR)
                surface.blit(lock_text, (row_rect.x + 14, row_rect.y + 54))
                continue

            price = small_font.render(f"{cost} FC", True, COLOR_WARNING)
            surface.blit(price, (row_rect.x + 14, row_rect.y + 61))
            weapon_key = str(item["key"])
            slot_buttons_width = SLOT_BUTTON_WIDTH * 3 + SLOT_BUTTON_GAP * 2
            slot_start_x = row_rect.right - slot_buttons_width - 12
            for slot_index in range(3):
                x = slot_start_x + slot_index * (SLOT_BUTTON_WIDTH + SLOT_BUTTON_GAP)
                rect = pygame.Rect(x, row_rect.y + 50, SLOT_BUTTON_WIDTH, SLOT_BUTTON_HEIGHT)
                self._add_button(
                    surface,
                    rect,
                    f"S{slot_index + 1}",
                    cost,
                    lambda key=weapon_key, i=slot_index: self._purchase_weapon(key, i),
                    enabled=self._can_purchase_weapon_for_slot(weapon_key, slot_index),
                )

    def _draw_drone_section(self, surface: pygame.Surface) -> None:
        """Draw Support Drone status, summon button, and re-summon button if destroyed."""
        from src.entities.support_drone import SupportDrone
        font = self._get_font()
        small_font = self._get_small_font()
        services_heading = font.render("Support & Services", True, PREP_TEXT_COLOR)
        _blit_centered(surface, services_heading, SERVICES_CARD_RECT.centerx, SECTION_HEADING_Y)
        draw_panel(surface, DRONE_PANEL_RECT, raised=False, shadow=False)
        drone_label = small_font.render("SUPPORT DRONE", True, PREP_MUTED_TEXT_COLOR)
        surface.blit(drone_label, (DRONE_PANEL_RECT.x + 14, DRONE_PANEL_RECT.y + 12))

        active_support = next((d for d in self.player.drones if isinstance(d, SupportDrone)), None)
        button_rect = pygame.Rect(
            DRONE_PANEL_RECT.x + 12,
            DRONE_BUTTON_Y,
            DRONE_PANEL_RECT.width - 24,
            SERVICE_BUTTON_HEIGHT,
        )

        if active_support is None:
            status = font.render("Not deployed", True, PREP_MUTED_TEXT_COLOR)
            surface.blit(status, (DRONE_PANEL_RECT.x + 14, DRONE_PANEL_RECT.y + 40))
            if SupportDrone in self.player.unlocked_drones:
                self._add_button(
                    surface,
                    button_rect,
                    f"Deploy - {DRONE_SUMMON_COST} FC",
                    DRONE_SUMMON_COST,
                    lambda: self._summon_drone(SupportDrone),
                )
            else:
                from src.entities.support_drone import SUPPORT_DRONE_UNLOCK_COST
                self._add_button(
                    surface,
                    button_rect,
                    f"Unlock - {SUPPORT_DRONE_UNLOCK_COST} FC",
                    SUPPORT_DRONE_UNLOCK_COST,
                    lambda: self._unlock_drone(SupportDrone),
                )
        elif active_support.is_destroyed:
            status = font.render("Destroyed", True, PREP_ERROR_COLOR)
            surface.blit(status, (DRONE_PANEL_RECT.x + 14, DRONE_PANEL_RECT.y + 40))
            self._add_button(
                surface,
                button_rect,
                f"Re-deploy - {DRONE_SUMMON_COST} FC",
                DRONE_SUMMON_COST,
                lambda: self._summon_drone(SupportDrone),
            )
        else:
            status = font.render("Online", True, COLOR_SUCCESS)
            surface.blit(status, (DRONE_PANEL_RECT.x + 14, DRONE_PANEL_RECT.y + 40))
            detail = small_font.render("Collects distant FC drops", True, PREP_MUTED_TEXT_COLOR)
            surface.blit(detail, (DRONE_PANEL_RECT.x + 14, DRONE_PANEL_RECT.y + 76))


    def _draw_repair_section(self, surface: pygame.Surface) -> None:
        """Draw repair and life purchase controls."""
        font = self._get_font()
        small_font = self._get_small_font()
        pygame.draw.rect(surface, COLOR_PANEL_RAISED, pygame.Rect(708, 456, 264, 1))
        services_label = small_font.render("SHIP SERVICES", True, PREP_MUTED_TEXT_COLOR)
        surface.blit(services_label, (708, 478))
        self._add_button(surface, REPAIR_BUTTON_RECT, "Repair 20% - 10 FC", REPAIR_FC_CHUNK, self._repair_ship)
        self._add_button(
            surface,
            LIFE_BUTTON_RECT,
            f"Purchase Life - {LIFE_PURCHASE_COST} FC",
            LIFE_PURCHASE_COST,
            self._purchase_life,
        )
        hint = small_font.render("Services use your current FC balance", True, PREP_MUTED_TEXT_COLOR)
        surface.blit(hint, (708, 620))

    def _draw_begin_button(self, surface: pygame.Surface) -> None:
        """Draw the begin mission button."""
        self._add_button(surface, BEGIN_BUTTON_RECT, "Launch Mission", 0, self._begin_mission, primary=True)

    def _draw_feedback(self, surface: pygame.Surface) -> None:
        """Draw current feedback text."""
        if not self.feedback_text:
            return
        text = self._get_font().render(self.feedback_text, True, self.feedback_color)
        _blit_centered(surface, text, PREP_CENTER_X, FEEDBACK_Y)

    def _add_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        cost: int,
        action: ButtonAction,
        *,
        enabled: bool = True,
        primary: bool = False,
    ) -> None:
        """Draw and register one button."""
        can_afford = enabled and cost <= self.player.fc_inventory
        draw_button(
            surface,
            rect,
            label,
            self._get_font(),
            enabled=can_afford,
            primary=primary,
            hovered=can_afford and mouse_over(rect),
        )
        self._buttons.append({"rect": rect, "label": label, "cost": cost, "action": action, "enabled": enabled})

    def _upgrade_slot(self, slot_index: int) -> bool:
        """Upgrade one weapon slot through PlayerShip's owned loadout state."""
        return self.player.upgrade_weapon(slot_index)

    def _summon_drone(self, drone_type: type[Drone]) -> bool:
        """Summon one replacement drone."""
        return self.player.summon_drone(drone_type) is not None

    def _unlock_drone(self, drone_type: type[Drone]) -> bool:
        """Unlock one drone type."""
        return self.player.unlock_drone(drone_type)

    def _repair_ship(self) -> bool:
        """Repair one 20 percent HP chunk."""
        return self.player.repair(REPAIR_FC_CHUNK) > 0

    def _purchase_life(self) -> bool:
        """Buy one extra life through PlayerShip's persistent state."""
        return self.player.purchase_life(LIFE_PURCHASE_COST, MAX_PURCHASED_LIVES)

    def _purchase_weapon(self, weapon_key: str, slot_index: int) -> bool:
        """Buy a new weapon and equip or replace the selected slot."""
        return purchase_weapon(self.player, weapon_key, slot_index, int(self.game_state.get("current_map", 1)))

    def _can_purchase_weapon_for_slot(self, weapon_key: str, slot_index: int) -> bool:
        """Return whether a shop button can change the selected weapon slot."""
        if slot_index < 0 or slot_index >= len(self.player.weapon_slots):
            return False
        weapon = self.player.weapon_slots[slot_index]
        if weapon is None:
            return True
        weapon_class = WEAPON_SHOP_TYPES.get(weapon_key)
        return weapon_class is not None and not isinstance(weapon, weapon_class)

    def _begin_mission(self) -> bool:
        """Transition to GameScene for the current map."""
        self.scene_manager.replace(
            GameScene(
                self.player,
                self.save_manager,
                self.game_state,
                scene_manager=self.scene_manager,
            )
        )
        return True

    def _get_font(self) -> pygame.font.Font:
        """Create the UI font lazily."""
        if self._font is None:
            self._font = load_font(PREP_FONT_SIZE)
        return self._font

    def _get_small_font(self) -> pygame.font.Font:
        """Create the compact preparation font lazily."""
        if self._small_font is None:
            self._small_font = load_font(PREP_SMALL_FONT_SIZE)
        return self._small_font

    def _get_title_font(self) -> pygame.font.Font:
        """Create the title font lazily."""
        if self._title_font is None:
            self._title_font = load_font(PREP_TITLE_FONT_SIZE)
        return self._title_font


def _blit_centered(surface: pygame.Surface, rendered: pygame.Surface, center_x: int, center_y: int) -> None:
    """Blit rendered text centered around the given coordinate."""
    surface.blit(rendered, rendered.get_rect(center=(center_x, center_y)))


def _success_message(label: str) -> str:
    """Return concise feedback for preparation actions."""
    if label.startswith("Upgrade"):
        return "Weapon upgraded"
    if label in {"S1", "S2", "S3"}:
        return "Weapon equipped"
    if label.startswith(("Unlock", "Deploy", "Re-deploy")):
        return "Support drone ready"
    if label.startswith("Repair"):
        return "Ship repaired"
    if label.startswith("Purchase Life"):
        return "Extra life purchased"
    return "Ready for launch"


class PreparationScreen:
    """Small preparation API kept for callers that do not render a scene."""

    def repair_ship(self, player: PlayerShip, fc_amount: int) -> int:
        """Spend FC to repair the player ship."""
        return player.repair(fc_amount)

    def upgrade_weapon(self, player: PlayerShip, slot: int, weapon: Weapon | None = None) -> bool:
        """Spend FC to upgrade a selected weapon."""
        return player.upgrade_weapon(slot, weapon)

    def summon_drone(self, player: PlayerShip, drone_type: type[Drone]) -> Drone | None:
        """Spend FC to summon one drone."""
        return player.summon_drone(drone_type)

    def unlock_drone_type(self, player: PlayerShip, drone_type: type[Drone]) -> bool:
        """Spend FC to unlock a drone type."""
        return player.unlock_drone(drone_type)

    def purchase_life(self, player: PlayerShip) -> bool:
        """Spend FC to buy one extra life."""
        return player.purchase_life(LIFE_PURCHASE_COST, MAX_PURCHASED_LIVES)

    def purchase_weapon(self, player: PlayerShip, weapon_key: str, slot: int, current_map: int) -> bool:
        """Spend FC to equip a new weapon into a selected slot."""
        return purchase_weapon(player, weapon_key, slot, current_map)


def get_weapon_shop_items(current_map: int) -> list[dict[str, object]]:
    """Build the unchanged map-gated weapon catalog for the preparation UI."""
    return [
        {
            "key": key,
            "name": weapon_class().name,
            "cost": WEAPON_PURCHASE_COSTS[key],
            "unlock_map": WEAPON_UNLOCK_MAPS[key],
            "unlocked": current_map >= WEAPON_UNLOCK_MAPS[key],
        }
        for key, weapon_class in ((key, WEAPON_SHOP_TYPES[key]) for key in WEAPON_SHOP_ORDER)
    ]


def purchase_weapon(player: PlayerShip, weapon_key: str, slot_index: int, current_map: int) -> bool:
    """Spend FC and equip the selected preparation-shop weapon without a manager."""
    weapon_class = WEAPON_SHOP_TYPES.get(weapon_key)
    if weapon_class is None or slot_index < 0 or slot_index >= len(player.weapon_slots):
        return False
    if current_map < WEAPON_UNLOCK_MAPS[weapon_key] or isinstance(player.weapon_slots[slot_index], weapon_class):
        return False
    cost = WEAPON_PURCHASE_COSTS[weapon_key]
    if not player.spend_fc(cost):
        return False
    player.equip_weapon(weapon_class(), slot_index)
    return True
