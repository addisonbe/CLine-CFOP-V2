# Plan: a 3D view for the desktop interface

Status: **plan**. Nothing in this document is implemented yet. It builds on the
2D interface in `src/rubiks_cfop/gui/` (milestones M0 to M3 of the manual's GUI
appendix) and keeps all of its rules: the engine stays dependency-free and headless,
the view-model never imports a toolkit, and anything that can be tested without a
screen is.

## 1. Goals and non-goals

**Goals**

1. Show the cube in 3D next to the net (a *Net | 3D* switch in the same window),
   always drawn from the same `Cube` state the net shows.
2. Animate the solution: every move of the player turns the right layer smoothly,
   including wide moves, slice moves and whole-cube rotations (`x y z`).
3. Let the user orbit the cube (drag), zoom (wheel) and reset the view.
4. Later: turn layers by dragging on stickers, and paint stickers to enter a cube
   state by hand (a friendlier alternative to typing 54 facelet letters).

**Non-goals**

* Photorealism: no textures, shadows or beveled pieces in the first version.
* A physics or "real cube" simulation (no corner cutting, no lockups).
* Other puzzle sizes. The design does not block them but does not plan for them.

## 2. What the engine already gives us

The move tables in `cube/moves.py` are generated from 3D geometry, not copied from a
table, so the hardest part of a 3D renderer already exists and is tested:

| Existing piece | Where | Use in 3D |
|---|---|---|
| `_STICKERS`: per facelet, the cubie position `(x, y, z)` in `{-1, 0, 1}` and the outward normal | `cube/moves.py` | where to draw each of the 54 stickers |
| `_BaseMove`: axis, layers and signed angle of every quarter turn | `cube/moves.py` | which stickers an animated move rotates, about which axis, in which direction |
| `Move.carried_to` | `cube/moves.py` | ground truth to test the animation against |
| `Timeline` and `ViewModel` | `gui/viewmodel.py` | the step before and after each animated move |
| `DEFAULT_PALETTE` | `render/net.py` | identical colors in the net and in 3D |

### Small engine additions (backwards compatible, no new dependency)

1. `sticker_geometry() -> tuple[tuple[Vector, Vector], ...]`: a public, documented
   view of `_STICKERS`, indexed by facelet.
2. `move_geometry(move) -> MoveGeometry(axis, layers, degrees)`: the rotation a move
   performs, with `degrees` in `{-270, -180, -90, 90, 180, 270}` for the move's
   turns. Today this lives on the private `_BaseMove`.
3. A property test that ties them together (see section 7): rotating every sticker
   of `move_geometry(m).layers` by the full angle sends sticker `i` to sticker
   `m.carried_to[i]`, for all 54 moves.

## 3. Choosing the rendering technology

| Option | Dependency | Strengths | Costs |
|---|---|---|---|
| **A. Software 3D on a Tk `Canvas`** | none | keeps the zero-dependency promise; same window, same threading model; 54 stickers plus the black plastic is under 200 polygons, well within what the canvas can redraw at 30 to 60 fps | hand-written projection and depth sorting; no GPU lighting; painter's algorithm needs care while a layer turns |
| B. OpenGL in Tk (`PyOpenGL` + `pyopengltk`) | two optional wheels | real depth buffer, smooth shading, high frame rates | native GL drivers vary on Windows; harder to test headlessly |
| C. A game/3D framework (`pyglet`, `moderngl`, Panda3D) | one large optional wheel | polished rendering and input | a second event loop or window; does not sit inside the Tk app |
| D. Web view (three.js in a browser or `pywebview`) | a browser, or one optional wheel | best-looking result; reuses `Solution.to_dict()` as is; also becomes the web front-end | a second language and process; offline packaging is harder |

**Recommendation.** Build option **A** first, behind a small renderer interface, so
that the 3D view ships with `pip install rubiks-cfop` and no extras. Keep option
**D** as the later "polished" path: the JSON payload is already the contract, and a
three.js viewer can consume the same timeline. Option B is only worth it if A turns
out too slow, which the numbers above make unlikely.

## 4. Architecture

```
+---------------------------------------------------------------+
| app shell (existing CubeApp): Net | 3D switch, player, table  |
+---------------------------------------------------------------+
| views     NetCanvas (existing)        CubeView3D (new, Tk)    |
+---------------------------------------------------------------+
| scene     Scene: stickers + plastic as 3D quads, from a Cube  |
| (pure)    Camera: yaw, pitch, distance, field of view         |
|           Animator: (move, progress 0..1) -> partial rotation |
|           project(): 3D quads -> sorted, culled 2D polygons   |
|           pick(): screen point -> facelet index               |
+---------------------------------------------------------------+
| view-model (existing ViewModel + an animation cursor)         |
+---------------------------------------------------------------+
| engine    rubiks_cfop + sticker_geometry() / move_geometry()  |
+---------------------------------------------------------------+
```

* **`gui/scene3d.py` (pure, no toolkit).** Builds the 54 sticker quads from
  `sticker_geometry()` and the cube's colors, plus the black body of each visible
  cubie face. Each sticker is a square inset slightly inside its cubie face so the
  black gaps read as plastic. Uses small `Vec3`/`Mat3` helpers written with the
  standard library (`math` only), no NumPy.
* **Camera.** Yaw and pitch (pitch clamped to about +/-85 degrees to avoid flipping),
  distance and a perspective projection. The default view is the classic
  three-quarter view showing U, F and R. An arcball (quaternion) camera can replace
  yaw/pitch later without touching anything else.
