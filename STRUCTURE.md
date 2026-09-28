# AInimity Arcade Structure

The existing single-file frontend remains the host. The Games panel adds one scoped `initAinimityArcade` controller near the end of the page script.

- `#games`: navigation shell and arcade layout.
- `#gameNav`: per-game navigation buttons.
- `#gameCanvas`: shared 640x400 2D canvas.
- `makers`: factory map for four games.
- `requestAnimationFrame`: shared local render/update loop.
- `keydown`, `keyup`, and canvas click handlers: cleaned into the scoped controller and gated by the active Games panel.

The games are intentionally 2D canvas mini-games rather than a separate runtime, keeping the permanent council website small and avoiding API, account, or network dependencies for play.
