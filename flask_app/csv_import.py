"""Game CSV import (T10): parse, validate, diff, then apply atomically.

Pure parts (``parse_game_csv``, ``build_plan``, ``state_token``) touch no database, so an
invalid file can never write. ``load_state`` reads the game as it is now, ``apply_plan``
writes the whole change set in the caller's transaction. Points that a new CSV no longer
contains are hidden (``Point.hidden_by_import``), never deleted.

Format (unchanged): row 1 is the O/D row (``O`` Tron on offense, ``X`` on defense) from
column B; row 2 holds a value where Tron scored; row 3 where the opponent scored; one
optional blank row; then one row per player (name in column A, any non-blank cell means
the player was on that point). ``N/`` marks a player subbed off in an injury timeout and
``/N`` one subbed on. The first blank row after the first player starts a new section;
``END PLAYERS`` in column A stops reading. The point number is the column number.
"""
import csv
import hashlib
import io
import json
from dataclasses import dataclass, field

MAX_CSV_BYTES = 1_000_000
MAX_ROWS = 1000
MAX_COLUMNS = 500
MAX_PLAYER_NAME = 100
MAX_REPORTED_ERRORS = 100


@dataclass(frozen=True)
class CsvError:
    row: int | None
    column: str | None
    message: str

    @property
    def location(self):
        if self.row and self.column:
            return f'Row {self.row}, column {self.column}'
        if self.row:
            return f'Row {self.row}'
        if self.column:
            return f'Column {self.column}'
        return 'File'


@dataclass(frozen=True)
class ParsedPoint:
    index: int
    tron_o: bool
    tron_point: bool
    players: tuple          # names in sheet order
    sub_off: tuple = ()
    sub_on: tuple = ()

    @property
    def injury_subs(self):
        return {'off': list(self.sub_off), 'on': list(self.sub_on)} if self.sub_off or self.sub_on else None


@dataclass(frozen=True)
class ParsedSheet:
    points: tuple
    player_order: tuple
    separator_index: int | None

    @property
    def player_order_data(self):
        return {'players': list(self.player_order), 'separator_index': self.separator_index}


def column_letter(index):
    """0-based column index to a spreadsheet label (0 -> A, 26 -> AA)."""
    label = ''
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        label = chr(65 + rem) + label
    return label


def _classify_cell(value):
    """Return (kind, error) for a non-blank player cell: kind is None, 'off' or 'on'."""
    if '/' not in value:
        return None, None
    core = value
    kind = None
    if value.endswith('/') and not value.startswith('/'):
        kind, core = 'off', value[:-1]
    elif value.startswith('/') and not value.endswith('/'):
        kind, core = 'on', value[1:]
    if kind is None or not core.strip() or '/' in core:
        return None, (f'Invalid injury notation "{value}": use "N/" for subbed off '
                      f'or "/N" for subbed on')
    return kind, None


