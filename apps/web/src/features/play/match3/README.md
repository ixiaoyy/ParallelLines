# 平行消消乐（小鱼）

本模块从独立的 WebMatch3 项目迁入，现由论坛的 `/play/match3` 路由加载。
存档保存在论坛域名的 `parallellines.match3.ambient-state`，旧域名的浏览器存档不迁入。
论坛沿用自己的 PWA，不注册原项目的独立 Service Worker 或安装清单。

The public game is a persistent felt-fish finding game, not a grid-based
Match-3 session. Pure wave construction, same-species tray combination,
Fibonacci level goals, progression, and loss-restart rules live in `engine/`.
Versioned local persistence lives in `session/`. Vue, attention lifecycle,
optional Document Picture-in-Picture, sound, cat motion, and visual projection
live in `ui/`.

The engine owns one seed-reproducible, single-layer school. Fish use authored
points along an open S-shaped route, stay outside the cat-and-plant corner, and
never overlap as a gameplay mechanic. The UI projects that route across the
available left-hand scene without mutating canonical positions. Every fish is
visible and directly actionable; pointer, touch, Enter, Space, or `F` puts it in
the tray. A forgiving hit target surrounds the artwork, and the fish use small
independent drift cycles so the scene feels alive without moving the solution.

Three same-species fish combine automatically. The exact three slide to the
tray, gather into one visibly larger fish, and travel to the cat while its
eating pose begins. The outgoing school remains visible during that sequence;
a replacement wave arrives only when feeding makes contact. Each completed
fish grows the plant, increments lifetime `fishFedCount`, and advances one of
three cat bond stages. Every third fish adds a short full-to-sleeping rest
sequence; later fish remain accepted and can interrupt it.

Level one is a deliberately easy nine-fish introduction: three species are
shown three times each, and all three groups must be completed before the level
ends. From level two onward, each wave contains exactly one species with three
fish and every other visible species has two. Completing the unique triple
refreshes the whole school while retaining progress inside the current level.
The level goals are 3, 5, 8, 13, 21, 34, and so on. Later levels add species up
to the eight-kind visual set, but never add stacking or occlusion.

A full unmatched tray briefly remains visible as quiet failure feedback, then
only the current wave is rebuilt. The current level and its already-completed
group count are preserved. Activating the cat still offers transient pet and
search actions; search highlights a useful visible fish, prioritizing a species
that already has two matching fish in the tray.

Version-four persistence validates the current single-layer wave, level-local
progress, preferences, plant age, a guarded fish ID, and lifetime
`fishFedCount`. Legacy v3/v2/v1 states migrate through a strict boundary, and
legacy v4 pile snapshots remain readable long enough to preserve durable plant,
pet, and sound progress. A new page/controller generates a fresh level-one
school with an empty tray while retaining lifetime plant and cat progress. The
same mounted Vue surface moves into Document Picture-in-Picture and reflows
without creating a second controller or resetting the current wave.
