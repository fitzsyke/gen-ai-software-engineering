# 2028 Wooden Canvas Game — Design

## Summary
A single self-contained `index.html` file in `workshop-6/` implementing a keyboard-controlled 2048-style sliding-tile puzzle game, rendered entirely on `<canvas>` in a carved-wood retro visual style, with the win value set to **2028**.

## Location
`workshop-6/index.html` — no other files. No build step, no external assets or CDN dependencies. Wood textures and all visuals are drawn procedurally with canvas gradients (no image files).

## Game Rules
- 4×4 grid, represented as a `number[4][4]` array (`0` = empty cell).
- Arrow keys (`ArrowLeft/Right/Up/Down`) slide all tiles in that direction:
  - Tiles compress toward the edge in the given direction.
  - Adjacent equal-value tiles merge into one tile of double value (each tile merges at most once per move).
  - After any tile moved or merged, a new tile spawns in a random empty cell: value `2` (90% chance) or `4` (10% chance).
  - A move that changes nothing on the board does not spawn a new tile.
- Score: running sum of all merge results (adding the merged tile's new value each time two tiles combine).
- Best score: persisted in `localStorage` (key: `wooden2028-best`), updated whenever current score exceeds stored best.
- Win condition: reaching a tile of value **2028** shows a win overlay. The game does *not* lock — pressing any arrow key after dismissing continues play (win overlay only shown once per game).
- Game over condition: board is full (no empty cells) AND no two adjacent cells (horizontally or vertically) share the same value. Triggers the game-over overlay.
- Restart: pressing `R` at any time resets the grid, score (not best score), and overlay state.

## Rendering (Canvas)
All game visuals render on a single `<canvas>` element via the 2D context; only page chrome (title, best-score label outside the canvas is optional but score/best are drawn on canvas for consistency) lives in HTML/CSS.

- **Board background:** dark walnut base fill with layered radial/linear gradients to suggest wood grain bands; beveled inset border around the board; four small brass-toned corner rivets (radial-gradient circles).
- **Empty cells:** recessed darker wood-tone rounded squares (subtle inner shadow via double-draw offset technique, since canvas has no native inset shadow).
- **Tiles:** rounded-rect blocks, fill color mapped from tile value along a light-pine → dark-mahogany gradient scale (e.g. 2/4 = pale pine, ...  1024+ = near-black walnut). Each tile has a subtle bevel (lighter top-left edge, darker bottom-right edge) and an engraved-looking number (dark offset shadow behind lighter text, or vice versa) using a bold slab-serif font stack (`"Rockwell", "Georgia", serif` fallback).
- **Animations:** driven by `requestAnimationFrame`.
  - Slide: each moved tile interpolates from its previous grid position to its new one over ~120ms (ease-out).
  - Merge: the resulting tile briefly scales up (~1.15x) then back to 1.0x over ~120ms as a "pop" pulse.
  - Implementation approach: each move computes a list of tile animation descriptors (`{ id, fromRow, fromCol, toRow, toCol, value, merged }`) rather than mutating the logical grid mid-flight; the grid updates immediately for logic purposes, animation is purely visual interpolation layered on top.
- **Overlays:** drawn on top of the canvas (semi-transparent dark backdrop rect + a centered wooden-plaque rounded rect with border) for both Win and Game Over states, with a large heading ("2028!" / "Game Over") and instruction text ("Press R to continue" / "Press R to restart").

## Controls
- Arrow keys: move tiles (only interaction mechanism, per requirements — no mouse/touch/swipe).
- `R`: restart game (works anytime, including mid-game, win, and game-over states).

## State Persistence
- `localStorage["wooden2028-best"]`: integer best score, read on load, written whenever a new best is achieved.

## Out of Scope
- Mobile/touch/swipe controls.
- Undo functionality.
- Multiple grid sizes or difficulty settings.
- Sound effects.
- External fonts/images/CDN assets — everything is self-contained in the one HTML file.

## Testing / Verification
- Manually exercise in browser preview: moves in all four directions, merges, spawn behavior, win overlay at 2028, game-over detection, restart via `R`, best-score persistence across reload.
