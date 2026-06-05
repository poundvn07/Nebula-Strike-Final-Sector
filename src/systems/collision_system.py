"""Collision system for bullets, enemies, player, and Feather Cores."""

from __future__ import annotations

import pygame

from src.entities.bullet import Bullet
from src.entities.feather_core import FeatherCore
from src.entities.player_ship import PlayerShip
from src.enemies.enemy import Enemy
from src.systems.resource_manager import ResourceManager
from src.utils.constants import MIN_HEALTH

FC_ITEM_DEFAULT_SIZE = 12
FC_DEFAULT_VALUE = 1
PLAYER_OWNER = "player"
ENEMY_OWNER = "enemy"
RECT_DEFAULT_X = 0
RECT_DEFAULT_Y = 0
AOE_DIAMETER_MULTIPLIER = 2


class CollisionSystem:
    """Coordinates pygame.Rect collisions across projectiles, enemies, and pickups."""

    def __init__(self, resource_manager: ResourceManager | None = None) -> None:
        """Initialize collision tracking state."""
        self.fc_streak_counter = MIN_HEALTH
        self.resource_manager = resource_manager

    def check_all(
        self,
        player: PlayerShip,
        bullets: list[Bullet],
        enemies: list[Enemy],
        fc_items: list[FeatherCore],
    ) -> None:
        """Check all requested collisions and mutate involved objects in place."""
        player.set_auto_targets(enemies)
        for bullet in bullets:
            if not getattr(bullet, "active", True):
                continue

            owner = _get_bullet_owner(bullet)
            if owner == PLAYER_OWNER:
                self._apply_fever_visual_state(bullet)
                self._check_player_bullet(player, bullet, enemies, fc_items)
            elif owner == ENEMY_OWNER:
                self._check_enemy_bullet(player, bullet)

        self._check_enemy_body_collisions(player, enemies)
        self._check_fc_pickups(player, fc_items)

    def _check_player_bullet(
        self,
        player: PlayerShip,
        bullet: Bullet,
        enemies: list[Enemy],
        fc_items: list[FeatherCore],
    ) -> None:
        """Apply player bullet damage to colliding enemies and collect drops."""
        bullet_rect = _get_bullet_collision_rect(bullet)
        for enemy in enemies:
            if not hasattr(enemy, "get_rect") or not hasattr(enemy, "is_alive"):
                continue
            if not getattr(enemy, "active", True):
                continue
            if not bullet_rect.colliderect(enemy.get_rect()):
                continue

            was_alive = enemy.is_alive()
            drops = self._hit_enemy_with_player_bullet(bullet, enemy)
            if was_alive and not enemy.is_alive():
                player.score += getattr(enemy, "score_value", MIN_HEALTH)
                fc_items.extend(drops)
            if not getattr(bullet, "active", True):
                return

    def _check_enemy_bullet(self, player: PlayerShip, bullet: Bullet) -> None:
        """Apply enemy bullet damage to the player on collision."""
        if _get_bullet_collision_rect(bullet).colliderect(player.get_rect()):
            bullet.on_hit(player)
            if self.resource_manager is not None:
                self.resource_manager.on_player_hit()

    def _check_enemy_body_collisions(self, player: PlayerShip, enemies: list[Enemy]) -> None:
        """Apply contact damage for enemies that attack by ramming the player."""
        player_rect = player.get_rect()
        for enemy in enemies:
            if not getattr(enemy, "active", True):
                continue
            collision_damage = int(getattr(enemy, "collision_damage", MIN_HEALTH))
            if collision_damage <= MIN_HEALTH:
                continue
            if not player_rect.colliderect(enemy.get_rect()):
                continue

            player.take_damage(collision_damage)
            enemy.hp = MIN_HEALTH
            enemy.active = False
            if self.resource_manager is not None:
                self.resource_manager.on_player_hit()

    def _check_fc_pickups(self, player: PlayerShip, fc_items: list[FeatherCore]) -> None:
        """Collect Feather Cores that collide with the player's rectangle."""
        player_rect = player.get_rect()
        for fc_item in fc_items:
            if not getattr(fc_item, "active", True):
                continue
            if not player_rect.colliderect(_get_fc_rect(fc_item)):
                continue

            player.add_fc(_collect_fc_item(fc_item))
            self.fc_streak_counter += 1
            player.fc_streak_counter = self.fc_streak_counter
            if self.resource_manager is not None:
                self.resource_manager.on_fc_collected()

    def _hit_enemy_with_player_bullet(self, bullet: Bullet, enemy: Enemy) -> list[object]:
        """Apply Fever Mode damage multiplier while preserving the bullet's base damage."""
        if self.resource_manager is None:
            return bullet.on_hit(enemy)

        original_damage = bullet.damage
        bullet.damage = original_damage * self.resource_manager.get_damage_multiplier()
        try:
            return bullet.on_hit(enemy)
        finally:
            bullet.damage = original_damage

    def _apply_fever_visual_state(self, bullet: Bullet) -> None:
        """Mark player bullets for Fever Mode tinting while Fever is active."""
        if self.resource_manager is not None:
            bullet.fever_active = self.resource_manager.fever_active


def _get_bullet_owner(bullet: Bullet) -> str:
    """Return the normalized owner for player and enemy projectile checks."""
    owner = getattr(bullet, "owner", None)
    if owner in (PLAYER_OWNER, ENEMY_OWNER):
        return owner
    return PLAYER_OWNER


def _get_bullet_collision_rect(bullet: Bullet) -> pygame.Rect:
    """Return the bullet collision rect, inflated for AOE bullets."""
    rect = bullet.get_rect()
    aoe_radius = int(bullet.aoe_radius)
    is_aoe = bool(bullet.is_aoe or aoe_radius > MIN_HEALTH)
    if is_aoe and aoe_radius > MIN_HEALTH:
        return rect.inflate(aoe_radius * AOE_DIAMETER_MULTIPLIER, aoe_radius * AOE_DIAMETER_MULTIPLIER)
    return rect


def _get_fc_rect(fc_item: FeatherCore) -> pygame.Rect:
    """Return a pygame.Rect for a Feather Core item."""
    if hasattr(fc_item, "get_rect"):
        return fc_item.get_rect()

    return pygame.Rect(
        int(getattr(fc_item, "x", RECT_DEFAULT_X)),
        int(getattr(fc_item, "y", RECT_DEFAULT_Y)),
        int(getattr(fc_item, "width", FC_ITEM_DEFAULT_SIZE)),
        int(getattr(fc_item, "height", FC_ITEM_DEFAULT_SIZE)),
    )


def _collect_fc_item(fc_item: FeatherCore) -> int:
    """Collect a Feather Core object or deactivate a legacy placeholder."""
    if hasattr(fc_item, "collect"):
        return int(fc_item.collect())

    fc_item.active = False
    return int(getattr(fc_item, "value", FC_DEFAULT_VALUE))
