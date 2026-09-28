# AInimity Optimization Checklist

## Completed

- Removed the Magic 5 game from the Games navigation, runtime factory, and page copy.
- Removed the inline base64 background video that made the initial HTML approximately 21 MB.
- Reduced background star and dust counts and capped canvas device-pixel density.
- Capped galaxy redraws at approximately 30 FPS.
- Throttled pointer trails and capped trail particle count.
- Paused ambient and arcade animation loops while the document is hidden.
- Paused the arcade game loop whenever the Games panel is not active.
- Added reduced-motion behavior for ambient effects.
- Verified the remaining Pacman, Snake Bite, Tetris, and Bouncy Tales games in the browser.

## Remaining optional improvements

- Add a user-facing performance toggle for low-power devices.
- Add touch controls for mobile arcade play.
- Replace the current 500 ms clock refresh with a lower-frequency update if profiling shows it matters.
