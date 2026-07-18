"""Lightweight resource-loading utilities for sprites, sounds, and fonts."""

from __future__ import annotations

from pathlib import Path

import pygame

ASSET_ROOT = Path(__file__).resolve().parents[2] / "assets"
SPRITE_ROOT = ASSET_ROOT / "sprites"
AUDIO_ROOT = ASSET_ROOT / "audio"
_get_default_font = getattr(pygame.font, "get_default_font", None)
PORTABLE_UI_FONT = _get_default_font() if callable(_get_default_font) else "freesansbold.ttf"

SPRITE_FILES = {
    "background": SPRITE_ROOT / "background.png", "victory_background": SPRITE_ROOT / "victory_background.png",
    "defeat_background": SPRITE_ROOT / "defeat_background.png", "player_ship": SPRITE_ROOT / "spaceship.png",
    "drone": SPRITE_ROOT / "drone.png", "enemy_grunt": SPRITE_ROOT / "alien1.png",
    "enemy_bomber": SPRITE_ROOT / "alien2.png", "enemy_dodge": SPRITE_ROOT / "alien3.png",
    "enemy_armored": SPRITE_ROOT / "alien4.png", "enemy_kamikaze": SPRITE_ROOT / "alien5.png",
    "boss_space_rooster": SPRITE_ROOT / "alien4.png", "boss_chicken_overlord": SPRITE_ROOT / "alien5.png",
    "player_bullet": SPRITE_ROOT / "bullet.png", "combo_bullet": SPRITE_ROOT / "laser.png",
    "enemy_bullet": SPRITE_ROOT / "alien_bullet.png", "lives_icon": SPRITE_ROOT / "lives.png",
    "explosion_1": SPRITE_ROOT / "explosion1.png", "explosion_2": SPRITE_ROOT / "explosion2.png",
    "explosion_3": SPRITE_ROOT / "explosion3.png", "explosion_4": SPRITE_ROOT / "explosion4.png",
    "explosion_5": SPRITE_ROOT / "explosion5.png",
}
ENEMY_SPRITE_KEYS = {
    "ChickenGrunt": "enemy_grunt", "EggBomber": "enemy_bomber", "KamikazeChicken": "enemy_kamikaze",
    "ArmoredRooster": "enemy_armored", "DodgeHen": "enemy_dodge", "SpaceRooster": "boss_space_rooster",
    "ChickenOverlord": "boss_chicken_overlord",
}
SOUND_FILES = {
    "player_fire": AUDIO_ROOT / "laser.mp3", "enemy_explosion": AUDIO_ROOT / "explosion.wav",
    "boss_explosion": AUDIO_ROOT / "explosion2.wav", "wave_clear": AUDIO_ROOT / "level_up_2.wav",
    "menu_select": AUDIO_ROOT / "ui-completed-status-alert-notification.wav", "result": AUDIO_ROOT / "result-9.mp3",
}
BACKGROUND_MUSIC_FILE = AUDIO_ROOT / "game_theme.mp3"
DEFAULT_SOUND_VOLUME = 0.45
BACKGROUND_MUSIC_VOLUME = 0.25
_sprite_cache: dict[tuple[str, tuple[int, int] | None], pygame.Surface | None] = {}
_sound_cache: dict[str, object | None] = {}
_font_cache: dict[tuple[str, int], pygame.font.Font] = {}
_mixer_failed = False
_music_started = False
_sound_effects_muted = False
_background_music_muted = False


def load_image(asset_key: str, size: tuple[int, int] | None = None) -> pygame.Surface | None:
    """Load and cache an image by asset key, returning None when unavailable."""
    cache_key = (asset_key, size)
    if cache_key in _sprite_cache:
        return _sprite_cache[cache_key]
    path = SPRITE_FILES.get(asset_key)
    if path is None or not path.exists() or not hasattr(pygame, "image"):
        _sprite_cache[cache_key] = None
        return None
    try:
        image = pygame.image.load(str(path))
        if hasattr(image, "convert_alpha"):
            try:
                image = image.convert_alpha()
            except Exception:
                pass
        if size is not None and hasattr(pygame, "transform"):
            image = pygame.transform.scale(image, size)
    except Exception:
        image = None
    _sprite_cache[cache_key] = image
    return image


