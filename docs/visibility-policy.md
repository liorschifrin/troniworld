# Film visibility policy (T03 slice 1)

Status: implemented for slice 1 on 2026-10-24. Leadership policy **Q1 is still open** ([roadmap §6](../FEATUREROADMAP_workplan.md)). This slice does not add or remove any leadership exception. Every cell that depends on Q1 is marked **pending Q1**.

Shared code: `flask_app/visibility.py` (`can_view_game`, `get_visible_game_or_404`, `visible_games_query`, `private_recipients`, `can_view_comment`). Tests: `tests/test_visibility.py`.

## Rules

1. **Hidden games.** A game with `is_hidden=True` exists only for admins. Nonadmins get the same response as for a game id that does not exist: the default Flask 404, byte-for-byte. Hidden games are left out of every list, count, statistic, option list, comment list and notification that nonadmins can read. Admin behavior is unchanged.
2. **Private comments (baseline).** If `private_to` is SQL NULL, the comment is public to anyone who can view its game. Any other value makes it private: only the author and the usernames listed in `private_to` can read it. `[]`, non-list JSON and malformed values all mean author-only (fail closed). Admins follow the same rule; being an admin does not make you a recipient.
3. **Replies.** A reply inherits the private audience of its whole parent chain. A viewer can see a reply only if they can see every ancestor and the reply's own `private_to` (if set) also includes them. A nonrecipient of a private parent therefore gets neither the parent body nor any reply body, including public replies. A private reply under a public parent is visible only to the reply's author and recipients. A reply whose parent row is missing is not visible.
4. **Notifications.** A notification row is created only for a user who can view the comment under rules 1–3. Reads return only the caller's own rows (`recipient_username`). Older rows whose comment or game the caller cannot view are left out of the response entirely (no snippet, title, author or id) and are not deleted.
5. **Fail closed.** No stored content is deleted or rewritten. There is no schema change or migration.

### Pre-existing leadership exception (pending Q1)

Before T03, the main film comments API (`GET /film/api/games/<id>/comments`) also let a **leadership viewer** read a **leadership-authored** private comment that has at least one explicit recipient. This applies to that comment's replies too, as long as their own `private_to` also allows the viewer. Removing it would decide Q1, so it is **kept exactly as it was, on that one route only**. It is applied through `can_view_comment(..., leadership_exception=True)`. Every other surface uses the explicit baseline (rule 2) with no leadership exception: `/api/v1`, notification creation and reads, and `my-games`. That is the fail-closed choice until Q1 is decided.

## `/api/v1` decision

`/api/v1` has no consumer in the repository. Its only client was the React film-room bundle (`flask_app/static/js/film-room/**`, `film_room_app.html`). That bundle was deleted in commit `e6ba8e7` ("rm-old-files", 2026-03-10). No template, static asset or document calls `/api/v1` today; only tests and ProductSpec mention it.

Decision: **retire `/api/v1` after Q1 and an owner confirmation that no external client uses it.** Until then, the blueprint stays registered but **fails closed**. It applies the same game and comment policy, with no leadership exception. Its responses keep their shape apart from the filtered entries. Do not add features to it. The blueprint has not been deleted.

## Policy matrix

Role meanings:

- **Anonymous**: no session.
- **Ordinary**: nonadmin, nonleadership member.
- **Nonrecipient**: any signed-in user who did not write the comment and is not in its `private_to`. Ordinary, admin and leadership users can all be nonrecipients.
- **Recipient**: listed in `private_to`.
- **Author**: wrote the comment.
- **Leadership author**: a leadership user who wrote the comment.
- **Leadership nonrecipient**: the Q1 role.

Anonymous users are redirected (`302 → /login`) on every surface below.

### A. Game-level surfaces

