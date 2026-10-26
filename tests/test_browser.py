"""T12: the film-room player, comments, notifications and navigation in a real Chromium.

Opt-in: ``python -m playwright install chromium`` then ``python -m pytest -m browser``. Every page is served by
Flask's test client through ``browser_support.AppBridge`` (in-memory synthetic database, no server, no network)
and YouTube is a local stub, so a failure here is a defect in the page and not in a service. Desktop runs use a
1280x800 Chromium; mobile runs use 390x844 with touch and mobile emulation. No other browser is covered.
"""
import os
import re

import pytest

pytestmark = pytest.mark.browser

sync_api = pytest.importorskip('playwright.sync_api')

from browser_support import ORIGIN, AppBridge  # noqa: E402

DESKTOP = dict(viewport={'width': 1280, 'height': 800})
MOBILE = dict(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True,
              user_agent='Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/130.0.0.0 Mobile Safari/537.36')
sync_api.expect.set_options(timeout=5000)


@pytest.fixture(scope='module')
def chromium():
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Exception as error:  # Chromium is not installed
            if os.environ.get('CI'):  # a CI job that installed Chromium must not pass by skipping
                raise
            pytest.skip(f'Chromium is not available ({str(error).splitlines()[0]})')
        yield browser
        browser.close()


@pytest.fixture
def data(db, records):
    """The shared synthetic game with a video, three timed points, a roster and one unread mention."""
    from flask_app.models import Comment, CommentNotification, Game, Player, Point
    game = records['game']
    names = ['Synthetic Alpha', 'Synthetic Bravo', 'Synthetic Charlie']
    players = [Player(name=name, active=True) for name in names]
    db.session.add_all(players)
    game.youtube_id = 'synthetic01'
    game.player_order_data = {'players': names}
    game.roster = list(players)
    records['point'].timestamp_start, records['point'].tron_o, records['point'].tron_point = 10, True, True
    records['point'].players = players[:2]
    for index, start in ((2, 60), (3, 120)):
        point = Point(game_id=game.id, point_index=index, timestamp_start=start, tron_o=False, tron_point=False)
        point.players = players[1:]
        db.session.add(point)
    novideo = Game(title='Synthetic game without video', opponent='Synthetic visitors')
    mention = Comment(game_id=game.id, author_name='admin', comment_type='Comment', timestamp=30,
                      content='Synthetic mention for @[ordinary] to read')
    db.session.add_all([novideo, mention])
    db.session.flush()
    notification = CommentNotification(recipient_username='ordinary', comment_id=mention.id, game_id=game.id,
                                       notification_type='mention')
    db.session.add(notification)
    db.session.commit()
    return dict(records, novideo=novideo, mention=mention, notification=notification)


class Site:
    def __init__(self, page, bridge, errors):
        self.page, self.bridge, self.errors = page, bridge, errors

    def open(self, path, ready=True):
        self.page.goto(ORIGIN + path, wait_until='domcontentloaded')
        if ready:
            self.page.wait_for_function('typeof playerReady !== "undefined" && playerReady === true')
        return self.page

    def yt_calls(self):
        return self.page.evaluate('window.__yt ? window.__yt.calls : []')


@pytest.fixture
def site(chromium, client_for, data):
    contexts = []

    def make(role='ordinary', mobile=False, youtube='stub'):
        bridge = AppBridge(client_for(role), youtube=youtube)
        context = chromium.new_context(**(MOBILE if mobile else DESKTOP))
        contexts.append(context)
        bridge.install(context)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        return Site(page, bridge, errors)

    yield make
    for context in contexts:
        context.close()


def game_path(data, key='game', query=''):
    return f'/film/games/{data[key].id}{query}'


def snapshot(page, selector='body'):
    return page.locator(selector).aria_snapshot()


# -- critical workflows --------------------------------------------------------------------------------------

def test_open_game_shows_player_controls_without_errors(site, data):
    s = site()
    page = s.open(game_path(data))
    assert 'Synthetic public game' in page.locator('h1').inner_text()
    assert page.locator('#player').get_attribute('title') == 'YouTube video player'
    expect = sync_api.expect
    expect(page.get_by_role('button', name='Play', exact=True)).to_be_visible()
    expect(page.locator('#commentsList')).to_contain_text('Synthetic mention')
    assert s.errors == []
    # the only thing that tried to leave the fake origin is the web-font stylesheet
    assert all(url.startswith('https://fonts.googleapis.com/') for url in s.bridge.refused), s.bridge.refused


