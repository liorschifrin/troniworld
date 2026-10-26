"""Run the real pages in Chromium without a network or a running server (T12).

``AppBridge`` answers every request the page makes: requests to the fake origin go to Flask's test client
(the in-memory test database, no socket), the YouTube IFrame API script is replaced by a local stub, and every
other host is refused, so a test cannot depend on the network or on a real video.
"""
from urllib.parse import urlsplit

ORIGIN = 'http://troniworld.test'
YOUTUBE_API = 'https://www.youtube.com/iframe_api'

# A minimal stand-in for the YouTube IFrame Player API. It records every command in window.__yt.calls and keeps
# a fake clock, so tests can check what the page asked the player to do. A video id starting with "err" makes it
# report an embed error (code 150), as YouTube does for a removed or non-embeddable video.
YOUTUBE_STUB = r"""
(function () {
  var S = { UNSTARTED: -1, ENDED: 0, PLAYING: 1, PAUSED: 2, BUFFERING: 3, CUED: 5 };
  window.__yt = { calls: [] };
  function Player(id, opts) {
    var self = this, host = document.getElementById(id);
    var iframe = document.createElement('iframe');
    iframe.id = id; iframe.title = 'YouTube video player'; iframe.src = 'about:blank';
    iframe.setAttribute('allowfullscreen', '');
    host.parentNode.replaceChild(iframe, host);
    var state = S.CUED, position = 0, mark = Date.now(), rate = 1, muted = false, events = opts.events || {};
    function now() { return position + (state === S.PLAYING ? (Date.now() - mark) / 1000 * rate : 0); }
    function set(next) { position = now(); mark = Date.now(); state = next; if (events.onStateChange) events.onStateChange({ data: next }); }
    function log(name, arg) { window.__yt.calls.push(arg === undefined ? name : name + ':' + arg); }
    self.playVideo = function () { log('play'); set(S.PLAYING); };
    self.pauseVideo = function () { log('pause'); set(S.PAUSED); };
    self.seekTo = function (s) { s = Math.max(0, s); log('seek', Math.round(s)); position = s; mark = Date.now(); };
    self.getCurrentTime = function () { return now(); };
    self.getDuration = function () { return 600; };
    self.getPlayerState = function () { return state; };
    self.setPlaybackRate = function (r) { log('rate', r); rate = r; position = now(); mark = Date.now(); };
    self.getPlaybackRate = function () { return rate; };
    self.mute = function () { log('mute'); muted = true; };
    self.unMute = function () { log('unmute'); muted = false; };
    self.isMuted = function () { return muted; };
    self.getIframe = function () { return iframe; };
    self.loadVideoById = function (v) { log('load', v); };
    setTimeout(function () {
      if (String(opts.videoId).indexOf('err') === 0) { if (events.onError) events.onError({ data: 150 }); return; }
      if (events.onReady) events.onReady({ target: self });
    }, 0);
  }
  window.YT = { Player: Player, PlayerState: S };
  if (window.onYouTubeIframeAPIReady) window.onYouTubeIframeAPIReady();
})();
"""


class AppBridge:
    """Routes a Playwright context's traffic to a Flask test client."""

    def __init__(self, client, youtube='stub'):
        self.client = client
        self.youtube = youtube  # 'stub' | 'blocked' (the API script fails to load) | 'hang' (never answers)
        self.requests = []  # (method, path) of every request that reached the app
        self.refused = []  # URLs that were refused because they leave the fake origin

    def install(self, context):
        context.route('**/*', self._handle)

    def _handle(self, route):
        request = route.request
        if request.url == YOUTUBE_API:
            if self.youtube == 'stub':
                return route.fulfill(status=200, content_type='application/javascript', body=YOUTUBE_STUB)
            if self.youtube == 'hang':
                return None  # leave the request pending
            return route.abort()
        parts = urlsplit(request.url)
        if f'{parts.scheme}://{parts.netloc}' != ORIGIN:
            self.refused.append(request.url)
            return route.abort()
        path = parts.path + (f'?{parts.query}' if parts.query else '')
        self.requests.append((request.method, parts.path))
        headers = {k: v for k, v in request.headers.items()
                   if k.lower() not in ('host', 'cookie', 'content-length')}
        reply = self.client.open(path, method=request.method, headers=headers, data=request.post_data_buffer)
        skip = {'set-cookie', 'content-length', 'transfer-encoding', 'connection'}
        return route.fulfill(status=reply.status_code, body=reply.get_data(),
                             headers={k: v for k, v in reply.headers.items() if k.lower() not in skip})
