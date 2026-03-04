import { html, useEffect, useMemo, useReducer, useRef, createRoot } from "./deps.js";
import { createApiClient } from "./services/api.js";
import { createInitialState, reducer } from "./state/useFilmRoomReducer.js";
import { useYouTubePlayer } from "./video/useYouTubePlayer.js";
import { GamesDrawer } from "./features/GamesDrawer.js";
import { VideoPane } from "./features/VideoPane.js";
import { PointTimeline } from "./features/PointTimeline.js";
import { CommentsPanel } from "./features/CommentsPanel.js";
import { PlayerSheet } from "./features/PlayerSheet.js";
import { safeTimestamp } from "./utils/time.js";

function flattenCommentsWithTimestamps(comments) {
  const items = [];
  for (const comment of comments || []) {
    items.push(comment);
    for (const reply of comment.replies || []) {
      items.push(reply);
    }
  }
  return items
    .filter((item) => item.timestamp !== null && item.timestamp !== undefined)
    .sort((a, b) => a.timestamp - b.timestamp || a.id - b.id);
}

function getActivePointIndex(points, currentTime) {
  let active = null;
  for (const point of points) {
    const ts = safeTimestamp(point.timestamp_start);
    if (ts === null) {
      continue;
    }
    if (ts <= currentTime) {
      active = point.point_index;
    }
  }
  return active;
}

function getActiveCommentId(comments, currentTime) {
  let active = null;
  for (const comment of comments) {
    const ts = safeTimestamp(comment.timestamp);
    if (ts === null) {
      continue;
    }
    if (ts <= currentTime) {
      active = comment.id;
    }
  }
  return active;
}

function computeLiveScore(points, activePointIndex) {
  if (!activePointIndex) {
    return { tron: 0, opp: 0 };
  }
  let tron = 0;
  let opp = 0;
  for (const point of points) {
    if (point.point_index > activePointIndex) {
      break;
    }
    if (point.tron_point) {
      tron += 1;
    } else {
      opp += 1;
    }
  }
  return { tron, opp };
}