@pytest.mark.parametrize('mobile', [False, True], ids=['desktop', 'mobile'])
def test_play_pause_with_button(site, data, mobile):
    s = site(mobile=mobile)
    page = s.open(game_path(data))
    play = page.get_by_role('button', name='Play', exact=True)
    play.click()
    sync_api.expect(page.get_by_role('button', name='Pause', exact=True)).to_be_visible()
    page.get_by_role('button', name='Pause', exact=True).click()
    sync_api.expect(page.get_by_role('button', name='Play', exact=True)).to_be_visible()
    assert s.yt_calls() == ['play', 'pause']


@pytest.mark.parametrize('mobile', [False, True], ids=['desktop', 'mobile'])
def test_post_comment_with_keyboard_and_button(site, data, db, mobile):
    from flask_app.models import Comment
    s = site(mobile=mobile)
    page = s.open(game_path(data))
    if mobile:  # the input is folded away on a single-column layout until "+ Comment" opens it
        page.get_by_role('button', name='+ Comment').click()
    box = page.get_by_role('textbox', name='Add a comment')
    box.click()
    page.keyboard.type('Synthetic keyboard comment')
    page.keyboard.press('Enter')
    sync_api.expect(page.locator('#commentsList')).to_contain_text('Synthetic keyboard comment')
    if mobile:
        page.get_by_role('button', name='+ Comment').click()
        box.click()
    box.click()
    page.keyboard.type('Synthetic button comment')
    page.get_by_role('button', name='Post Comment').click()
    sync_api.expect(page.locator('#commentsList')).to_contain_text('Synthetic button comment')
    db.session.expire_all()
    stored = {c.content for c in Comment.query.filter_by(game_id=data['game'].id)}
    assert {'Synthetic keyboard comment', 'Synthetic button comment'} <= stored
    assert s.errors == []


@pytest.mark.parametrize('mobile', [False, True], ids=['desktop', 'mobile'])
def test_mark_notification_read(site, data, db, mobile):
    from flask_app.models import CommentNotification
    s = site(mobile=mobile)
    page = s.open(game_path(data, 'novideo'), ready=False)
    sync_api.expect(page.locator('#notifBellBadge')).to_have_text('1')
    page.get_by_role('button', name=re.compile('Notifications')).click()
    item = page.locator('.notif-item.unread')
    sync_api.expect(item).to_have_count(1)
    item.click()
    page.wait_for_url(re.compile(r'\?comment=%d$' % data['mention'].id))
    page.wait_for_function('typeof playerReady !== "undefined" && playerReady === true')
    db.session.expire_all()
    assert db.session.get(CommentNotification, data['notification'].id).is_read is True
    sync_api.expect(page.locator('#notifBellBadge')).to_have_attribute('data-count', '0')


def test_mark_all_notifications_read(site, data, db):
    from flask_app.models import CommentNotification
    s = site()
    page = s.open(game_path(data))
    page.get_by_role('button', name=re.compile('Notifications')).click()
    page.get_by_role('button', name='Mark all read').click()
    sync_api.expect(page.locator('#notifBellBadge')).to_have_attribute('data-count', '0')
    page.wait_for_timeout(200)
    db.session.expire_all()
    assert db.session.get(CommentNotification, data['notification'].id).is_read is True


# -- shortcuts and editable text -----------------------------------------------------------------------------

SHORTCUT_KEYS = 'kjlmfFMKJL<>tT ,.'


@pytest.mark.parametrize('field', ['comment', 'private', 'video_url'])
def test_shortcuts_do_not_fire_while_typing(site, data, field):
    s = site()
    if field == 'video_url':
        page = s.open(game_path(data, 'novideo'), ready=False)
        target = page.locator('#videoUrl')
    else:
        page = s.open(game_path(data))
        if field == 'private':
            page.get_by_role('button', name='Private', exact=False).first.click()
            target = page.locator('#privateToInput')
        else:
            target = page.get_by_role('textbox', name='Add a comment')
    target.click()
    # a comma in the private-to box turns the text into a user chip, which is that box's own behaviour
    keys = SHORTCUT_KEYS.replace(',', '') if field == 'private' else SHORTCUT_KEYS
    page.keyboard.type(keys)
    assert s.yt_calls() == []
    typed = target.input_value() if field != 'comment' else target.inner_text()
    assert typed.replace('\xa0', ' ') == keys
    assert page.evaluate('document.body.classList.contains("theater-mode")') is False
    assert s.errors == []


