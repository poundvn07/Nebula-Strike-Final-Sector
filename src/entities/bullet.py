"""Bullet entity and object pool for projectile reuse."""

from __future__ import annotations

from typing import Literal, TYPE_CHECKING

import pygame

from src.entities.game_object import GameObject
from src.utils.constants import MIN_HEALTH, SCREEN_HEIGHT, SCREEN_WIDTH

if TYPE_CHECKING:
    from src.weapons.weapon import WeaponType

BulletOwner = Literal["player", "enemy"]

PLAYER_BULLET_OWNER = "player"
ENEMY_BULLET_OWNER = "enemy"
BULLET_DEFAULT_X = 0.0
BULLET_DEFAULT_Y = 0.0
BULLET_DEFAULT_VELOCITY = 0.0
BULLET_DEFAULT_WIDTH = 8
BULLET_DEFAULT_HEIGHT = 12
BULLET_DEFAULT_HP = 1
BULLET_DEFAULT_DAMAGE = 1
BULLET_DEFAULT_AOE_RADIUS = 0
BULLET_OFFSCREEN_MARGIN = 64
BULLET_POOL_DEFAULT_SIZE = 128
CHAIN_DAMAGE_MULTIPLIER = 0.5
PLAYER_BULLET_COLOR = (80, 220, 255)
ENEMY_BULLET_COLOR = (255, 180, 80)


class Bullet(GameObject):
    """GameObject projectile that carries owner, damage, and weapon effect data."""

    def __init__(
        self,
        x: float = BULLET_DEFAULT_X,
        y: float = BULLET_DEFAULT_Y,
        vx: float = BULLET_DEFAULT_VELOCITY,
        vy: float = BULLET_DEFAULT_VELOCITY,
        damage: int = BULLET_DEFAULT_DAMAGE,
        owner: BulletOwner = PLAYER_BULLET_OWNER,
        weapon_type: "WeaponType | None" = None,
        is_piercing: bool = False,
        is_aoe: bool = False,
        aoe_radius: int = BULLET_DEFAULT_AOE_RADIUS,
        width: int = BULLET_DEFAULT_WIDTH,
        height: int = BULLET_DEFAULT_HEIGHT,
    ) -> None:
        """Initialize a projectile with reusable pool-friendly state."""
        super().__init__(x=x, y=y, width=width, height=height, hp=BULLET_DEFAULT_HP, vx=vx, vy=vy)
        self.reset(
            x=x,
            y=y,
            vx=vx,
            vy=vy,
            damage=damage,
            owner=owner,
            weapon_type=weapon_type,
            is_piercing=is_piercing,
            is_aoe=is_aoe,
            aoe_radius=aoe_radius,
            width=width,
            height=height,
        )

    @property
    def piercing(self) -> bool:
        """Alias used by weapon combo code for piercing bullets."""
        return self.is_piercing

    @piercing.setter
    def piercing(self, value: bool) -> None:
        self.is_piercing = value

    @property
    def explosion_radius(self) -> int:
        """Alias used by weapon combo code for AOE radius."""
        return self.aoe_radius

    @explosion_radius.setter
    def explosion_radius(self, value: float) -> None:
        self.aoe_radius = int(value)
        self.is_aoe = self.aoe_radius > BULLET_DEFAULT_AOE_RADIUS

    def reset(
        self,
        x: float = BULLET_DEFAULT_X,
        y: float = BULLET_DEFAULT_Y,
        vx: float = BULLET_DEFAULT_VELOCITY,
        vy: float = BULLET_DEFAULT_VELOCITY,
        damage: int = BULLET_DEFAULT_DAMAGE,
        owner: BulletOwner = PLAYER_BULLET_OWNER,
        weapon_type: "WeaponType | None" = None,
        is_piercing: bool = False,
        is_aoe: bool = False,
        aoe_radius: int = BULLET_DEFAULT_AOE_RADIUS,
        width: int = BULLET_DEFAULT_WIDTH,
        height: int = BULLET_DEFAULT_HEIGHT,
    ) -> None:
        """Reset all mutable fields so pooled bullets can be reused safely."""
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.width = width
        self.height = height
        self.hp = BULLET_DEFAULT_HP
        self.max_hp = BULLET_DEFAULT_HP
        self.active = True
        self.damage = damage
        self.owner = owner
        self.weapon_type = weapon_type
        self.is_piercing = is_piercing
        self.is_aoe = is_aoe or aoe_radius > BULLET_DEFAULT_AOE_RADIUS
        self.aoe_radius = aoe_radius
        self.debuffs: dict[str, object] = {}
        self.chain_targets = 0
        self.combo_targets: list[object] = []
        self.metadata: dict[str, object] = {}

    def update(self, dt: float) -> None:
        """Move the bullet and deactivate it once it leaves the screen margin."""
        self.x += self.vx * dt
        self.y += self.vy * dt
        if (
            self.x < -BULLET_OFFSCREEN_MARGIN
            or self.x > SCREEN_WIDTH + BULLET_OFFSCREEN_MARGIN
            or self.y < -BULLET_OFFSCREEN_MARGIN
            or self.y > SCREEN_HEIGHT + BULLET_OFFSCREEN_MARGIN
        ):
            self.active = False

    def render(self, surface: pygame.Surface) -> None:
        """Draw the bullet as a colored rectangle until sprites are available."""
        color = PLAYER_BULLET_COLOR if self.owner == PLAYER_BULLET_OWNER else ENEMY_BULLET_COLOR
        pygame.draw.rect(surface, color, self.get_rect())

    def on_death(self) -> None:
        """Deactivate the projectile when its lifecycle ends."""
        self.active = False

    def on_hit(self, target: object) -> list[object]:
        """Apply damage and supported status effects to a collision target."""
        drops = _apply_damage(target, self.damage, self.weapon_type, self.is_aoe)
        self._apply_status_effects(target)
        self._apply_chain_effects(target)
        if not self.is_piercing:
            self.active = False
        return drops

    def _apply_status_effects(self, target: object) -> None:
        """Attach slow, stun, freeze, or other debuffs to a target object."""
        if not self.debuffs:
            return

        existing_effects = getattr(target, "status_effects", {})
        merged_effects = dict(existing_effects)
        merged_effects.update(self.debuffs)
        target.status_effects = merged_effects

    def _apply_chain_effects(self, target: object) -> None:
        """Apply reduced chain damage to combo-provided nearby targets."""
        if self.chain_targets <= MIN_HEALTH or not self.combo_targets:
            return

        chain_damage = int(self.damage * CHAIN_DAMAGE_MULTIPLIER)
        chained = 0
        for chained_target in self.combo_targets:
            if chained_target is target:
                continue
            _apply_damage(chained_target, chain_damage, self.weapon_type, self.is_aoe)
            chained += 1
            if chained >= self.chain_targets:
                return


