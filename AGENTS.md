Source the virtual environment at venv/ before running flask commands

Don't run the flask server, I already have one running

If you change of the below information, or add significantly to the page, update this file accordingly.

## Active work: game_player.html

Primary file: `flask_app/templates/game_player.html` (~4200 lines). Ignore the React rewrite — all work stays in this file.

### Video player
- Uses YouTube IFrame API. Key globals: `player` (YT.Player instance), `playerReady` (bool).
- Single polling interval (`controlsUpdateInterval`, 100ms) lives in `startVideoControlsUpdate()`. All per-tick work goes here: `updateVideoControls()`, `updateScoreboard()`, `syncPlaybackRateIndicator()`, `syncMuteIndicator()`, `syncPlayPauseIndicator()`.
- Video controls bar: `#videoControls` div below the video. Buttons use `.vc-btn`; speed buttons have `data-speed-group`. The `vc-always-icon` class shows icon+label on all sizes; `vc-icon-mobile` shows icon-only on mobile and text-only on desktop.
- Keyboard shortcuts: `k`=play/pause, `j`=−10s, `l`=+10s, `m`=mute, `f`=fullscreen, `<`/`>`=speed ±0.25×.
- Speed highlight: `syncPlaybackRateIndicator()` injects a dashed `.vc-speed-custom#vc-custom-rate` badge at the correct sort position when the active rate doesn't match 0.5/1/2×.

### Layout & responsive breakpoints
- Desktop: 2-column grid (`.main` + `.sidebar`, sidebar 320px). Narrows at 1300px (250px), collapses to single column at ≤1100px.
- Mobile (≤767px): `.main` becomes flex-column with explicit `order` values. Scoreboard and timestamp live in `.player-meta-bar` (shown as a flex bar above the video on mobile; `display:contents` on desktop so they remain absolute overlays). Point-info-section is ordered above the video.

### Comments
- Sidebar panel. Input box is always visible on desktop; on mobile it's hidden by default and revealed by a `+ Comment` button (`toggleCommentInput()`). Auto-hides after a successful post.
- `scrollCommentIntoView(el, opts)` — scrolls within `#commentsList` only. Pass `{ toTop: true }` to also nudge the page scroll on single-column layouts (shows 250px of the list from the bottom of the viewport).