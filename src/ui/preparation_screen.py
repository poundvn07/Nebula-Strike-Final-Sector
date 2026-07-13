"""Preparation scene for pre-map repairs, upgrades, and drone management."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pygame

from src.core.game_scene import GameScene
from src.core.scene_manager import Scene, SceneManager
from src.systems.resource_manager import (
    DRONE_SUMMON_COST,
    LIFE_PURCHASE_COST,
    REPAIR_FC_CHUNK,
    ResourceManager,
    WEAPON_SHOP_TYPES,
)
from src.systems.save_manager import SaveManager
from src.utils.constants import SCREEN_HEIGHT, SCREEN_WIDTH

if TYPE_CHECKING:
    from src.entities.drone import Drone
    from src.entities.player_ship import PlayerShip
    from src.weapons.weapon import Weapon

PREP_BG_COLOR = (8, 13, 25)
PREP_TEXT_COLOR = (230, 240, 255)
PREP_MUTED_TEXT_COLOR = (150, 165, 190)
PREP_ERROR_COLOR = (255, 90, 90)
PREP_BUTTON_COLOR = (34, 72, 110)
PREP_BUTTON_DISABLED_COLOR = (54, 58, 70)
PREP_BUTTON_TEXT_COLOR = (255, 255, 255)
PREP_HP_BACK_COLOR = (60, 26, 34)
PREP_HP_FILL_COLOR = (80, 220, 130)
PREP_FONT_SIZE = 22
PREP_SMALL_FONT_SIZE = 18
PREP_TITLE_FONT_SIZE = 50
PREP_CENTER_X = SCREEN_WIDTH // 2
PREP_TITLE_Y = 58
SECTION_WIDTH = 260
SECTION_LEFT_X = 78
SECTION_MIDDLE_X = PREP_CENTER_X - SECTION_WIDTH // 2
SECTION_RIGHT_X = SCREEN_WIDTH - SECTION_LEFT_X - SECTION_WIDTH
BUTTON_WIDTH = 214
BUTTON_HEIGHT = 34
SLOT_BUTTON_WIDTH = 42
SLOT_BUTTON_GAP = 8
HP_BAR_WIDTH = 360
HP_BAR_HEIGHT = 20
LINE_HEIGHT = 40
STATUS_Y = 126
PROGRESSION_TIP_Y = 232
SECTION_HEADING_Y = 278
SECTION_BODY_Y = 316
WEAPON_SLOT_SPACING = 70
WEAPON_BUTTON_X = SECTION_LEFT_X + 18
SHOP_HEADING_Y = SECTION_HEADING_Y
SHOP_BODY_Y = SECTION_BODY_Y
SHOP_ROW_HEIGHT = 46
SHOP_LABEL_X = SECTION_MIDDLE_X
SHOP_SLOT_ONE_X = SECTION_MIDDLE_X + 150
SHOP_SLOT_TWO_X = SHOP_SLOT_ONE_X + SLOT_BUTTON_WIDTH + SLOT_BUTTON_GAP
SHOP_SLOT_THREE_X = SHOP_SLOT_TWO_X + SLOT_BUTTON_WIDTH + SLOT_BUTTON_GAP
REPAIR_SECTION_Y = 548
BEGIN_BUTTON_RECT = pygame.Rect(PREP_CENTER_X - 115, SCREEN_HEIGHT - 76, 230, 44)
REPAIR_BUTTON_RECT = pygame.Rect(SECTION_RIGHT_X, REPAIR_SECTION_Y + 28, BUTTON_WIDTH, BUTTON_HEIGHT)
LIFE_BUTTON_RECT = pygame.Rect(SECTION_RIGHT_X, REPAIR_SECTION_Y + 70, BUTTON_WIDTH, BUTTON_HEIGHT)
FEEDBACK_Y = SCREEN_HEIGHT - 106


ButtonAction = Callable[[], bool]


class PreparationScene(Scene):
    """Scene shown between maps for FC spending before starting combat."""

    def __init__(
        self,
        player: PlayerShip,
        scene_manager: SceneManager,
        save_manager: SaveManager | None = None,
        game_state: dict | None = None,
        resource_manager: ResourceManager | None = None,
    ) -> None:
        """Initialize the preparation scene with player state and scene transition hooks."""
        self.player = player
        self.scene_manager = scene_manager
        self.save_manager = save_manager or SaveManager()
        self.game_state = dict(game_state or {"current_map": 1, "highest_wave_reached": 1})
        self.resource_manager = resource_manager or ResourceManager()
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
        surface.fill(PREP_BG_COLOR)
        self._buttons = []
        self._draw_title(surface)
        self._draw_ship_status(surface)
        self._draw_progression_tip(surface)
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
            self.feedback_text = f"{label} complete"
            self.feedback_color = PREP_TEXT_COLOR
        elif cost > 0:
            self.feedback_text = "Action unavailable"
            self.feedback_color = PREP_ERROR_COLOR

    def _draw_title(self, surface: pygame.Surface) -> None:
        """Draw the preparation title."""
        title = self._get_title_font().render("Preparation", True, PREP_TEXT_COLOR)
        _blit_centered(surface, title, PREP_CENTER_X, PREP_TITLE_Y)

    def _draw_ship_status(self, surface: pygame.Surface) -> None:
        """Draw HP, lives, and FC inventory."""
        font = self._get_font()
        hp_label = font.render(f"Ship HP {int(self.player.hp)}/{int(self.player.max_hp)}", True, PREP_TEXT_COLOR)
        _blit_centered(surface, hp_label, PREP_CENTER_X, STATUS_Y)
        bar_rect = pygame.Rect(PREP_CENTER_X - HP_BAR_WIDTH // 2, STATUS_Y + 28, HP_BAR_WIDTH, HP_BAR_HEIGHT)
        pygame.draw.rect(surface, PREP_HP_BACK_COLOR, bar_rect)
        hp_ratio = self.player.hp / self.player.max_hp if self.player.max_hp > 0 else 0.0
        fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, int(bar_rect.width * hp_ratio), bar_rect.height)
        pygame.draw.rect(surface, PREP_HP_FILL_COLOR, fill_rect)
        lives_text = self._get_small_font().render(f"Lives: {int(getattr(self.player, 'lives', 0))}", True, PREP_TEXT_COLOR)
        _blit_centered(surface, lives_text, PREP_CENTER_X, STATUS_Y + 58)
        fc_text = font.render(f"FC: {self.player.fc_inventory}", True, PREP_TEXT_COLOR)
        _blit_centered(surface, fc_text, PREP_CENTER_X, STATUS_Y + 82)

    def _draw_progression_tip(self, surface: pygame.Surface) -> None:
        """Draw map-specific weapon guidance for upcoming enemy mechanics."""
        current_map = int(self.game_state.get("current_map", 1))
        if current_map == 2:
            tip = "Map 2: Missile AOE bypasses Armored Rooster armor"
        elif current_map >= 3:
            tip = "Map 3+: Missile AOE can damage Dodge Hen"
        else:
            tip = "Buy a second weapon before harder maps"
        _blit_centered(surface, self._get_small_font().render(tip, True, PREP_MUTED_TEXT_COLOR), PREP_CENTER_X, PROGRESSION_TIP_Y)

    def _draw_weapon_section(self, surface: pygame.Surface) -> None:
        """Draw weapon slots and upgrade buttons."""
        font = self._get_font()
        heading = font.render("Weapons", True, PREP_TEXT_COLOR)
        _blit_centered(surface, heading, SECTION_LEFT_X + SECTION_WIDTH // 2, SECTION_HEADING_Y)
        for slot_index, weapon in enumerate(self.player.weapon_slots):
            y = SECTION_BODY_Y + slot_index * WEAPON_SLOT_SPACING
            if weapon is None:
                label = f"Slot {slot_index + 1}: Empty"
                cost = 0
            else:
                label = f"Slot {slot_index + 1}: {weapon.name} Lv {weapon.upgrade_level}"
                cost = int(weapon.get_upgrade_cost())
            surface.blit(font.render(label, True, PREP_TEXT_COLOR), (SECTION_LEFT_X, y))
            if weapon is not None and cost > 0:
                rect = pygame.Rect(WEAPON_BUTTON_X, y + 26, BUTTON_WIDTH, BUTTON_HEIGHT)
                self._add_button(surface, rect, f"Upgrade ({cost} FC)", cost, lambda i=slot_index: self._upgrade_slot(i))

    def _draw_weapon_shop(self, surface: pygame.Surface) -> None:
        """Draw map-gated weapon purchase buttons for each weapon slot."""
        font = self._get_font()
        small_font = self._get_small_font()
        current_map = int(self.game_state.get("current_map", 1))
        _blit_centered(surface, font.render("Weapon Shop", True, PREP_TEXT_COLOR), SECTION_MIDDLE_X + SECTION_WIDTH // 2, SHOP_HEADING_Y)
        for row_index, item in enumerate(self.resource_manager.get_weapon_shop_items(current_map)):
            y = SHOP_BODY_Y + row_index * SHOP_ROW_HEIGHT
            unlocked = bool(item["unlocked"])
            name = str(item["name"])
            cost = int(item["cost"])
            unlock_map = int(item["unlock_map"])
            label = f"{name} ({cost} FC)" if unlocked else f"{name} - Map {unlock_map}"
            color = PREP_TEXT_COLOR if unlocked else PREP_MUTED_TEXT_COLOR
            surface.blit(small_font.render(label, True, color), (SHOP_LABEL_X, y + 8))
            if not unlocked:
                continue

            weapon_key = str(item["key"])
            for slot_index, x in enumerate((SHOP_SLOT_ONE_X, SHOP_SLOT_TWO_X, SHOP_SLOT_THREE_X)):
                rect = pygame.Rect(x, y, SLOT_BUTTON_WIDTH, BUTTON_HEIGHT)
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
        _blit_centered(surface, font.render("Support Drone", True, PREP_TEXT_COLOR), SECTION_RIGHT_X + SECTION_WIDTH // 2, SECTION_HEADING_Y)
        y = SECTION_BODY_Y

        active_support = next((d for d in self.player.drones if isinstance(d, SupportDrone)), None)

        if active_support is None:
            surface.blit(small_font.render("No drone deployed", True, PREP_MUTED_TEXT_COLOR), (SECTION_RIGHT_X, y))
            y += LINE_HEIGHT
            # Summon button — only if player has unlocked SupportDrone
            if SupportDrone in self.player.unlocked_drones:
                rect = pygame.Rect(SECTION_RIGHT_X, y, BUTTON_WIDTH, BUTTON_HEIGHT)
                self._add_button(surface, rect, f"Summon ({DRONE_SUMMON_COST} FC)", DRONE_SUMMON_COST, lambda: self._summon_drone(SupportDrone))
            else:
                from src.entities.support_drone import SUPPORT_DRONE_UNLOCK_COST
                rect = pygame.Rect(SECTION_RIGHT_X, y, BUTTON_WIDTH, BUTTON_HEIGHT)
                self._add_button(surface, rect, f"Unlock ({SUPPORT_DRONE_UNLOCK_COST} FC)", SUPPORT_DRONE_UNLOCK_COST, lambda: self._unlock_drone(SupportDrone))
        elif active_support.is_destroyed:
            surface.blit(small_font.render("Support Drone: Destroyed", True, PREP_ERROR_COLOR), (SECTION_RIGHT_X, y))
            y += LINE_HEIGHT
            rect = pygame.Rect(SECTION_RIGHT_X, y, BUTTON_WIDTH, BUTTON_HEIGHT)
            self._add_button(surface, rect, f"Re-summon ({DRONE_SUMMON_COST} FC)", DRONE_SUMMON_COST, lambda: self._summon_drone(SupportDrone))
        else:
            surface.blit(small_font.render("Support Drone: Active ✓", True, PREP_TEXT_COLOR), (SECTION_RIGHT_X, y))
            y += LINE_HEIGHT
            surface.blit(small_font.render("Collects distant FC drops", True, PREP_MUTED_TEXT_COLOR), (SECTION_RIGHT_X, y))


    def _draw_repair_section(self, surface: pygame.Surface) -> None:
        """Draw repair and life purchase controls."""
        font = self._get_font()
        surface.blit(font.render("Repair / Lives", True, PREP_TEXT_COLOR), (SECTION_RIGHT_X, REPAIR_SECTION_Y))
        self._add_button(surface, REPAIR_BUTTON_RECT, "+20% HP (10 FC)", REPAIR_FC_CHUNK, self._repair_ship)
        self._add_button(surface, LIFE_BUTTON_RECT, f"+1 Life ({LIFE_PURCHASE_COST} FC)", LIFE_PURCHASE_COST, self._purchase_life)

    def _draw_begin_button(self, surface: pygame.Surface) -> None:
        """Draw the begin mission button."""
        self._add_button(surface, BEGIN_BUTTON_RECT, "Begin Mission", 0, self._begin_mission)

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
    ) -> None:
        """Draw and register one button."""
        can_afford = enabled and cost <= self.player.fc_inventory
        color = PREP_BUTTON_COLOR if can_afford else PREP_BUTTON_DISABLED_COLOR
        pygame.draw.rect(surface, color, rect)
        text = self._get_font().render(label, True, PREP_BUTTON_TEXT_COLOR)
        _blit_centered(surface, text, rect.centerx, rect.centery)
        self._buttons.append({"rect": rect, "label": label, "cost": cost, "action": action, "enabled": enabled})

    def _upgrade_slot(self, slot_index: int) -> bool:
        """Upgrade one weapon slot through ResourceManager."""
        return self.resource_manager.upgrade_weapon(self.player, slot_index)

    def _summon_drone(self, drone_type: type[Drone]) -> bool:
        """Summon one replacement drone."""
        return self.resource_manager.summon_drone(self.player, drone_type) is not None

    def _unlock_drone(self, drone_type: type[Drone]) -> bool:
        """Unlock one drone type."""
        return self.resource_manager.unlock_drone_type(self.player, drone_type)

    def _repair_ship(self) -> bool:
        """Repair one 20 percent HP chunk."""
        return self.resource_manager.repair_ship(self.player, REPAIR_FC_CHUNK) > 0

    def _purchase_life(self) -> bool:
        """Buy one extra life through ResourceManager."""
        return self.resource_manager.purchase_life(self.player)

    def _purchase_weapon(self, weapon_key: str, slot_index: int) -> bool:
        """Buy a new weapon and equip or replace the selected slot."""
        current_map = int(self.game_state.get("current_map", 1))
        return self.resource_manager.purchase_weapon(self.player, weapon_key, slot_index, current_map)

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
                resource_manager=self.resource_manager,
            )
        )
        return True

    def _get_font(self) -> pygame.font.Font:
        """Create the UI font lazily."""
        if self._font is None:
            self._font = pygame.font.Font(None, PREP_FONT_SIZE)
        return self._font

    def _get_small_font(self) -> pygame.font.Font:
        """Create the compact preparation font lazily."""
        if self._small_font is None:
            self._small_font = pygame.font.Font(None, PREP_SMALL_FONT_SIZE)
        return self._small_font

    def _get_title_font(self) -> pygame.font.Font:
        """Create the title font lazily."""
        if self._title_font is None:
            self._title_font = pygame.font.Font(None, PREP_TITLE_FONT_SIZE)
        return self._title_font


def _blit_centered(surface: pygame.Surface, rendered: pygame.Surface, center_x: int, center_y: int) -> None:
    """Blit rendered text centered around the given coordinate."""
    surface.blit(rendered, rendered.get_rect(center=(center_x, center_y)))


class PreparationScreen:
    """Compatibility facade that delegates FC spending to ResourceManager."""

    def __init__(self, resource_manager: ResourceManager | None = None) -> None:
        """Initialize with a ResourceManager used for all FC spending actions."""
        self.resource_manager = resource_manager or ResourceManager()

    def repair_ship(self, player: PlayerShip, fc_amount: int) -> int:
        """Spend FC to repair the player ship."""
        return self.resource_manager.repair_ship(player, fc_amount)

    def upgrade_weapon(self, player: PlayerShip, slot: int, weapon: Weapon | None = None) -> bool:
        """Spend FC to upgrade a selected weapon."""
        return self.resource_manager.upgrade_weapon(player, slot, weapon)

    def summon_drone(self, player: PlayerShip, drone_type: type[Drone]) -> Drone | None:
        """Spend FC to summon one drone."""
        return self.resource_manager.summon_drone(player, drone_type)

    def unlock_drone_type(self, player: PlayerShip, drone_type: type[Drone]) -> bool:
        """Spend FC to unlock a drone type."""
        return self.resource_manager.unlock_drone_type(player, drone_type)

    def purchase_life(self, player: PlayerShip) -> bool:
        """Spend FC to buy one extra life."""
        return self.resource_manager.purchase_life(player)

    def purchase_weapon(self, player: PlayerShip, weapon_key: str, slot: int, current_map: int) -> bool:
        """Spend FC to equip a new weapon into a selected slot."""
        return self.resource_manager.purchase_weapon(player, weapon_key, slot, current_map)