def test_shortcuts_do_not_fire_in_reply_and_edit_editors(site, data):
    s = site('admin')
    page = s.open(game_path(data))
    reply = page.get_by_role('button', name=re.compile('Reply')).first
    reply.focus()  # hidden until hover for a mouse user, but a keyboard user must be able to reach and see it
    assert reply.evaluate('b => getComputedStyle(b).opacity') == '1'
    page.keyboard.press('Enter')
    editor = page.get_by_role('textbox', name=re.compile('Reply'))
    editor.click()
    page.keyboard.type(SHORTCUT_KEYS)
    assert s.yt_calls() == []


def test_each_shortcut_acts_once_outside_text(site, data):
    s = site()
    page = s.open(game_path(data))
    page.locator('body').click(position={'x': 2, 'y': 2})
    for key in ('k', 'k', 'l', 'j', 'm', 'm', '>', '<'):
        page.keyboard.press(key)
    assert s.yt_calls() == ['play', 'pause', 'seek:10', 'seek:0', 'mute', 'unmute', 'rate:1.25', 'rate:1']


def test_space_on_a_focused_button_activates_that_button_only(site, data):
    s = site()
    page = s.open(game_path(data))
    page.locator('#vcTheaterBtn').focus()
    page.keyboard.press('Space')
    assert page.evaluate('document.body.classList.contains("theater-mode")') is True
    assert s.yt_calls() == []
    page.locator('#vcMuteBtn').focus()
    page.keyboard.press('Enter')
    assert s.yt_calls() == ['mute']


# -- keyboard and focus --------------------------------------------------------------------------------------

def focus_chain(page, steps):
    seen = []
    for _ in range(steps):
        page.keyboard.press('Tab')
        seen.append(page.evaluate('''() => { const e = document.activeElement;
            return e.id || e.getAttribute("aria-label") || e.textContent.trim().slice(0, 30); }'''))
    return seen


def test_tab_reaches_every_player_control_in_order(site, data):
    s = site()
    page = s.open(game_path(data))
    page.locator('#watchedToggleBtn').focus()
    chain = focus_chain(page, 14)
    controls = ['vcMuteBtn', 'vcFullscreenBtn', 'vcTheaterBtn']
    assert [c for c in chain if c in controls] == controls
    for label in ('Back 10 seconds', 'Play', 'Forward 10 seconds'):
        assert any(label in str(c) for c in chain), (label, chain)


def test_focused_controls_have_a_visible_focus_indicator(site, data):
    s = site()
    page = s.open(game_path(data))
    page.locator('body').click(position={'x': 2, 'y': 2})
    page.keyboard.press('Tab')
    seen = set()
    for _ in range(14):
        info = page.evaluate('''() => { const e = document.activeElement, s = getComputedStyle(e);
            return { tag: e.tagName, id: e.id,
              ring: (s.outlineStyle !== "none" && parseFloat(s.outlineWidth) > 0) || s.boxShadow !== "none" }; }''')
        if info['tag'] != 'IFRAME':  # the embedded YouTube player draws its own focus ring
            seen.add((info['id'] or info['tag'], info['ring']))
        page.keyboard.press('Tab')
    assert seen and all(ring for _, ring in seen), sorted(seen)


def test_buttons_and_links_have_accessible_names(site, data):
    s = site('admin')
    page = s.open(game_path(data))
    page.get_by_role('button', name=re.compile('Notifications')).click()
    tree = snapshot(page)
    nameless = [line.strip() for line in tree.splitlines() if re.match(r'\s*- (button|link|textbox)( \[.*\])?:?$', line)]
    assert nameless == []


