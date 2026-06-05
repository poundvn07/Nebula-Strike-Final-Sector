"""Asset loading helpers for sprites and audio used by gameplay objects."""

from __future__ import annotations

from pathlib import Path

import pygame

ASSET_ROOT = Path(__file__).resolve().parents[2] / "assets"
SPRITE_ROOT = ASSET_ROOT / "sprites"
AUDIO_ROOT = ASSET_ROOT / "audio"

SPRITE_FILES = {
    "background": SPRITE_ROOT / "background.png",
    "player_ship": SPRITE_ROOT / "spaceship.png",
    "enemy_grunt": SPRITE_ROOT / "alien1.png",
    "enemy_bomber": SPRITE_ROOT / "alien2.png",
    "enemy_dodge": SPRITE_ROOT / "alien3.png",
    "enemy_armored": SPRITE_ROOT / "alien4.png",
    "enemy_kamikaze": SPRITE_ROOT / "alien5.png",
    "boss_space_rooster": SPRITE_ROOT / "alien4.png",
    "boss_chicken_overlord": SPRITE_ROOT / "alien5.png",
    "player_bullet": SPRITE_ROOT / "bullet.png",
    "enemy_bullet": SPRITE_ROOT / "alien_bullet.png",
    "explosion_1": SPRITE_ROOT / "explosion1.png",
    "explosion_2": SPRITE_ROOT / "explosion2.png",
    "explosion_3": SPRITE_ROOT / "explosion3.png",
    "explosion_4": SPRITE_ROOT / "explosion4.png",
    "explosion_5": SPRITE_ROOT / "explosion5.png",
}

ENEMY_SPRITE_KEYS = {
    "ChickenGrunt": "enemy_grunt",
    "EggBomber": "enemy_bomber",
    "KamikazeChicken": "enemy_kamikaze",
    "ArmoredRooster": "enemy_armored",
    "DodgeHen": "enemy_dodge",
    "SpaceRooster": "boss_space_rooster",
    "ChickenOverlord": "boss_chicken_overlord",
}

SOUND_FILES = {
    "player_fire": AUDIO_ROOT / "laser.mp3",
    "enemy_explosion": AUDIO_ROOT / "explosion.wav",
    "boss_explosion": AUDIO_ROOT / "explosion2.wav",
    "wave_clear": AUDIO_ROOT / "level_up_2.wav",
    "menu_select": AUDIO_ROOT / "ui-completed-status-alert-notification.wav",
    "result": AUDIO_ROOT / "result-9.mp3",
}

BACKGROUND_MUSIC_FILE = AUDIO_ROOT / "game_theme.mp3"
DEFAULT_SOUND_VOLUME = 0.45
BACKGROUND_MUSIC_VOLUME = 0.35

_sprite_cache: dict[tuple[str, tuple[int, int] | None], pygame.Surface | None] = {}
_sound_cache: dict[str, object | None] = {}
_mixer_failed = False
_music_started = False


def load_sprite(asset_key: str, size: tuple[int, int] | None = None) -> pygame.Surface | None:
    """Load and cache a sprite, returning None when pygame image support is unavailable."""
    cache_key = (asset_key, size)
    if cache_key in _sprite_cache:
        return _sprite_cache[cache_key]

    path = SPRITE_FILES.get(asset_key)
    if path is None or not path.exists() or not hasattr(pygame, "image"):
        _sprite_cache[cache_key] = None
        return None

    try:
        sprite = pygame.image.load(str(path))
        if hasattr(sprite, "convert_alpha"):
            try:
                sprite = sprite.convert_alpha()
            except Exception:
                pass
        if size is not None and hasattr(pygame, "transform"):
            try:
                sprite = pygame.transform.scale(sprite, size)
            except Exception:
                pass
    except Exception:
        sprite = None

    _sprite_cache[cache_key] = sprite
    return sprite


def load_enemy_sprite(enemy: object) -> pygame.Surface | None:
    """Return the sprite selected for an enemy subclass, scaled to its hitbox."""
    asset_key = ENEMY_SPRITE_KEYS.get(enemy.__class__.__name__, "enemy_grunt")
    width = max(1, int(getattr(enemy, "width", 1)))
    height = max(1, int(getattr(enemy, "height", 1)))
    return load_sprite(asset_key, (width, height))


def play_sound(sound_key: str) -> bool:
    """Play a cached sound effect when mixer support is available."""
    if not _ensure_mixer_ready():
        return False

    sound = _get_sound(sound_key)
    if sound is None:
        return False

    try:
        sound.play()
    except Exception:
        return False
    return True


def start_background_music() -> bool:
    """Start looping background music once, falling back silently if audio is unavailable."""
    global _music_started
    if _music_started or not _ensure_mixer_ready():
        return False
    if not BACKGROUND_MUSIC_FILE.exists() or not hasattr(pygame.mixer, "music"):
        return False

    try:
        pygame.mixer.music.load(str(BACKGROUND_MUSIC_FILE))
        pygame.mixer.music.set_volume(BACKGROUND_MUSIC_VOLUME)
        pygame.mixer.music.play(-1)
    except Exception:
        return False

    _music_started = True
    return True


def _get_sound(sound_key: str) -> object | None:
    """Load one sound effect into the cache."""
    if sound_key in _sound_cache:
        return _sound_cache[sound_key]

    path = SOUND_FILES.get(sound_key)
    if path is None or not path.exists():
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


def _ensure_mixer_ready() -> bool:
    """Initialize pygame.mixer once when possible."""
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