def load_sprite(asset_key: str, size: tuple[int, int] | None = None) -> pygame.Surface | None:
    """Compatibility name for image loading used by existing renderers."""
    return load_image(asset_key, size)


def load_enemy_sprite(enemy: object) -> pygame.Surface | None:
    """Return the correctly sized sprite for an enemy subclass."""
    key = ENEMY_SPRITE_KEYS.get(enemy.__class__.__name__, "enemy_grunt")
    return load_image(key, (max(1, int(getattr(enemy, "width", 1))), max(1, int(getattr(enemy, "height", 1)))))


def load_font(size: int, path: str | None = None) -> pygame.font.Font:
    """Load and cache the pygame-bundled UI font or an explicit font path."""
    resolved_path = path or PORTABLE_UI_FONT
    cache_key = (resolved_path, size)
    if cache_key not in _font_cache:
        _font_cache[cache_key] = pygame.font.Font(resolved_path, size)
    return _font_cache[cache_key]


def load_sound(sound_key: str) -> object | None:
    """Load and cache one sound effect when mixer support is available."""
    if sound_key in _sound_cache:
        return _sound_cache[sound_key]
    path = SOUND_FILES.get(sound_key)
    if path is None or not path.exists() or not _ensure_mixer_ready():
        _sound_cache[sound_key] = None
        return None
    try:
        sound = pygame.mixer.Sound(str(path))
        if hasattr(sound, "set_volume"):
            sound.set_volume(DEFAULT_SOUND_VOLUME)
    except Exception:
        sound = None
    _sound_cache[sound_key] = sound
    return sound


def play_sound(sound_key: str) -> bool:
    """Play a cached sound effect unless effects are muted."""
    if _sound_effects_muted:
        return False
    sound = load_sound(sound_key)
    if sound is None:
        return False
    try:
        sound.play()
    except Exception:
        return False
    return True


def start_background_music() -> bool:
    """Start looping background music once when audio support is available."""
    global _music_started
    if _music_started or not _ensure_mixer_ready() or not BACKGROUND_MUSIC_FILE.exists() or not hasattr(pygame.mixer, "music"):
        return False
    try:
        pygame.mixer.music.load(str(BACKGROUND_MUSIC_FILE))
        pygame.mixer.music.set_volume(_current_music_volume())
        pygame.mixer.music.play(-1)
    except Exception:
        return False
    _music_started = True
    return True


def toggle_sound_effects_muted() -> bool:
    """Toggle sound effect playback and return the new mute state."""
    global _sound_effects_muted
    _sound_effects_muted = not _sound_effects_muted
    return _sound_effects_muted


def toggle_background_music_muted() -> bool:
    """Toggle background music muting and return the new state."""
    global _background_music_muted
    _background_music_muted = not _background_music_muted
    _apply_music_volume()
    return _background_music_muted


def sound_effects_muted() -> bool:
    """Return whether sound effects are muted."""
    return _sound_effects_muted


def background_music_muted() -> bool:
    """Return whether background music is muted."""
    return _background_music_muted


def _current_music_volume() -> float:
    return 0.0 if _background_music_muted else BACKGROUND_MUSIC_VOLUME


def _apply_music_volume() -> None:
    if _ensure_mixer_ready() and hasattr(pygame.mixer, "music"):
        try:
            pygame.mixer.music.set_volume(_current_music_volume())
        except Exception:
            pass


def _ensure_mixer_ready() -> bool:
    global _mixer_failed
    if _mixer_failed or not hasattr(pygame, "mixer"):
        return False
    try:
        if hasattr(pygame.mixer, "get_init") and pygame.mixer.get_init():
            return True
        pygame.mixer.init()
    except Exception:
        _mixer_failed = True
        return False
    return True