* **`project()`.** Rotate, cull back faces (normal facing away from the camera),
  project to 2D, and sort far to near (painter's algorithm). Returns
  `Polygon(points, fill, facelet)` records, so it can be asserted in tests.
* **Shading.** Simple Lambert shading: scale each color by
  `ambient + diffuse * max(0, normal . light)`, so the three visible faces read as
  different planes even when they share a color.
* **`Painter3D` protocol.** `fill_polygon(points, fill, outline)`, mirroring the
  existing `Painter`. The Tk implementation keeps one canvas item per polygon and
  updates it with `canvas.coords()` and `itemconfigure()` each frame instead of
  deleting and recreating items, which is the main performance lever on a canvas.

## 5. Animation

1. The player already moves between `Timeline` steps. In 3D mode, stepping from
   step *i* to *i+1* starts an animation of `steps[i+1].move` instead of jumping.
2. `Animator` turns `(move, progress)` into a rotation angle
   `move_geometry(move).degrees * ease(progress)` (ease-in-out cubic), applied only
   to the stickers whose cubie lies in the move's layers. Rotations `x y z` move all
   layers, wide moves two, slices the middle one, so no special cases are needed.
3. When `progress` reaches 1, the scene is rebuilt from `steps[i+1].cube`, so any
   floating-point drift is thrown away after every move. The animation is purely
   cosmetic: the source of truth is always a `Cube`.
4. Frame timing uses `root.after()` at about 16 ms, with the duration taken from
   the existing speed slider (half turns take 1.5 times as long as quarter turns).
   Stepping backwards plays the inverse move. Seeking or selecting a stage skips the
   animation and jumps.
5. **Depth sorting while a layer turns.** Sorting individual stickers fails when a
   turning layer intersects the rest. Split the scene into two groups, the turning
   layer and the static cube, sort the groups by the distance of their centers
   along the move axis, draw the far group first, and sort within each group. The
   inner faces exposed by a turning layer are drawn as black quads at the cut.

## 6. Interaction

| Input | Action |
|---|---|
| Left drag on the background | orbit the camera |
| Mouse wheel | zoom (clamped) |
| Double-click | reset the camera |
| Arrow keys, Space, Home, End | the existing player shortcuts |
| Left drag on a sticker (later) | turn a layer: pick the facelet, compare the drag vector with the projected directions of the two axes in that face's plane, and apply the nearest move |
| Paint mode (later) | click a sticker to cycle its color; *Solve* validates the result with the existing `parse_input(..., "facelets")` |

Picking is a point-in-polygon test over the projected polygons, nearest first,
which is cheap and testable without a screen.

## 7. Testing without a display

| Layer | Test |
|---|---|
| geometry | property test: for every one of the 54 moves, rotating the stickers in `move_geometry(m).layers` by the full angle maps facelet `i` onto `m.carried_to[i]` |
| scene | a solved cube produces 54 stickers whose colors match `DEFAULT_PALETTE` by face; after `R`, the scene equals the scene of `Cube.solved().apply("R")` |
| animation | `progress = 0` equals the step before, `progress = 1` equals the step after, for every move kind (face, wide, slice, rotation) |
| projection | back faces are culled (the default camera shows exactly three faces, 27 stickers); polygons come out far to near |
| picking | clicking the projected center of every visible sticker returns that facelet |
| view | a recording `Painter3D`, then a Tk smoke test that toggles to 3D, plays three moves and checks the canvas item count, skipped without a display |

The coverage floor of 90 percent stays in force; the pure modules should sit near
100 percent.

## 8. Milestones

Each milestone ends with the usual gate (`ruff format --check`, `ruff check`, the
whole suite and coverage) and leaves the program usable.

| Step | Scope | Acceptance |
|---|---|---|
| 3D-0 | `sticker_geometry()` and `move_geometry()` in the engine, with the property test | all 54 moves pass the geometry test; no change to existing behavior |
| 3D-1 | `scene3d.py`, camera, projection, culling, shading; static 3D view behind a *Net / 3D* switch; orbit and zoom | the 3D view always matches the net for the selected step; 30 fps while orbiting on a typical laptop |
| 3D-2 | Animated playback through the existing player, forward and backward, speed slider | every stage of 20 random solves plays to a solved cube; no depth-sorting glitches on wide, slice and rotation moves |
| 3D-3 | Interaction: drag on a sticker to turn a layer; undo; paint mode for entering a state | picking tests pass; a painted state solves through the normal pipeline |
| 3D-4 | Polish: rounded stickers, adjustable lighting, high-contrast palette, remember camera and speed between sessions | manual screenshots; settings round-trip |
| 3D-5 (optional) | three.js viewer fed by `Solution.to_dict()` plus the move geometry, as the web front-end | the same scramble animates identically in both views |

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Tk canvas too slow at large window sizes | reuse canvas items and update coordinates; cap the frame rate; drop shading during drags; option B as the fallback |
| Painter's-algorithm artefacts while turning | the two-group split in section 5; tests at mid-animation for each move kind |
| Floating-point drift over long playback | rebuild the scene from the engine's `Cube` after every move |
| Gimbal flips at the poles | clamp pitch; switch to an arcball camera if users want free rotation |
| Drag-to-turn feels wrong | ship it after playback (3D-3), behind a setting, with tests on the drag-to-move mapping |
| High-DPI blur on Windows | already handled: the app declares DPI awareness at start-up |

## 10. Order of work

Start with 3D-0: it is small, touches only the engine, and its property test proves
that the geometry the renderer will draw is exactly the geometry the solver uses.
3D-1 and 3D-2 then deliver the visible value (a turning cube that follows the
solution). Interaction and polish come after, and the web viewer only once the
desktop view has settled the scene and animation model.
