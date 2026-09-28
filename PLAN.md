# AInimity Arcade Plan

## Scope
Add a Games section inside the existing AInimity experience with local, lightweight browser games and clear per-game navigation.

## Risk slices
- Panel navigation must preserve Home, Council, and Memory behavior.
- Canvas games must remain local and must not call the debate API.
- Keyboard listeners must only affect games while the Games panel is active.
- Each game must reset cleanly when selected or restarted.
- The large legacy frontend must pass JavaScript syntax validation.

## Verification criteria
- Games tab and command-palette route open the Games panel.
- Four game buttons select Pacman, Snake Bite, Tetris, and Bouncy Tales.
- Canvas renders a playable scene for each selected game.
- Hosted preview returns HTTP 200 and browser smoke test reports all four titles.
