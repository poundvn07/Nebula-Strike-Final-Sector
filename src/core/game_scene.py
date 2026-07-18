"""Gameplay scene helpers for map-level state transitions."""

from __future__ import annotations

import pygame

from src.core.scene_manager import Scene, SceneManager
from src.enemies.chicken_overlord import ChickenOverlord
from src.entities.bullet import Bullet
from src.entities.effect import Effect
from src.entities.pickup import Pickup
from src.entities.player_ship import PlayerShip
from src.systems.save_manager import SaveManager
from src.systems.wave_manager import WaveManager
from src.ui.hud import HUD
from src.ui.theme import (
    COLOR_ACCENT_HOVER,
    COLOR_MUTED,
    COLOR_PANEL_RAISED,
    COLOR_TEXT,
    draw_button,
    draw_panel,
    mouse_over,
)
from src.utils.resource import (
    background_music_muted,
    load_font,
    load_sprite,
    play_sound,
    sound_effects_muted,
    toggle_background_music_muted,
    toggle_sound_effects_muted,
)
from src.utils.constants import FIRST_MAP_INDEX, MAP_COUNT, SCREEN_HEIGHT, SCREEN_WIDTH

MAP_LOSS_FC_KEEP_RATIO = 0.75


GAME_SCENE_BG_COLOR = (8, 12, 24)
INITIAL_WAVE = 1
FIRE_KEY = pygame.K_SPACE
PAUSE_KEYS = (pygame.K_p, pygame.K_ESCAPE)
CONTROLS_KEY = pygame.K_h
MUTE_SOUND_KEY = pygame.K_m
MUTE_MUSIC_KEY = pygame.K_n
WEAPON_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3)
GO_PHASE = "GO"
COUNTDOWN_PHASES = ("3", "2", "1")
COUNTDOWN_STEP_SECONDS = 1.0
GO_DURATION_SECONDS = 0.5
INTRO_FONT_SIZE = 72
INTRO_TEXT_COLOR = (235, 244, 255)
INTRO_SHADOW_COLOR = (18, 24, 36)
PAUSE_OVERLAY_COLOR = (4, 8, 18)
PAUSE_TEXT_COLOR = (235, 244, 255)
PAUSE_TITLE_FONT_SIZE = 48
PAUSE_FONT_SIZE = 24
PAUSE_SMALL_FONT_SIZE = 20
PAUSE_MENU_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 210, 128, 420, 500)
PAUSE_RESUME_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 150, 300, 300, 52)
PAUSE_CONTROLS_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 150, 370, 300, 52)
PAUSE_SOUND_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 150, 450, 142, 48)
PAUSE_MUSIC_RECT = pygame.Rect(SCREEN_WIDTH // 2 + 8, 450, 142, 48)
CONTROLS_PANEL_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 350, 54, 700, 660)
CONTROLS_BACK_RECT = pygame.Rect(SCREEN_WIDTH // 2 - 130, 642, 260, 46)
RESPAWN_INVULNERABLE_SECONDS = 0.8
RESET_MAP_UNLOCKED = [True, False, False, False, False]
CONTROL_BINDINGS = (
    ("WASD / ARROWS", "Move ship"),
    ("SPACE", "Fire active weapon"),
    ("TAB", "Cycle weapon"),
    ("1 / 2 / 3", "Select weapon slot"),
    ("HOLD 2 SLOTS", "Combo attack"),
    ("Q", "Toggle drone mode"),
    ("P / ESC", "Pause or resume"),
    ("H", "Open controls"),
    ("M", "Mute sound effects"),
    ("N", "Mute music"),
    ("MOUSE", "Menus and upgrades"),
    ("MAX LV PAIR", "Unlock weapon combo"),
)


class GameScene(Scene):
    """Scene-level owner for map combat, wave progression, and result transitions."""

    def __init__(
        self,
        player: PlayerShip,
        save_manager: SaveManager | None = None,
        game_state: dict | None = None,
        scene_manager: SceneManager | None = None,
    ) -> None:
        """Initialize the scene with player, save manager, and map progress state."""
        self.player = player
        self.save_manager = save_manager or SaveManager()
        self.game_state = dict(game_state or {})
        self.current_map = int(self.game_state.get("current_map", FIRST_MAP_INDEX))
        self.scene_manager = scene_manager
        self.wave_manager = WaveManager(self.current_map)
        self.hud = HUD()
        self.bullets: list[Bullet] = []
        self.fc_items: list[Pickup] = []
        self.effects: list[Effect] = []
        self.fc_earned_this_map = 0
        self.total_waves = int(self.wave_manager.map_config["waves"])
        self.reload_map_number: int | None = None
        self._last_combo_name: object | None = None
        self._transitioned_to_result = False
        self._wave_intro_phase = ""
        self._wave_intro_timer = 0.0
        self._respawn_invulnerable_timer = 0.0
        self.paused = False
        self.controls_visible = False
        self._held_combo_pair: tuple[int, int] | None = None
        self._intro_font: pygame.font.Font | None = None
        self._pause_title_font: pygame.font.Font | None = None
        self._pause_font: pygame.font.Font | None = None
        self._pause_small_font: pygame.font.Font | None = None
        self._start_wave(INITIAL_WAVE)

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle gameplay input events."""
        if event.type == pygame.MOUSEBUTTONDOWN and self._is_pause_overlay_active():
            self._handle_pause_click(event.pos)
            return
        if event.type == pygame.KEYDOWN:
            if event.key in PAUSE_KEYS:
                self._toggle_pause()
                return
            if event.key == CONTROLS_KEY:
                self._toggle_controls_guide()
                return
            if event.key == MUTE_SOUND_KEY:
                toggle_sound_effects_muted()
                return
            if event.key == MUTE_MUSIC_KEY:
                toggle_background_music_muted()
                return
            if self._is_pause_overlay_active():
                return

        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_TAB:
            self.player.cycle_weapon_slot()
        elif event.key == pygame.K_q:
            self.player.toggle_drone_mode()
        elif event.key in WEAPON_KEYS:
            self.player.select_weapon_slot(WEAPON_KEYS.index(event.key))

    def update(self, dt: float) -> None:
        """Advance combat systems and transition to results when the map resolves."""
        if self._transitioned_to_result:
            return
        if self._is_pause_overlay_active():
            return

        if self._is_wave_intro_active():
            self._update_player(dt)
            self._update_wave_intro(dt)
            self._update_effects(dt)
            self.hud.update(dt, combo_name=self._last_combo_name)
            return

        if self._respawn_invulnerable_timer > 0.0:
            self._respawn_invulnerable_timer = max(0.0, self._respawn_invulnerable_timer - dt)

        self._update_player(dt)
        self._sync_enemy_threats()
        self.wave_manager.update(dt)
        self._collect_enemy_attack_bullets()
        keys_pressed = pygame.key.get_pressed()
        self._activate_combo_if_pressed(keys_pressed)
        self._fire_player_weapons(dt, keys_pressed)
        self._update_drones(dt)
        self._update_gameplay_objects(dt)
        if self._respawn_invulnerable_timer <= 0.0:
            self._check_collisions()
        self._spawn_enemy_death_explosions()
        self._prune_inactive_objects()
        self._notify_bosses_of_minion_deaths()
        self.hud.update(dt, combo_name=self._last_combo_name)

        if not self.player.is_alive():
            self._handle_player_defeat()
        elif self.wave_manager.is_wave_clear():
            self._handle_wave_clear()

    def render(self, surface: pygame.Surface) -> None:
        """Render gameplay entities, then draw HUD on top."""
        self._render_background(surface)
        self._render_gameplay_objects(surface)
        self._render_intro_overlay(surface)
        self.hud.render(
            surface,
            self.player,
            current_wave=self.wave_manager.current_wave,
            total_waves=self.total_waves,
            boss=self._get_active_boss(),
            combo_name=self._last_combo_name,
        )
        self._render_pause_overlay(surface)

    def on_map_lose(self) -> bool:
        """Apply FC penalty, preserve loadout/HP, save, then keep the same map active."""
        self.player._fc_inventory = int(self.player.fc_inventory * MAP_LOSS_FC_KEEP_RATIO)
        self.game_state["current_map"] = self.current_map
        self.reload_map_number = self.current_map
        return self.save_manager.save(self.player, self.game_state)

    def _update_player(self, dt: float) -> None:
        """Move the player from keyboard state and tick weapon cooldowns."""
        self.player.move(pygame.key.get_pressed(), dt)
        self.player.update(dt)
        self.player.set_auto_targets(self.wave_manager.enemies_alive)

    def _collect_enemy_attack_bullets(self) -> None:
        """Add enemy bullets emitted by WaveManager-updated enemies this frame."""
        for enemy in self.wave_manager.enemies_alive:
            emitted_bullets = [
                bullet
                for bullet in getattr(enemy, "last_attack_bullets", [])
                if getattr(bullet, "active", True)
            ]
            self.bullets.extend(emitted_bullets)
            enemy.last_attack_bullets = []

    def _sync_enemy_threats(self) -> None:
        """Provide current player state to enemies with reactive movement logic."""
        player_bullets = [
            bullet
            for bullet in self.bullets
            if getattr(bullet, "owner", None) == "player" and getattr(bullet, "active", True)
        ]
        player_center = (
            self.player.x + self.player.width / 2,
            self.player.y + self.player.height / 2,
        )
        for enemy in self.wave_manager.enemies_alive:
            if hasattr(enemy, "incoming_bullets"):
                enemy.incoming_bullets = player_bullets
            if hasattr(enemy, "player_position"):
                enemy.player_position = player_center

    def _activate_combo_if_pressed(self, keys_pressed: object) -> None:
        """Activate one combo attack when a valid weapon key pair is newly pressed."""
        combo_pair = _pressed_combo_pair(keys_pressed)
        if combo_pair is None:
            self._held_combo_pair = None
            return
        if combo_pair == self._held_combo_pair:
            return

        self._held_combo_pair = combo_pair
        fired_bullets, combo = self.player.activate_combo(combo_pair[0], combo_pair[1])
        if not fired_bullets or combo is None:
            return

        self._last_combo_name = combo
        self.bullets.extend(fired_bullets)

    def _fire_player_weapons(self, dt: float, keys_pressed: object | None = None) -> None:
        """Fire ready player weapons only while the player holds Space."""
        if self._is_wave_intro_active():
            return
        if keys_pressed is None:
            keys_pressed = pygame.key.get_pressed()
        if not _is_fire_pressed(keys_pressed):
            return

        fired_bullets = self.player.fire(dt)
        if not fired_bullets:
            return

        self.bullets.extend(fired_bullets)

    def _update_drones(self, dt: float) -> None:
        """Update PlayerShip-owned drones and collect their emitted bullets."""
        enemy_bullets = [
            bullet
            for bullet in self.bullets
            if getattr(bullet, "owner", None) == "enemy" and getattr(bullet, "active", True)
        ]
        self.bullets.extend(
            self.player.update_drones(
                dt,
                self.wave_manager.enemies_alive,
                self.fc_items,
                enemy_bullets,
            )
        )

    def _update_gameplay_objects(self, dt: float) -> None:
        """Tick bullets and Feather Core lifetimes."""
        for bullet in self.bullets:
            if getattr(bullet, "active", True):
                bullet.update(dt)
        for fc_item in self.fc_items:
            if getattr(fc_item, "active", True):
                fc_item.update(dt)
        self._update_effects(dt)

    def _update_effects(self, dt: float) -> None:
        """Advance generic effects and remove completed animations."""
        for effect in self.effects:
            if getattr(effect, "active", True):
                effect.update(dt)
        self.effects = [effect for effect in self.effects if getattr(effect, "active", False)]

    def _spawn_enemy_death_explosions(self) -> None:
        """Create one generic explosion effect for each enemy that died this frame."""
        for enemy in self.wave_manager.enemies_alive:
            if getattr(enemy, "active", True) or getattr(enemy, "_death_explosion_spawned", False):
                continue
            enemy._death_explosion_spawned = True
            effect_size = max(int(enemy.width), int(enemy.height), 44) + 18
            self.effects.append(
                Effect(
                    enemy.x + enemy.width / 2 - effect_size / 2,
                    enemy.y + enemy.height / 2 - effect_size / 2,
                    effect_size,
                    effect_size,
                )
            )

    def _prune_inactive_objects(self) -> None:
        """Remove inactive bullets, expired FC pickups, and dead enemies."""
        self.bullets = [bullet for bullet in self.bullets if getattr(bullet, "active", False)]
        self.fc_items = [fc_item for fc_item in self.fc_items if getattr(fc_item, "active", False)]
        self.wave_manager.enemies_alive = [
            enemy
            for enemy in self.wave_manager.enemies_alive
            if getattr(enemy, "active", False) and enemy.is_alive()
        ]

    def _check_collisions(self) -> None:
        """Resolve bullets, ramming enemies, and FC pickups during scene update."""
        self.player.set_auto_targets(self.wave_manager.enemies_alive)
        for bullet in self.bullets:
            if not getattr(bullet, "active", True):
                continue
            if getattr(bullet, "owner", "player") == "enemy":
                if bullet.get_rect().colliderect(self.player.get_rect()):
                    bullet.on_hit(self.player)
                    self.player.on_player_hit()
                continue
            self._check_player_bullet_collision(bullet)

        player_rect = self.player.get_rect()
        for enemy in self.wave_manager.enemies_alive:
            if not getattr(enemy, "active", True) or not player_rect.colliderect(enemy.get_rect()):
                continue
            damage = int(getattr(enemy, "collision_damage", 0))
            if damage > 0:
                self.player.take_damage(damage)
                enemy.hp = 0
                enemy.active = False
                self.player.on_player_hit()

        for item in self.fc_items:
            if getattr(item, "active", True) and player_rect.colliderect(item.get_rect()):
                self.player.add_fc(item.collect())
                self.player.on_fc_collected()

    def _check_player_bullet_collision(self, bullet: Bullet) -> None:
        """Apply player bullet damage and collect enemy drops into scene state."""
        hit_rect = bullet.get_rect()
        if (bullet.is_aoe or bullet.aoe_radius > 0) and bullet.aoe_radius > 0:
            hit_rect = hit_rect.inflate(int(bullet.aoe_radius) * 2, int(bullet.aoe_radius) * 2)
        for enemy in self.wave_manager.enemies_alive:
            if not getattr(enemy, "active", True) or not hit_rect.colliderect(enemy.get_rect()):
                continue
            was_alive = enemy.is_alive()
            base_damage = bullet.damage
            bullet.damage = base_damage * self.player.get_damage_multiplier()
            try:
                drops = bullet.on_hit(enemy)
            finally:
                bullet.damage = base_damage
            if was_alive and not enemy.is_alive():
                self.player.score += int(getattr(enemy, "score_value", 1))
                self.fc_items.extend(drops)
            if not getattr(bullet, "active", True):
                return

    def _notify_bosses_of_minion_deaths(self) -> None:
        """Keep ChickenOverlord healing lists aligned after collision damage."""
        for enemy in self.wave_manager.enemies_alive:
            if not isinstance(enemy, ChickenOverlord):
                continue
            for minion in list(enemy.minions_alive):
                if not minion.is_alive():
                    enemy.on_minion_death(minion)

    def _handle_wave_clear(self) -> None:
        """Start the next wave or finish the map when the final wave is clear."""
        self.hud.show_wave_clear()
        play_sound("wave_clear")
        self.fc_earned_this_map += self.wave_manager.get_wave_reward()
        if self.wave_manager.current_wave >= self.total_waves:
            self._transition_to_win()
            return

        next_wave = self.wave_manager.current_wave + 1
        self.game_state["highest_wave_reached"] = max(
            int(self.game_state.get("highest_wave_reached", INITIAL_WAVE)),
            next_wave,
        )
        self.save_manager.save(self.player, self.game_state)
        self._start_wave(next_wave)

    def _handle_player_defeat(self) -> None:
        """Respawn on remaining lives, otherwise perform a full run reset."""
        if self.player.consume_life():
            self._respawn_player()
            return
        self._transition_to_loss()

    def _respawn_player(self) -> None:
        """Restore the player after losing one life and restart safe gameplay."""
        self.player.respawn()
        self.bullets.clear()
        self._respawn_invulnerable_timer = RESPAWN_INVULNERABLE_SECONDS
        self._begin_wave_intro()

    def _start_wave(self, wave_num: int) -> None:
        """Start a wave immediately, with combat gated by countdown intro text."""
        self.bullets.clear()
        self.wave_manager.start_wave(wave_num)
        if self.wave_manager.should_spawn_all_on_intro():
            self.wave_manager.spawn_pending_now()
        self._begin_wave_intro()

    def _begin_wave_intro(self) -> None:
        """Show 3, 2, 1, then GO before combat systems can act."""
        self._wave_intro_phase = COUNTDOWN_PHASES[0]
        self._wave_intro_timer = COUNTDOWN_STEP_SECONDS

    def _update_wave_intro(self, dt: float) -> None:
        """Tick the countdown intro state machine."""
        if not self._is_wave_intro_active():
            return

        self._wave_intro_timer -= dt
        if self._wave_intro_timer > 0.0:
            return

        if self._wave_intro_phase in COUNTDOWN_PHASES:
            phase_index = COUNTDOWN_PHASES.index(self._wave_intro_phase)
            if phase_index < len(COUNTDOWN_PHASES) - 1:
                self._wave_intro_phase = COUNTDOWN_PHASES[phase_index + 1]
                self._wave_intro_timer = COUNTDOWN_STEP_SECONDS
            else:
                self._wave_intro_phase = GO_PHASE
                self._wave_intro_timer = GO_DURATION_SECONDS
        else:
            self._wave_intro_phase = ""
            self._wave_intro_timer = 0.0

    def _is_wave_intro_active(self) -> bool:
        """Return whether countdown/GO is currently blocking combat."""
        return bool(self._wave_intro_phase)

    def _toggle_pause(self) -> None:
        """Toggle paused gameplay state."""
        if self.controls_visible:
            self.controls_visible = False
            self.paused = True
            return
        self.paused = not self.paused

    def _toggle_controls_guide(self) -> None:
        """Toggle the dedicated controls panel while keeping gameplay paused."""
        self.controls_visible = not self.controls_visible
        self.paused = True

    def _handle_pause_click(self, position: tuple[int, int]) -> None:
        """Handle pause-menu and controls-panel mouse actions."""
        if self.controls_visible:
            if CONTROLS_BACK_RECT.collidepoint(position):
                self.controls_visible = False
                self.paused = True
            return
        if PAUSE_RESUME_RECT.collidepoint(position):
            self.paused = False
        elif PAUSE_CONTROLS_RECT.collidepoint(position):
            self.controls_visible = True
            self.paused = True
        elif PAUSE_SOUND_RECT.collidepoint(position):
            toggle_sound_effects_muted()
        elif PAUSE_MUSIC_RECT.collidepoint(position):
            toggle_background_music_muted()

    def _is_pause_overlay_active(self) -> bool:
        """Return whether pause or controls overlay is currently blocking gameplay."""
        return self.paused or self.controls_visible

    def _transition_to_win(self) -> None:
        """Replace gameplay with a win ResultScene."""
        self._transitioned_to_result = True
        play_sound("result")
        self._unlock_next_map()
        self.game_state["current_map"] = self.current_map
        self.game_state["highest_wave_reached"] = self.total_waves
        if self.scene_manager is None:
            return

        from src.ui.result_screen import ResultScene

        self.scene_manager.replace(
            ResultScene(
                self.player,
                self.scene_manager,
                self.save_manager,
                self.game_state,
                won=True,
                fc_earned=self.fc_earned_this_map,
            )
        )

    def _transition_to_loss(self) -> None:
        """Reset run state after the final life and replace gameplay with ResultScene."""
        self._transitioned_to_result = True
        play_sound("result")
        reset_player = PlayerShip()
        reset_player.reset_for_new_run()
        self.save_manager.apply_starting_loadout(reset_player)
        reset_state = {
            "current_map": FIRST_MAP_INDEX,
            "highest_wave_reached": INITIAL_WAVE,
            "map_unlocked": list(RESET_MAP_UNLOCKED),
        }
        self.save_manager.save(reset_player, reset_state)
        if self.scene_manager is None:
            return

        from src.ui.result_screen import ResultScene

        self.scene_manager.replace(
            ResultScene(
                reset_player,
                self.scene_manager,
                self.save_manager,
                reset_state,
                won=False,
            )
        )

    def _unlock_next_map(self) -> None:
        """Mark the next map as unlocked in save-ready game state."""
        map_unlocked = list(self.game_state.get("map_unlocked", [True] + [False] * (MAP_COUNT - 1)))
        while len(map_unlocked) < MAP_COUNT:
            map_unlocked.append(False)
        if self.current_map < MAP_COUNT:
            map_unlocked[self.current_map] = True
        self.game_state["map_unlocked"] = map_unlocked

    def _render_gameplay_objects(self, surface: pygame.Surface) -> None:
        """Draw all active combat objects before the HUD."""
        for fc_item in self.fc_items:
            if getattr(fc_item, "active", True):
                fc_item.render(surface)
        for enemy in self.wave_manager.enemies_alive:
            if getattr(enemy, "active", True):
                enemy.render(surface)
        for bullet in self.bullets:
            if getattr(bullet, "active", True):
                bullet.render(surface)
        for effect in self.effects:
            if getattr(effect, "active", True):
                effect.render(surface)
        for drone in self.player.drones:
            if getattr(drone, "active", True):
                drone.render(surface)
        self.player.render(surface)

    def _render_background(self, surface: pygame.Surface) -> None:
        """Render the sprite background, using the flat color as fallback."""
        background = load_sprite("background", (SCREEN_WIDTH, SCREEN_HEIGHT))
        if background is None:
            surface.fill(GAME_SCENE_BG_COLOR)
            return
        surface.blit(background, (0, 0))

    def _render_intro_overlay(self, surface: pygame.Surface) -> None:
        """Draw countdown or GO centered over the spawned wave."""
        if not self._is_wave_intro_active():
            return
        font = self._get_intro_font()
        text = self._wave_intro_phase
        center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        shadow_surface = font.render(text, True, INTRO_SHADOW_COLOR)
        text_surface = font.render(text, True, INTRO_TEXT_COLOR)
        surface.blit(shadow_surface, shadow_surface.get_rect(center=(center[0] + 4, center[1] + 4)))
        surface.blit(text_surface, text_surface.get_rect(center=center))

    def _render_pause_overlay(self, surface: pygame.Surface) -> None:
        """Draw either the compact pause menu or the requested controls panel."""
        if not self._is_pause_overlay_active():
            return

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill(PAUSE_OVERLAY_COLOR)
        overlay.set_alpha(226)
        surface.blit(overlay, (0, 0))

        if self.controls_visible:
            self._draw_controls_panel(surface)
        else:
            self._draw_pause_menu(surface)

    def _draw_pause_menu(self, surface: pygame.Surface) -> None:
        """Draw pause actions without exposing the full keybind guide."""
        draw_panel(surface, PAUSE_MENU_RECT, raised=True)
        eyebrow = self._get_pause_small_font().render("GAME PAUSED", True, COLOR_ACCENT_HOVER)
        surface.blit(eyebrow, eyebrow.get_rect(center=(SCREEN_WIDTH // 2, PAUSE_MENU_RECT.y + 38)))
        title = self._get_pause_title_font().render("Take a Breather", True, COLOR_TEXT)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, PAUSE_MENU_RECT.y + 88)))
        subtitle = self._get_pause_small_font().render("Combat and timers are frozen", True, COLOR_MUTED)
        surface.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH // 2, PAUSE_MENU_RECT.y + 128)))

        draw_button(
            surface,
            PAUSE_RESUME_RECT,
            "Resume Game",
            self._get_pause_font(),
            primary=True,
            hovered=mouse_over(PAUSE_RESUME_RECT),
        )
        draw_button(
            surface,
            PAUSE_CONTROLS_RECT,
            "View Controls",
            self._get_pause_font(),
            hovered=mouse_over(PAUSE_CONTROLS_RECT),
        )

        sound_label = "Muted" if sound_effects_muted() else "On"
        music_label = "Muted" if background_music_muted() else "On"
        draw_button(
            surface,
            PAUSE_SOUND_RECT,
            f"SFX: {sound_label}",
            self._get_pause_small_font(),
            hovered=mouse_over(PAUSE_SOUND_RECT),
        )
        draw_button(
            surface,
            PAUSE_MUSIC_RECT,
            f"Music: {music_label}",
            self._get_pause_small_font(),
            hovered=mouse_over(PAUSE_MUSIC_RECT),
        )
        hint = self._get_pause_small_font().render("P / Esc resumes    |    H opens controls", True, COLOR_MUTED)
        surface.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, PAUSE_MENU_RECT.bottom - 56)))

    def _draw_controls_panel(self, surface: pygame.Surface) -> None:
        """Draw keybinds only after the player explicitly requests them."""
        draw_panel(surface, CONTROLS_PANEL_RECT, raised=True)
        eyebrow = self._get_pause_small_font().render("REFERENCE", True, COLOR_ACCENT_HOVER)
        surface.blit(eyebrow, eyebrow.get_rect(center=(SCREEN_WIDTH // 2, CONTROLS_PANEL_RECT.y + 34)))
        title = self._get_pause_title_font().render("Controls", True, COLOR_TEXT)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, CONTROLS_PANEL_RECT.y + 78)))
        subtitle = self._get_pause_small_font().render("Everything you need during a mission", True, COLOR_MUTED)
        surface.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH // 2, CONTROLS_PANEL_RECT.y + 118)))

        column_width = 306
        row_height = 58
        row_gap = 10
        start_x = CONTROLS_PANEL_RECT.x + 30
        start_y = CONTROLS_PANEL_RECT.y + 150
        for index, (key, action) in enumerate(CONTROL_BINDINGS):
            column = index // 6
            row = index % 6
            rect = pygame.Rect(
                start_x + column * (column_width + 28),
                start_y + row * (row_height + row_gap),
                column_width,
                row_height,
            )
            pygame.draw.rect(surface, COLOR_PANEL_RAISED, rect, border_radius=8)
            key_surface = self._get_pause_small_font().render(key, True, COLOR_ACCENT_HOVER)
            action_surface = self._get_pause_small_font().render(action, True, PAUSE_TEXT_COLOR)
            surface.blit(key_surface, (rect.x + 14, rect.y + 8))
            surface.blit(action_surface, (rect.x + 14, rect.y + 31))

        draw_button(
            surface,
            CONTROLS_BACK_RECT,
            "Back to Pause",
            self._get_pause_small_font(),
            primary=True,
            hovered=mouse_over(CONTROLS_BACK_RECT),
        )

    def _get_intro_font(self) -> pygame.font.Font:
        """Create the countdown font lazily."""
        if self._intro_font is None:
            self._intro_font = load_font(INTRO_FONT_SIZE)
        return self._intro_font

    def _get_pause_title_font(self) -> pygame.font.Font:
        """Create the pause title font lazily."""
        if self._pause_title_font is None:
            self._pause_title_font = load_font(PAUSE_TITLE_FONT_SIZE)
        return self._pause_title_font

    def _get_pause_font(self) -> pygame.font.Font:
        """Create the pause guide font lazily."""
        if self._pause_font is None:
            self._pause_font = load_font(PAUSE_FONT_SIZE)
        return self._pause_font

    def _get_pause_small_font(self) -> pygame.font.Font:
        """Create the pause status font lazily."""
        if self._pause_small_font is None:
            self._pause_small_font = load_font(PAUSE_SMALL_FONT_SIZE)
        return self._pause_small_font

    def _get_active_boss(self) -> object | None:
        """Return the active boss enemy for HUD display, if present."""
        for enemy in self.wave_manager.enemies_alive:
            if getattr(enemy, "health_bar_visible", False) and getattr(enemy, "active", True):
                return enemy
        return None


def _is_fire_pressed(keys_pressed: object) -> bool:
    """Return whether Space is pressed for dict-like or sequence key states."""
    return _is_key_pressed(keys_pressed, FIRE_KEY)


def _pressed_combo_pair(keys_pressed: object) -> tuple[int, int] | None:
    """Return a newly held weapon-slot pair for combo activation."""
    pressed_slots = tuple(
        slot_index
        for slot_index, key in enumerate(WEAPON_KEYS)
        if _is_key_pressed(keys_pressed, key)
    )
    if len(pressed_slots) != 2:
        return None
    return pressed_slots[0], pressed_slots[1]


def _is_key_pressed(keys_pressed: object, key: int) -> bool:
    """Return whether a key is pressed for dict-like or sequence key states."""
    if hasattr(keys_pressed, "get"):
        return bool(keys_pressed.get(key, False))
    try:
        return bool(keys_pressed[key])  # type: ignore[index]
    except (IndexError, KeyError, TypeError):
        return False
