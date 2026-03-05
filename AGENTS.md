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
- Comment type UI removed — `comment_type` is hardcoded to `'Comment'` everywhere.
- Author styling: own name → `.comment-author-self` (purple `#C45AB3`); leadership → `.comment-author-leadership` (blue `#4A9EDB`, ★ prefix). Both get a border-bottom.

### Private comments
- `Comment.private_to` DB column (Text, nullable) stores a JSON list of allowed usernames (e.g. `["alice","bob"]`). `null` = public.
- Server-side filtering in `get_comments()` (`film_routes.py`): a comment is returned only if `private_to` is NULL, or the viewer is the author, or the viewer's username is in the list. Same filter applied to replies.
- `create_comment` / `update_comment` accept `private_to` (list or null) in the request body.
- Frontend globals: `isPrivateComment` (bool), `privateToUsers` (array), `editIsPrivate`, `editPrivateToUsers`.
- UI: 🔒 lock button (`.privacy-toggle-btn`) in `.comment-controls`. When active (yellow border), a chip-input section (`.private-to-wrap`) appears. Users type a username and press Enter/comma to add a chip; click × to remove.
- Helper JS: `togglePrivacy()`, `renderPrivateChips()`, `addPrivateUser()`, `removePrivateUser()` (and `Edit` variants for the edit form).
- Rendered private comments/replies show a 🔒 badge next to the author name. If you're the author, a "visible to: you, alice, bob" line appears below the comment text (`.comment-private-recipients`).
- Edit form includes the same lock toggle + chips, pre-populated from existing `private_to` data.