| Surface | Anonymous | Nonadmin (ordinary, leadership, author, recipient) | Admin |
|---|---|---|---|
| `GET /film/games` (list) | 302 login | hidden games not listed | all games, hidden marked |
| `GET /film/games/<id>` (`view_game`) | 302 login | hidden → 404 = missing | 200 |
| `view_game` / `/api/v1/games/<id>` point option lists | 302 login | labels from visible games only | all games |
| `GET /film/my-games` (games and own comments) | 302 login | hidden games and own comments on them left out | unchanged (includes hidden) |
| `GET /film/data` (list, `game_ids`, leaderboard `games_played`, tendencies) | 302 login | hidden ids treated as missing; counts and statistics from visible games only | unchanged |
| `GET/POST /film/api/games/<id>/comments`, `PATCH/DELETE .../<comment_id>` | 302 login | hidden → 404 = missing, no write | unchanged |
| `POST .../track-watch-time`, `GET .../watch-progress`, `POST .../toggle-watched` | 302 login | hidden → 404 = missing, no write. A missing game used to return 500 on toggle; now 404 | unchanged |
| `GET /api/v1/games` | 302 login | hidden games not listed | all games |
| `GET /api/v1/games/<id>`, `GET/POST .../comments`, `PATCH/DELETE .../comments/<cid>`, `POST .../track-watch-time` | 302 login | hidden → 404 = missing, no write | unchanged |
| `GET /film/api/notifications` | 302 login | rows for hidden-game comments left out; none created | unchanged |
| Admin reports: `/film/analytics`, `/film/api/user/<u>/comments`, `/leadership-tags`, `/watched-games` | 302 login | 302 → `/` (admin-only) | unchanged; private-content rules **pending Q1 (current behavior retained, not modified)** |

### B. Comment bodies and notification snippets (visible game)

"Body" means the comment text, its id, and any notification snippet.

| Surface | Nonrecipient (ordinary / admin) | Explicit recipient | Author | Leadership author | Leadership nonrecipient |
|---|---|---|---|---|---|
| `GET /film/api/games/<id>/comments`: public top-level | visible | visible | visible | visible | visible |
| same: private top-level | hidden | visible | visible | visible (own) | **pending Q1 (current behavior retained)**: visible only if the author is leadership and has ≥1 recipient; otherwise hidden |
| same: reply under private parent | hidden (parent and reply) | visible | visible | visible (own thread) | **pending Q1 (current behavior retained)**: follows the parent, as in the cell above |
| same: private reply under public parent | hidden | visible | visible | visible (own) | **pending Q1 (current behavior retained)**: same leadership exception |
| `GET /api/v1/games/<id>` and `/comments`: all of the above | hidden (private, inherited) | visible | visible | visible (own) | **pending Q1 (current baseline applied)**: hidden |
| `/api/v1` POST/PATCH response `replies` | only replies the caller may see | same | same | same | **pending Q1 (current baseline applied)**: hidden |
| Notification **creation** (mention, reply, thread, private, everyone) | not created | created | never for own comment | never for own comment | **pending Q1 (current baseline applied)**: not created, e.g. a `thread` row for a leadership-authored private thread |
| `GET /film/api/notifications` | stored rows the caller cannot view are left out | served with snippet | n/a (no own rows) | n/a | **pending Q1 (current baseline applied)**: left out |
| `POST /film/api/notifications/<id>/read` | own rows only; another user's id → 404 | own rows only | own rows only | own rows only | own rows only |
| `POST /film/api/notifications/read-all` | marks only the caller's rows | same | same | same | same |
| `GET /film/my-games` (own comments) | n/a | n/a | own comments on visible games | own comments on visible games | n/a |
| Admin reports (`/film/api/user/<u>/comments`, `/leadership-tags`) | admin-only | admin-only | admin-only | admin-only | **pending Q1 (current behavior retained, not modified)** |

## Known limits of slice 1

- Admin report private-content rules are unchanged and still pending Q1. `user_comment_list` shows private comments by leadership or admin authors to any admin. `leadership-tags` returns notification bodies without per-viewer checks.
- `GET /film/api/notifications` still reads only the 50 newest stored rows and then filters them. The caller can therefore get fewer than 50 items. `unread_count` counts only the rows that were returned.
- On a visible game, a nonauthor who edits or deletes an existing comment id gets 403; a missing comment id gets 404. That difference shows whether a comment id exists, but no content. This is unchanged.
- Parent validation is T04 scope: cross-game parents, and replies to a parent the caller cannot see. Such a reply inherits the parent's audience, so its author cannot read the thread through it.
- Stored `private_to = ''` is now treated as author-only on the main film API; before, it counted as public. The application never writes that value.
- Article comments have no private or hidden concept and were not changed.