def test_toggle_buttons_expose_their_state(site, data):
    s = site()
    page = s.open(game_path(data))
    for selector, before, after in (('#vcMuteBtn', 'false', 'true'), ('#vcTheaterBtn', 'false', 'true'),
                                    ('#watchedToggleBtn', 'false', 'true'), ('#privacyToggleBtn', 'false', 'true')):
        button = page.locator(selector)
        assert button.get_attribute('aria-pressed') == before, selector
        button.click()
        sync_api.expect(button).to_have_attribute('aria-pressed', after)
    speed = page.locator('.vc-speed[data-rate="2"]')
    assert speed.get_attribute('aria-pressed') == 'false'
    speed.click()
    sync_api.expect(speed).to_have_attribute('aria-pressed', 'true')
    sync_api.expect(page.locator('.vc-speed[data-rate="1"]')).to_have_attribute('aria-pressed', 'false')


def test_player_sheet_disclosure_state_and_keyboard(site, data):
    s = site()
    page = s.open(game_path(data))
    toggle = page.get_by_role('button', name=re.compile('Player Sheet'))
    assert toggle.get_attribute('aria-expanded') == 'false'
    toggle.focus()
    page.keyboard.press('Enter')
    sync_api.expect(toggle).to_have_attribute('aria-expanded', 'true')
    sync_api.expect(page.locator('#playerSheetContent')).to_have_class(re.compile('open'))
    page.keyboard.press('Space')
    sync_api.expect(toggle).to_have_attribute('aria-expanded', 'false')


def test_point_cards_seek_from_the_keyboard(site, data):
    s = site()
    page = s.open(game_path(data))
    card = page.get_by_role('button', name=re.compile('P2'))
    card.focus()
    page.keyboard.press('Enter')
    assert s.yt_calls() == ['seek:60']
    card.focus()
    page.keyboard.press('Space')
    assert s.yt_calls() == ['seek:60', 'seek:60']


def test_comment_timestamps_seek_from_the_keyboard(site, data):
    s = site()
    page = s.open(game_path(data))
    comment = page.locator('.comment-item[data-timestamp]').first
    page.get_by_role('button', name=re.compile('Jump to 0:30')).focus()
    page.keyboard.press('Enter')
    assert s.yt_calls() == ['seek:30']


def test_comment_composer_flow_by_keyboard_only(site, data, db):
    from flask_app.models import Comment
    s = site()
    page = s.open(game_path(data))
    page.get_by_role('textbox', name='Add a comment').focus()
    page.keyboard.type('Synthetic keyboard only')
    page.keyboard.press('Tab')
    assert page.evaluate('document.activeElement.id') == 'privacyToggleBtn'
    page.keyboard.press('Tab')
    assert page.evaluate('document.activeElement.textContent.trim()') == 'Post Comment'
    page.keyboard.press('Enter')
    sync_api.expect(page.locator('#commentsList')).to_contain_text('Synthetic keyboard only')
    db.session.expire_all()
    assert Comment.query.filter_by(content='Synthetic keyboard only').count() == 1


def test_mention_dropdown_keyboard_and_roles(site, data):
    s = site()
    page = s.open(game_path(data))
    box = page.get_by_role('textbox', name='Add a comment')
    box.click()
    page.keyboard.type('@adm')
    listbox = page.get_by_role('listbox')
    sync_api.expect(listbox).to_be_visible()
    sync_api.expect(page.get_by_role('option', name=re.compile('admin'))).to_have_count(1)
    assert box.get_attribute('aria-expanded') == 'true'
    page.keyboard.press('Escape')
    sync_api.expect(listbox).to_be_hidden()
    assert box.get_attribute('aria-expanded') == 'false'
    page.keyboard.type(' @adm')
    sync_api.expect(listbox).to_be_visible()
    page.keyboard.press('Enter')
    sync_api.expect(box.locator('.mention-token')).to_have_count(1)
    assert s.yt_calls() == []


# -- notification dropdown -----------------------------------------------------------------------------------