class BulletPool:
    """Object pool that reuses Bullet instances to reduce projectile churn."""

    def __init__(self, max_size: int = BULLET_POOL_DEFAULT_SIZE) -> None:
        """Initialize an empty bullet pool with a maximum retained size."""
        self.max_size = max_size
        self._available: list[Bullet] = []

    def get(
        self,
        x: float = BULLET_DEFAULT_X,
        y: float = BULLET_DEFAULT_Y,
        vx: float = BULLET_DEFAULT_VELOCITY,
        vy: float = BULLET_DEFAULT_VELOCITY,
        damage: int = BULLET_DEFAULT_DAMAGE,
        owner: BulletOwner = PLAYER_BULLET_OWNER,
        weapon_type: "WeaponType | None" = None,
        is_piercing: bool = False,
        is_aoe: bool = False,
        aoe_radius: int = BULLET_DEFAULT_AOE_RADIUS,
        width: int = BULLET_DEFAULT_WIDTH,
        height: int = BULLET_DEFAULT_HEIGHT,
    ) -> Bullet:
        """Return a reset Bullet from the pool or create one if needed."""
        bullet = self._available.pop() if self._available else Bullet()
        bullet.reset(
            x=x,
            y=y,
            vx=vx,
            vy=vy,
            damage=damage,
            owner=owner,
            weapon_type=weapon_type,
            is_piercing=is_piercing,
            is_aoe=is_aoe,
            aoe_radius=aoe_radius,
            width=width,
            height=height,
        )
        return bullet

    def release(self, bullet: Bullet) -> None:
        """Return an inactive bullet to the pool if capacity allows."""
        bullet.active = False
        if len(self._available) < self.max_size:
            self._available.append(bullet)


def _apply_damage(
    target: object,
    damage: int,
    weapon_type: "WeaponType | None",
    is_aoe: bool,
) -> list[object]:
    """Call a target's take_damage method while supporting special enemy signatures."""
    take_damage = getattr(target, "take_damage", None)
    if take_damage is None:
        return []

    try:
        result = take_damage(damage, weapon_type=weapon_type, is_aoe=is_aoe)
    except TypeError:
        result = take_damage(damage)

    return list(result or [])
