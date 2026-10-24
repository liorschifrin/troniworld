# Film visibility policy (T03)

Status: implemented on the draft T03 branch; Q1 **option A** selected by the user on 2026-10-25. Private comments are for their author and explicit recipients, including on admin reports. Leadership status grants no extra access. See [T03 and proposed T03a](../FEATUREROADMAP_workplan.md#t03--one-visibility-policy-for-games-comments-and-notifications).

Shared code: `flask_app/visibility.py` (`can_view_game`, `get_visible_game_or_404`, `visible_games_query`, `private_recipients`, `can_view_comment`). Tests: `tests/test_visibility.py`.

## Rules

1. **Hidden games.** A game with `is_hidden=True` exists only for admins. Nonadmins get the same response as for a game id that does not exist: the default Flask 404, byte-for-byte. Hidden games are left out of every list, count, statistic, option list, comment list and notification that nonadmins can read. Admin behavior is unchanged.
2. **Private comments.** If `private_to` is SQL NULL, the comment is public to anyone who can view its game. Any other value makes it private: only the author and the usernames listed in `private_to` can read it. `[]`, non-list JSON and malformed values all mean author-only (fail closed). Admins follow the same rule; being an admin does not make you a recipient.
3. **Replies.** A reply inherits the private audience of its whole parent chain. A viewer can see a reply only if they can see every ancestor's game and audience and the reply's own `private_to` (if set) also includes them. A nonrecipient of a private parent therefore gets neither the parent body nor any reply body, including public replies. A private reply under a public parent is visible only to the reply's author and recipients. A reply whose parent row is missing is not visible.
4. **Notifications.** A notification row is created only for a user who can view the comment under rules 1–3. Reads return only the caller's own rows (`recipient_username`). Older rows whose comment or game the caller cannot view are left out of the response entirely (no snippet, title, author or id) and are not deleted.
5. **Admin reports and counts.** Comment lists and leadership-tag reports filter with the same policy for the viewing admin, including every ancestor. Dashboard per-user comment counts, total comments, and leadership-tag read/total counts use the exact same selections as their detail endpoints. They represent what that admin may read, not global activity totals. Leadership tags still exclude admin-only authors without the leadership flag.
6. **Fail closed.** This repair does not rewrite or delete stored comments. There is no schema change or migration.

### Comment edits and notification history

Edits reconcile notifications instead of wiping and recreating them. Existing rows for still-entitled recipients keep their ID, `created_at`, `is_read`, and `read_at`, including when a mention is removed but the comment remains visible. If a retained recipient is still targeted, the notification type follows the current priority. Newly targeted recipients receive unread rows; rows for recipients who lost access to the edited comment are deleted. Editing an ancestor does not rewrite descendant notification rows: reads filter those rows through the full current ancestor chain. This is a small T03 correction; broader notification pagination, count semantics, races, and history requirements remain T09 follow-ups.

### Leadership group proposal

T03a proposes a separately selectable leadership-group audience with membership captured at posting time. It is **not implemented** here. Existing leadership flags alone grant no access to a private comment.

## `/api/v1` decision

`/api/v1` has no consumer in the repository. Its only client was the React film-room bundle (`flask_app/static/js/film-room/**`, `film_room_app.html`). That bundle was deleted in commit `e6ba8e7` ("rm-old-files", 2026-03-10). No template, static asset or document calls `/api/v1` today; only tests and ProductSpec mention it.

Decision: **retire `/api/v1` after an owner confirmation that no external client uses it.** Until then, the blueprint stays registered but **fails closed**. It applies the same game and comment policy, with no leadership exception. Its responses keep their shape apart from the filtered entries. Do not add features to it. The blueprint has not been deleted.

## Policy matrix

Role meanings:

- **Anonymous**: no session.
- **Ordinary**: nonadmin, nonleadership member.
- **Nonrecipient**: any signed-in user who did not write the comment and is not in its `private_to`. Ordinary, admin and leadership users can all be nonrecipients.
- **Recipient**: listed in `private_to`.
- **Author**: wrote the comment.
- **Leadership author**: a leadership user who wrote the comment.
- **Leadership nonrecipient**: a leadership user who is neither author nor explicit recipient.

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
| Admin reports: `/film/analytics`, `/film/api/user/<u>/comments`, `/leadership-tags`, `/watched-games` | 302 login | 302 → `/` (admin-only) | all games; private bodies and comment/tag counts follow the viewing admin’s audience (rule 5) |

### B. Comment bodies and notification snippets (visible game)

"Body" means the comment text, its id, and any notification snippet.

| Surface | Nonrecipient (ordinary / admin) | Explicit recipient | Author | Leadership author | Leadership nonrecipient |
|---|---|---|---|---|---|
| `GET /film/api/games/<id>/comments`: public top-level | visible | visible | visible | visible | visible |
| same: private top-level | hidden | visible | visible | visible (own) | hidden |
| same: reply under private parent | hidden (parent and reply) | visible | visible | visible (own thread) | hidden (parent and reply) |
| same: private reply under public parent | hidden | visible | visible | visible (own) | hidden |
| `GET /api/v1/games/<id>` and `/comments`: all of the above | hidden (private, inherited) | visible | visible | visible (own) | hidden |
| `/api/v1` POST/PATCH response `replies` | only replies the caller may see | same | same | same | hidden |
| Notification **creation** (mention, reply, thread, private, everyone) | not created | created | never for own comment | never for own comment | not created, e.g. a `thread` row for a leadership-authored private thread |
| `GET /film/api/notifications` | stored rows the caller cannot view are left out | served with snippet | n/a (no own rows) | n/a | left out |
| `POST /film/api/notifications/<id>/read` | own rows only; another user's id → 404 | own rows only | own rows only | own rows only | own rows only |
| `POST /film/api/notifications/read-all` | marks only the caller's rows | same | same | same | same |
| `GET /film/my-games` (own comments) | n/a | n/a | own comments on visible games | own comments on visible games | n/a |
| Admin reports (`/film/api/user/<u>/comments`, `/leadership-tags`): private bodies | hidden for admin; nonadmin → 302 `/` | visible if admin | visible if admin | visible if admin | hidden for admin; nonadmin → 302 `/` |
| `/film/analytics`: comment totals and leadership-tag read/total counts | inaccessible rows excluded | entitled rows counted if admin | entitled rows counted if admin | entitled rows counted if admin | inaccessible rows excluded; nonadmin → 302 `/` |

All reply cells require **every** ancestor and the reply itself to admit the viewer, even when the viewer authored the reply. Reports use this rule at arbitrary depth; the main film comments UI still renders one level of replies.

## Known limits

- Admin counts intentionally vary by viewing admin and can be lower than global activity. Filtering loads candidate comments/notifications and walks their ancestors; load/performance qualification is outside T03.
- T03a leadership-group audiences are proposed only; no group UI, storage, or notifications were added.
- `GET /film/api/notifications` still reads only the 50 newest stored rows and then filters them. The caller can therefore get fewer than 50 items. `unread_count` counts only the rows that were returned.
- On a visible game, a nonauthor who edits or deletes an existing comment id gets 403; a missing comment id gets 404. That difference shows whether a comment id exists, but no content. This is unchanged.
- Parent validation is T04 scope: cross-game parents, and replies to a parent the caller cannot see. Such a reply inherits the parent's audience, so its author cannot read the thread through it.
- Legacy stored `private_to` forms fail closed: `''` formerly counted as public on film GET; a JSON string such as `"recipient"` formerly used substring membership; a JSON object such as `{"recipient": true}` formerly used key membership. All now mean author-only. Route tests assert that the author still sees each body and a matching username does not. POST/PATCH input normalization is unchanged (T04 validation scope); these tests seed stored legacy values directly.
- Article comments have no private or hidden concept and were not changed.