def test_notification_dropdown_keyboard_flow(site, data, db):
    from flask_app.models import CommentNotification
    s = site()
    page = s.open(game_path(data))
    bell = page.get_by_role('button', name=re.compile('Notifications'))
    assert bell.get_attribute('aria-expanded') == 'false'
    assert bell.get_attribute('aria-haspopup') == 'true'
    bell.focus()
    page.keyboard.press('Enter')
    sync_api.expect(bell).to_have_attribute('aria-expanded', 'true')
    item = page.locator('.notif-item.unread')
    sync_api.expect(item).to_have_count(1)
    assert 'unread' in item.get_attribute('aria-label').lower()
    page.keyboard.press('Escape')
    sync_api.expect(bell).to_have_attribute('aria-expanded', 'false')
    assert page.evaluate('document.activeElement.id') == 'notifBellBtn'
    page.keyboard.press('Enter')
    item.focus()
    page.keyboard.press('Enter')
    page.wait_for_url(re.compile(r'\?comment='))
    db.session.expire_all()
    assert db.session.get(CommentNotification, data['notification'].id).is_read is True


def test_notification_tabs_expose_selection(site, data):
    s = site()
    page = s.open(game_path(data))
    page.get_by_role('button', name=re.compile('Notifications')).click()
    main, replies = page.get_by_role('tab', name=re.compile('Mentions')), page.get_by_role('tab', name=re.compile('Replies'))
    assert main.get_attribute('aria-selected') == 'true'
    assert replies.get_attribute('aria-selected') == 'false'
    replies.click()
    sync_api.expect(replies).to_have_attribute('aria-selected', 'true')
    sync_api.expect(main).to_have_attribute('aria-selected', 'false')


# -- roster edit ---------------------------------------------------------------------------------------------

def test_roster_edit_by_keyboard(site, data, db):
    from flask_app.models import Point
    s = site('admin')
    page = s.open(game_path(data))
    page.get_by_role('button', name=re.compile('Edit Roster')).click()
    cell = page.locator('td[data-player="Synthetic Charlie"][data-point-id="%d"]' % data['point'].id)
    assert cell.get_attribute('role') == 'button'
    assert cell.get_attribute('aria-pressed') == 'false'
    cell.focus()
    page.keyboard.press('Space')
    sync_api.expect(cell).to_have_attribute('aria-pressed', 'true')
    page.keyboard.press('ArrowRight')
    assert page.evaluate('document.activeElement.dataset.pointId') != str(data['point'].id)
    page.get_by_role('button', name=re.compile('Cancel')).click()
    assert cell.get_attribute('tabindex') is None
    assert page.get_by_role('button', name=re.compile('Edit Roster')).is_visible()


# -- YouTube unavailable -------------------------------------------------------------------------------------

def test_youtube_script_blocked_shows_a_visible_error(site, data):
    s = site(youtube='blocked')
    page = s.open(game_path(data), ready=False)
    alert = page.get_by_role('alert').filter(has_text='video')
    sync_api.expect(alert).to_be_visible()
    assert 'YouTube' in alert.inner_text()
    assert page.get_by_role('button', name='Play', exact=True).is_disabled()
    page.keyboard.press('k')  # a shortcut with no player must not raise
    assert s.errors == []


def test_youtube_never_answering_times_out_visibly(site, data):
    s = site(youtube='hang')
    s.page.clock.install()
    page = s.open(game_path(data), ready=False)
    page.clock.fast_forward(20000)
    sync_api.expect(page.get_by_role('alert').filter(has_text='video')).to_be_visible()


def test_youtube_embed_error_event_shows_a_visible_error(chromium, site, data, db):
    data['game'].youtube_id = 'errorvideo1'
    db.session.commit()
    s = site()
    page = s.open(game_path(data), ready=False)
    alert = page.get_by_role('alert').filter(has_text='video')
    sync_api.expect(alert).to_be_visible()
    assert 'embedded' in alert.inner_text().lower() or 'unavailable' in alert.inner_text().lower()


def test_load_video_with_no_api_does_not_crash(site, data):
    s = site(youtube='blocked')
    page = s.open(game_path(data, 'novideo'), ready=False)
    page.locator('#videoUrl').fill('https://youtu.be/dQw4w9WgXcQ')
    page.get_by_role('button', name='Load Video').click()
    sync_api.expect(page.get_by_role('alert').filter(has_text='video')).to_be_visible()
    assert s.errors == []


# -- mobile layout and navigation (390x844) -----------------------------------------------------------------

def test_mobile_page_does_not_scroll_sideways(site, data):
    s = site(mobile=True)
    page = s.open(game_path(data))
    assert page.evaluate('window.innerWidth') == 390
    overflow = page.evaluate('document.documentElement.scrollWidth - window.innerWidth')
    assert overflow <= 0, overflow