def parse_game_csv(raw):
    """Parse CSV bytes or text into ``(ParsedSheet | None, [CsvError])``.

    A sheet is returned only when there are no errors.
    """
    errors = []

    def err(row, column, message):
        errors.append(CsvError(row, column, message))

    if isinstance(raw, bytes):
        if len(raw) > MAX_CSV_BYTES:
            return None, [CsvError(None, None, f'CSV is larger than {MAX_CSV_BYTES // 1000} KB.')]
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            return None, [CsvError(None, None, 'CSV must be UTF-8 text.')]
    else:
        text = raw
        if len(text.encode('utf-8')) > MAX_CSV_BYTES:
            return None, [CsvError(None, None, f'CSV is larger than {MAX_CSV_BYTES // 1000} KB.')]
    try:
        rows = list(csv.reader(io.StringIO(text, newline=None)))
    except csv.Error as exc:
        return None, [CsvError(None, None, f'Could not read the CSV: {exc}')]
    if len(rows) < 4:
        return None, [CsvError(None, None, 'CSV needs at least 4 rows: the O/D row, the TRON row, '
                                           'the opponent row and player rows.')]
    if len(rows) > MAX_ROWS:
        return None, [CsvError(None, None, f'CSV has more than {MAX_ROWS} rows.')]
    width = max(len(row) for row in rows)
    if width > MAX_COLUMNS:
        return None, [CsvError(None, None, f'CSV has more than {MAX_COLUMNS} columns.')]

    def cell(row, col):
        return row[col].strip() if col < len(row) else ''

    od_row, tron_row, enemy_row = rows[0], rows[1], rows[2]

    # Player rows, section break and END PLAYERS marker.
    start = 3
    if all(not c.strip() for c in rows[3]):
        start = 4
    player_rows = []   # (csv row number, name, cells)
    names = []
    first_row_of = {}
    separator_index = None
    for offset, row in enumerate(rows[start:]):
        number = start + offset + 1
        if row and row[0].strip().upper() == 'END PLAYERS':
            break
        if all(not c.strip() for c in row):
            if names and separator_index is None:
                separator_index = len(names)
            continue
        name = cell(row, 0)
        if not name:
            err(number, 'A', 'Player row has cells but no player name in column A.')
            continue
        if len(name) > MAX_PLAYER_NAME:
            err(number, 'A', f'Player name is longer than {MAX_PLAYER_NAME} characters.')
            continue
        if name in first_row_of:
            err(number, 'A', f'Player "{name}" is already listed on row {first_row_of[name]}.')
            continue
        first_row_of[name] = number
        names.append(name)
        player_rows.append((number, name, row))

    # Point columns: the point number equals the column number (B is 1).
    columns = []
    for col in range(1, width):
        od = cell(od_row, col).upper()
        tron = cell(tron_row, col)
        enemy = cell(enemy_row, col)
        marks = [(n, name, cell(r, col)) for n, name, r in player_rows if cell(r, col)]
        columns.append((col, od, tron, enemy, marks))
    while columns and not (columns[-1][1] or columns[-1][2] or columns[-1][3] or columns[-1][4]):
        columns.pop()  # trailing empty columns are harmless spreadsheet padding

    points = []
    for col, od, tron, enemy, marks in columns:
        letter = column_letter(col)
        if not (od or tron or enemy or marks):
            err(1, letter, f'Column {letter} (point {col}) is empty between other points; '
                           f'delete the column or fill it in.')
            continue
        ok = True
        if od not in ('O', 'X'):
            ok = False
            err(1, letter, 'Missing O/D value (use O or X).' if not od
                else f'Invalid O/D value "{od}" (use O or X).')
        if tron and enemy:
            ok = False
            err(2, letter, f'Both rows 2 and 3 have a score in column {letter}; only one team scores a point.')
        elif not tron and not enemy:
            ok = False
            err(2, letter, f'Neither row 2 (Tron) nor row 3 (opponent) has a score in column {letter}.')
        players, sub_off, sub_on = [], [], []
        for number, name, value in marks:
            kind, problem = _classify_cell(value)
            if problem:
                ok = False
                err(number, letter, problem)
                continue
            players.append(name)
            if kind == 'off':
                sub_off.append(name)
            elif kind == 'on':
                sub_on.append(name)
        if ok:
            points.append(ParsedPoint(col, od == 'O', bool(tron), tuple(players), tuple(sub_off), tuple(sub_on)))

    if not errors and not points:
        err(None, None, 'CSV has no points. Importing it would hide every existing point.')
    if errors:
        return None, errors
    return ParsedSheet(tuple(points), tuple(names), separator_index), []


# ---------------------------------------------------------------------------
# Current state, change set, version token
# ---------------------------------------------------------------------------

def _subs_key(subs):
    subs = subs or {}
    return (tuple(sorted(subs.get('off') or [])), tuple(sorted(subs.get('on') or [])))


@dataclass(frozen=True)
class CurrentPoint:
    id: int
    index: int
    tron_o: bool | None
    tron_point: bool | None
    hidden: bool
    players: tuple            # sorted names
    injury_subs: object
    timestamp_start: int | None
    not_filmed: bool
    pull_play: str | None
    defense_type: str | None
    offense_faced: str | None
    comment_count: int = 0


@dataclass(frozen=True)
class CurrentState:
    points: dict              # point_index -> CurrentPoint
    roster: tuple             # sorted names
    player_order_data: object
    known_players: frozenset  # names of Player rows that exist


@dataclass
class PointDiff:
    index: int
    point: CurrentPoint | None = None
    changes: list = field(default_factory=list)   # (label, before, after)


@dataclass
class ImportPlan:
    added: list
    restored: list
    changed: list
    unchanged: int
    hidden: list              # CurrentPoint no longer in the CSV
    already_hidden: int
    new_players: list
    roster_added: list
    roster_removed: list
    order_before: list
    order_after: list
    separator_before: object
    separator_after: object

    @property
    def order_changed(self):
        return (self.order_before != self.order_after or self.separator_before != self.separator_after)

    @property
    def has_changes(self):
        return bool(self.added or self.restored or self.changed or self.hidden or self.new_players
                    or self.roster_added or self.roster_removed or self.order_changed)


def _side(tron_o):
    return 'Offense' if tron_o else 'Defense'


def _result(tron_point):
    return 'Tron scored' if tron_point else 'Opponent scored'


def _subs_text(subs):
    off, on = _subs_key(subs)
    if not off and not on:
        return 'none'
    return '; '.join(part for part in (f'off: {", ".join(off)}' if off else '',
                                       f'on: {", ".join(on)}' if on else '') if part)


def _point_changes(current, new):
    changes = []
    if current.tron_o != new.tron_o:
        changes.append(('Offense/defense', _side(current.tron_o), _side(new.tron_o)))
    if current.tron_point != new.tron_point:
        changes.append(('Result', _result(current.tron_point), _result(new.tron_point)))
    before, after = set(current.players), set(new.players)
    if before != after:
        gone, came = sorted(before - after), sorted(after - before)
        changes.append(('Players', ', '.join(f'-{n}' for n in gone) or 'no removals',
                        ', '.join(f'+{n}' for n in came) or 'no additions'))
    if _subs_key(current.injury_subs) != _subs_key(new.injury_subs):
        changes.append(('Injury subs', _subs_text(current.injury_subs), _subs_text(new.injury_subs)))
    return changes


