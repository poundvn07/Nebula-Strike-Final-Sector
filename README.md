# Nebula Strike: Final Sector

Nebula Strike: Final Sector is a 2D shoot 'em up game built with Python and
Pygame for an Object-Oriented Programming course project.

The project focuses on clear OOP structure: abstract base classes, inheritance,
method overriding, composition, polymorphism, and JSON-based persistence.

## Features

- Wave-based combat across 5 maps.
- 1024x768 Pygame display.
- Player ship with 3 weapon slots and one active weapon at a time.
- Weapon shop and preparation phase between maps.
- Weapon upgrades, combo attacks, drones, repairs, and extra lives.
- Enemy tiers with distinct behavior, including bosses.
- JSON-driven weapon and enemy balance data.
- Save/load support through an ignored runtime save file.
- Unit tests for core gameplay, save, enemy, wave, and weapon behavior.

## Controls

- Move: `WASD` or arrow keys
- Fire active weapon: `Space`
- Cycle active weapon: `Tab`
- Select weapon slot directly: `1`, `2`, `3`
- Combo attack: hold two weapon slot keys, such as `1+2`
- Toggle drone mode: `Q`
- Pause or resume: `P` or `Esc`
- Show controls guide: `H`
- Mute sound effects: `M`
- Mute background music: `N`
- Use menu, preparation, retry, and shop buttons: mouse click

## Setup

Python 3.11+ is recommended. The local project currently uses Python 3.13.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

For running tests, install pytest if it is not already available:

```bash
pip install pytest
```

## Run

```bash
python main.py
```

## Test

```bash
venv/bin/python -m pytest tests -q
```

## Project Structure

```text
src/
  core/       game loop, scenes, and input routing
  entities/   player, bullets, drones, pickups, shared game objects
  weapons/    weapon hierarchy and combo effects
  enemies/    enemy hierarchy and boss classes
  systems/    wave, collision, resource, and save managers
  ui/         main menu, HUD, preparation, and result screens
  utils/      constants, assets, and helpers

assets/
  sprites/    game sprites and effects
  audio/      music and sound effects

data/
  weapon_stats.json
  enemy_stats.json
  wave_config.json
```

## Configuring Enemy Waves

Enemy composition, spawn timing, formations, movement sway, and bosses are
configured in `data/wave_config.json`. Each map contains an ordered `waves`
array. A wave can repeat an enemy pattern:

```json
{
  "formation": "grid",
  "enemy_count": 12,
  "enemy_pattern": ["chicken_grunt", "egg_bomber", "kamikaze"]
}
```

Alternatively, use `enemies` for an exact type order and `positions` for an
arbitrary formation. Include one `[x, y]` position for every enemy and boss:

```json
{
  "formation": "grid",
  "enemies": ["egg_bomber", "chicken_grunt"],
  "positions": [[300, 90], [700, 160]]
}
```

Named presets under `formations` control columns, origin, spacing, spawn
stagger, coordinated enemy types, sway, and screen bounds. Restart the game
after editing the file so the selected map reloads its wave configuration.
Regular formation sprites keep a six-pixel minimum gap while swaying; unsafe
custom positions and boss summons are separated before movement is applied.
Set `layout` to `grid`, `chevron`, `staggered`, `wave`, or `diamond` in any
formation preset. Optional `layout_options` tune shape-specific values such as
chevron `depth`, staggered `row_offset`, or wave `amplitude` and `cycles`.
Set `spawn_all_on_intro` to `false` when `spawn_delay` and `spawn_stagger`
should release enemies gradually after the countdown.

## Runtime Files

The following files are generated locally and intentionally ignored by git:

- `data/save_state.json`
- `__pycache__/`
- `.pytest_cache/`
- `.DS_Store`

`AI_GUIDE.md` contains the course/project rules used while developing this
codebase.