def test_mobile_controls_are_visible_and_large_enough_to_tap(site, data):
    s = site(mobile=True)
    page = s.open(game_path(data))
    small = page.evaluate('''() => [...document.querySelectorAll("#videoControls button")]
        .filter(b => b.offsetParent !== null)
        .map(b => [b.id || b.getAttribute("aria-label"), b.getBoundingClientRect().height, b.getBoundingClientRect().width])
        .filter(([, h, w]) => h < 32 || w < 32)''')
    assert small == [], small


def test_mobile_menu_is_a_labelled_disclosure_with_focus_handling(site, data):
    s = site(mobile=True)
    page = s.open(game_path(data))
    burger = page.get_by_role('button', name='Menu', exact=True)
    assert burger.get_attribute('aria-expanded') == 'false'
    burger.click()
    sync_api.expect(burger).to_have_attribute('aria-expanded', 'true')
    menu = page.locator('.film-nav__mobile-menu')
    sync_api.expect(menu).to_have_class(re.compile('active'))
    assert page.evaluate('document.activeElement.closest(".film-nav__mobile-menu") !== null')
    page.keyboard.press('Escape')
    sync_api.expect(menu).not_to_have_class(re.compile('active'))
    sync_api.expect(burger).to_have_attribute('aria-expanded', 'false')
    assert page.evaluate('document.activeElement.className') == 'film-nav__hamburger'


def test_mobile_notification_dropdown_fits_the_viewport(site, data):
    s = site(mobile=True)
    page = s.open(game_path(data))
    page.get_by_role('button', name=re.compile('Notifications')).click()
    box = page.locator('#notifDropdown').bounding_box()
    assert box['x'] >= 0 and box['x'] + box['width'] <= 390 + 0.5


def test_mobile_comment_input_opens_with_a_disclosure_button(site, data):
    s = site(mobile=True)
    page = s.open(game_path(data))
    button = page.get_by_role('button', name='+ Comment')
    assert button.get_attribute('aria-expanded') == 'false'
    button.click()
    sync_api.expect(button).to_have_attribute('aria-expanded', 'true')
    sync_api.expect(page.get_by_role('textbox', name='Add a comment')).to_be_visible()


def test_mobile_player_sheet_and_points_fit(site, data):
    s = site(mobile=True)
    page = s.open(game_path(data))
    cards = page.locator('.point-item')
    assert cards.count() == 3
    box = cards.first.bounding_box()
    assert box['width'] > 0 and box['x'] < 390


def test_admin_add_time_menu_by_keyboard(site, data, db):
    from flask_app.models import Point
    db.session.add(Point(game_id=data['game'].id, point_index=4, tron_o=True, tron_point=True))
    db.session.commit()
    s = site('admin')
    page = s.open(game_path(data))
    opener = page.get_by_role('button', name='Set time for P4')
    assert opener.get_attribute('aria-expanded') == 'false'
    opener.focus()
    page.keyboard.press('Enter')
    sync_api.expect(page.get_by_role('menu')).to_be_visible()
    assert opener.get_attribute('aria-expanded') == 'true'
    assert page.evaluate('document.activeElement.id') == 'pamSetTime'
    page.keyboard.press('Escape')
    sync_api.expect(page.get_by_role('menu')).to_be_hidden()
    assert page.evaluate('document.activeElement.getAttribute("aria-label")') == 'Set time for P4'
    assert opener.get_attribute('aria-expanded') == 'false'


def test_roster_edit_reaches_not_filmed_cells_by_keyboard(site, data, db):
    from flask_app.models import Point
    point = Point(game_id=data['game'].id, point_index=4, not_filmed=True, tron_o=True, tron_point=True)
    db.session.add(point)
    db.session.commit()
    s = site('admin')
    page = s.open(game_path(data))
    page.get_by_role('button', name=re.compile('Edit Roster')).click()
    cell = page.locator('td[data-player="Synthetic Alpha"][data-point-id="%d"]' % point.id)
    assert cell.get_attribute('role') == 'button'
    cell.focus()
    page.keyboard.press('Enter')
    sync_api.expect(cell).to_have_attribute('aria-pressed', 'true')