def build_plan(sheet, state):
    """Compare a parsed sheet with the game as it is; nothing is written."""
    added, restored, changed, unchanged = [], [], [], 0
    seen = set()
    for new in sheet.points:
        seen.add(new.index)
        current = state.points.get(new.index)
        if current is None:
            added.append(PointDiff(new.index, None, [
                ('Offense/defense', '', _side(new.tron_o)), ('Result', '', _result(new.tron_point)),
                ('Players', '', ', '.join(new.players) or 'none'),
                ('Injury subs', '', _subs_text(new.injury_subs))]))
            continue
        changes = _point_changes(current, new)
        if current.hidden:
            restored.append(PointDiff(new.index, current, changes))
        elif changes:
            changed.append(PointDiff(new.index, current, changes))
        else:
            unchanged += 1
    hidden = [p for i, p in sorted(state.points.items()) if i not in seen and not p.hidden]
    already_hidden = sum(1 for i, p in state.points.items() if i not in seen and p.hidden)

    roster_after = sorted({name for p in sheet.points for name in p.players})
    before_roster, after_roster = set(state.roster), set(roster_after)
    needed = {name for p in sheet.points for name in p.players}
    new_players = sorted(n for n in needed if n not in state.known_players)
    order = state.player_order_data if isinstance(state.player_order_data, dict) else {}
    before_order = [n for n in (order.get('players') or []) if isinstance(n, str)]
    return ImportPlan(
        added=added, restored=restored, changed=changed, unchanged=unchanged,
        hidden=hidden, already_hidden=already_hidden, new_players=new_players,
        roster_added=sorted(after_roster - before_roster), roster_removed=sorted(before_roster - after_roster),
        order_before=before_order, order_after=list(sheet.player_order),
        separator_before=order.get('separator_index'), separator_after=sheet.separator_index,
    )


def state_token(state, csv_names=()):
    """Hash of everything an import reads or overwrites, for stale-preview detection."""
    payload = {
        'points': [[p.index, p.id, p.tron_o, p.tron_point, p.hidden, list(p.players),
                    list(_subs_key(p.injury_subs)[0]), list(_subs_key(p.injury_subs)[1]),
                    p.timestamp_start, p.not_filmed, p.pull_play, p.defense_type, p.offense_faced]
                   for _, p in sorted(state.points.items())],
        'roster': list(state.roster),
        'order': state.player_order_data,
        'known': sorted(set(csv_names) & state.known_players),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Database access
# ---------------------------------------------------------------------------

def load_state(game):
    """Read the game's points, roster and sheet order as they are now."""
    from sqlalchemy import func
    from . import db
    from .models import Comment, Player, Point
    counts = dict(db.session.query(Comment.point_id, func.count(Comment.id))
                  .filter(Comment.game_id == game.id, Comment.point_id.isnot(None))
                  .group_by(Comment.point_id).all())
    points = {}
    for p in Point.query.filter_by(game_id=game.id).all():
        points[p.point_index] = CurrentPoint(
            id=p.id, index=p.point_index, tron_o=p.tron_o, tron_point=p.tron_point,
            hidden=bool(p.hidden_by_import), players=tuple(sorted(pl.name for pl in p.players)),
            injury_subs=p.injury_subs, timestamp_start=p.timestamp_start, not_filmed=bool(p.not_filmed),
            pull_play=p.pull_play, defense_type=p.defense_type, offense_faced=p.offense_faced,
            comment_count=counts.get(p.id, 0))
    return CurrentState(points=points, roster=tuple(sorted(pl.name for pl in game.roster)),
                        player_order_data=game.player_order_data,
                        known_players=frozenset(n for (n,) in db.session.query(Player.name).all()))


def apply_plan(game, sheet, create_player):
    """Write ``sheet`` into ``game`` in the caller's transaction (the caller commits).

    ``create_player(name)`` returns a new ``Player`` (flushed). Retained points keep their
    row, comments, timestamp, not-filmed flag and labels; omitted points are hidden.
    """
    from . import db
    from .models import Player, Point
    players = {}

    def player(name):
        if name not in players:
            players[name] = Player.query.filter_by(name=name).first() or create_player(name)
        return players[name]

    existing = {p.point_index: p for p in Point.query.filter_by(game_id=game.id).all()}
    seen = set()
    for new in sheet.points:
        seen.add(new.index)
        point = existing.get(new.index)
        if point is None:
            point = Point(game_id=game.id, point_index=new.index)
            db.session.add(point)
        point.hidden_by_import = False
        point.tron_o = new.tron_o
        point.tron_point = new.tron_point
        wanted = [player(name) for name in new.players]
        if {pl.id for pl in point.players} != {pl.id for pl in wanted}:
            point.players = wanted
        if _subs_key(point.injury_subs) != _subs_key(new.injury_subs):
            point.injury_subs = new.injury_subs
    for index, point in existing.items():
        if index not in seen:
            point.hidden_by_import = True
    db.session.flush()
    game.roster = [player(name) for name in sorted({n for p in sheet.points for n in p.players})]
    game.player_order_data = sheet.player_order_data
    db.session.flush()