function FilmRoomApp({ config }) {
  const api = useMemo(() => createApiClient(config.apiPrefix), [config.apiPrefix]);
  const [state, dispatch] = useReducer(reducer, createInitialState(config.initialGameId));
  const loadTokenRef = useRef(0);
  const watchRef = useRef({
    sessionId: null,
    lastWall: null,
    accumulated: 0,
    inFlight: false,
  });

  const viewer = state.game?.viewer || {
    username: config.currentUser?.username || null,
    is_admin: Boolean(config.currentUser?.isAdmin),
    player_name: null,
  };

  const points = useMemo(() => {
    return [...(state.game?.points || [])].sort((a, b) => a.point_index - b.point_index);
  }, [state.game]);

  const filteredGames = useMemo(() => {
    const normalized = (state.gamesQuery || "").trim().toLowerCase();
    if (!normalized) {
      return state.games;
    }
    return state.games.filter((item) => {
      const title = (item.title || "").toLowerCase();
      const opponent = (item.opponent || "").toLowerCase();
      return title.includes(normalized) || opponent.includes(normalized);
    });
  }, [state.games, state.gamesQuery]);

  const flattenedTimedComments = useMemo(() => {
    return flattenCommentsWithTimestamps(state.game?.comments || []);
  }, [state.game]);

  const activePoint = useMemo(() => {
    if (!state.activePointIndex) {
      return null;
    }
    return points.find((point) => point.point_index === state.activePointIndex) || null;
  }, [points, state.activePointIndex]);

  const onFieldPlayers = activePoint?.players || [];
  const liveScore = useMemo(() => computeLiveScore(points, state.activePointIndex), [points, state.activePointIndex]);

  const {
    hostRef,
    isReady: isPlayerReady,
    seekTo,
    togglePlayPause,
    seekRelative,
    fullscreen,
    getCurrentTime,
  } = useYouTubePlayer({
    videoId: state.game?.youtube_id || null,
    onTimeUpdate: ({ currentTime, duration, playerState }) => {
      dispatch({
        type: "VIDEO_TICK",
        currentTime,
        duration,
        playerState,
      });
    },
  });

  useEffect(() => {
    dispatch({ type: "LOAD_GAMES_START" });
    api
      .getGames()
      .then((payload) => {
        dispatch({ type: "LOAD_GAMES_SUCCESS", games: payload.games || [] });
      })
      .catch((err) => {
        dispatch({ type: "LOAD_GAMES_ERROR", error: err.message });
      });
  }, [api]);

  useEffect(() => {
    if (state.selectedGameId || state.games.length === 0) {
      return;
    }
    dispatch({ type: "SELECT_GAME", gameId: state.games[0].id });
  }, [state.games, state.selectedGameId]);

  async function reloadGame(gameId) {
    if (!gameId) {
      return;
    }
    const token = loadTokenRef.current + 1;
    loadTokenRef.current = token;

    dispatch({ type: "LOAD_GAME_START" });
    try {
      const payload = await api.getGame(gameId);
      if (loadTokenRef.current !== token) {
        return;
      }
      dispatch({ type: "LOAD_GAME_SUCCESS", game: payload.game });
    } catch (err) {
      if (loadTokenRef.current !== token) {
        return;
      }
      dispatch({ type: "LOAD_GAME_ERROR", error: err.message });
    }
  }

  useEffect(() => {
    if (!state.selectedGameId) {
      return;
    }
    reloadGame(state.selectedGameId);

    const targetPath = `/film/app/games/${state.selectedGameId}`;
    if (window.location.pathname !== targetPath) {
      window.history.replaceState({}, "", targetPath);
    }
  }, [state.selectedGameId]);

  useEffect(() => {
    if (!state.game) {
      return;
    }
    const nextActivePoint = getActivePointIndex(points, state.videoCurrentTime || 0);
    if (nextActivePoint !== state.activePointIndex) {
      dispatch({ type: "SET_ACTIVE_POINT", pointIndex: nextActivePoint });
    }

    const nextActiveComment = getActiveCommentId(flattenedTimedComments, state.videoCurrentTime || 0);
    if (nextActiveComment !== state.activeCommentId) {
      dispatch({ type: "SET_ACTIVE_COMMENT", commentId: nextActiveComment });
    }
  }, [
    state.game,
    points,
    flattenedTimedComments,
    state.videoCurrentTime,
    state.activePointIndex,
    state.activeCommentId,
  ]);

  useEffect(() => {
    try {
      window.sessionStorage.setItem("film_app_player_sheet_open", state.playerSheetOpen ? "1" : "0");
    } catch {
      // Ignore storage errors.
    }
  }, [state.playerSheetOpen]);

  async function pushWatchTime(force = false) {
    if (!state.selectedGameId || watchRef.current.inFlight) {
      return;
    }

    const seconds = Math.floor(watchRef.current.accumulated);
    if (!force && seconds < 10) {
      return;
    }
    if (seconds <= 0) {
      return;
    }

    watchRef.current.inFlight = true;
    watchRef.current.accumulated -= seconds;

    try {
      const payload = await api.trackWatchTime(state.selectedGameId, {
        seconds_watched: seconds,
        session_id: watchRef.current.sessionId,
      });
      watchRef.current.sessionId = payload.session_id;
    } catch {
      watchRef.current.accumulated += seconds;
    } finally {
      watchRef.current.inFlight = false;
    }
  }

  useEffect(() => {
    if (!state.game || !state.selectedGameId) {
      return;
    }

    const now = Date.now() / 1000;
    const isPlaying = state.playerState === 1;

    if (isPlaying) {
      if (watchRef.current.lastWall !== null) {
        const delta = now - watchRef.current.lastWall;
        if (delta > 0 && delta < 2) {
          watchRef.current.accumulated += delta;
        }
      }
      watchRef.current.lastWall = now;
      if (watchRef.current.accumulated >= 10) {
        pushWatchTime(false);
      }
    } else {
      watchRef.current.lastWall = null;
      if (watchRef.current.accumulated >= 1) {
        pushWatchTime(true);
      }
    }
  }, [state.playerState, state.videoCurrentTime, state.game, state.selectedGameId]);

  useEffect(() => {
    function flushOnUnload() {
      if (!state.selectedGameId) {
        return;
      }
      const seconds = Math.floor(watchRef.current.accumulated);
      if (seconds <= 0) {
        return;
      }

      const body = {
        seconds_watched: seconds,
        session_id: watchRef.current.sessionId,
      };
      const blob = new Blob([JSON.stringify(body)], { type: "application/json" });
      navigator.sendBeacon(`${config.apiPrefix}/games/${state.selectedGameId}/track-watch-time`, blob);
    }

    window.addEventListener("beforeunload", flushOnUnload);
    return () => {
      window.removeEventListener("beforeunload", flushOnUnload);
    };
  }, [state.selectedGameId, config.apiPrefix]);

  async function handleCreateComment(payload) {
    if (!state.selectedGameId) {
      return;
    }
    await api.createComment(state.selectedGameId, {
      content: payload.content,
      parent_id: payload.parent_id,
      timestamp: payload.timestamp,
      comment_type: "Comment",
    });
    await reloadGame(state.selectedGameId);
  }

  async function handleUpdateComment(commentId, content) {
    if (!state.selectedGameId) {
      return;
    }
    await api.updateComment(state.selectedGameId, commentId, {
      content,
      comment_type: "Comment",
    });
    await reloadGame(state.selectedGameId);
  }

  async function handleDeleteComment(commentId) {
    if (!state.selectedGameId) {
      return;
    }
    if (!window.confirm("Delete this comment?")) {
      return;
    }
    await api.deleteComment(state.selectedGameId, commentId);
    await reloadGame(state.selectedGameId);
  }

  async function handleUpdatePoint(pointId, patchPayload) {
    if (!state.selectedGameId) {
      return;
    }
    await api.updatePoint(state.selectedGameId, pointId, patchPayload);
    await reloadGame(state.selectedGameId);
  }

  return html`
    <div className="film-app">
      <header className="film-app__header">
        <div>
          <p className="film-app__header-kicker">Hybrid Film Room</p>
          <h1 className="film-app__header-title">React Film App</h1>
        </div>
        <div className="film-app__header-actions">
          <button className="film-app__primary-btn" onClick=${() => dispatch({ type: "SET_DRAWER_OPEN", open: true })}>
            Browse Games
          </button>
          <a className="film-app__inline-btn" href=${config.routes?.gamesPage || "/film/games"}>All Games</a>
        </div>
      </header>

      ${state.error ? html`<div className="film-app__status is-error">${state.error}</div>` : null}

      ${state.gameLoading
        ? html`<div className="film-app__panel"><div className="film-app__status">Loading game...</div></div>`
        : state.game
          ? html`
              <${PlayerSheet}
                game=${state.game}
                open=${state.playerSheetOpen}
                onToggle=${() => dispatch({ type: "SET_PLAYER_SHEET_OPEN", open: !state.playerSheetOpen })}
                activePointIndex=${state.activePointIndex}
                onSeekPoint=${(seconds) => seekTo(seconds)}
              />

              <div className="film-app__hero-grid">
                <${VideoPane}
                  game=${state.game}
                  viewer=${viewer}
                  hostRef=${hostRef}
                  isPlayerReady=${isPlayerReady}
                  currentTime=${state.videoCurrentTime}
                  duration=${state.videoDuration}
                  score=${liveScore}
                  onFieldPlayers=${onFieldPlayers}
                  togglePlayPause=${togglePlayPause}
                  seekRelative=${seekRelative}
                  fullscreen=${fullscreen}
                />

                <${CommentsPanel}
                  comments=${state.game.comments || []}
                  viewer=${viewer}
                  mentionables=${state.game.mentionables || []}
                  activeCommentId=${state.activeCommentId}
                  onSeek=${(seconds) => seekTo(seconds)}
                  onCreateComment=${handleCreateComment}
                  onUpdateComment=${handleUpdateComment}
                  onDeleteComment=${handleDeleteComment}
                  getCurrentVideoTime=${getCurrentTime}
                />
              </div>

              <${PointTimeline}
                points=${points}
                pointFieldOptions=${state.game.point_field_options || {}}
                viewer=${viewer}
                activePointIndex=${state.activePointIndex}
                onSeekPoint=${(seconds) => seekTo(seconds)}
                onUpdatePoint=${handleUpdatePoint}
              />
            `
          : html`<div className="film-app__panel"><div className="film-app__status">Choose a game to get started.</div></div>`}

      <${GamesDrawer}
        open=${state.drawerOpen}
        onClose=${() => dispatch({ type: "SET_DRAWER_OPEN", open: false })}
        games=${filteredGames}
        loading=${state.gamesLoading}
        query=${state.gamesQuery}
        onQueryChange=${(value) => dispatch({ type: "SET_GAMES_QUERY", value })}
        selectedGameId=${state.selectedGameId}
        onSelectGame=${(gameId) => dispatch({ type: "SELECT_GAME", gameId })}
      />
    </div>
  `;
}

export function mountFilmRoomApp(config) {
  const rootNode = document.getElementById("film-room-app-root");
  if (!rootNode) {
    return;
  }
  createRoot(rootNode).render(html`<${FilmRoomApp} config=${config} />`);
}
