import React, { useEffect, useMemo, useState } from "https://esm.sh/react@18.3.1";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client";
import htm from "https://esm.sh/htm@3.1.1";

const html = htm.bind(React.createElement);

const bootstrap = window.TRONI_FILM_APP_CONFIG || {};
const API_PREFIX = bootstrap.apiPrefix || "/api/v1";

function toInt(value) {
  const num = Number.parseInt(value, 10);
  return Number.isFinite(num) ? num : null;
}

function formatClock(seconds) {
  const total = toInt(seconds);
  if (total === null || total < 0) {
    return "";
  }
  const mins = Math.floor(total / 60);
  const secs = String(total % 60).padStart(2, "0");
  return `${mins}:${secs}`;
}

function scoreLabel(game) {
  if (game.final_score_tron === null || game.final_score_tron === undefined) {
    return "";
  }
  if (game.final_score_opponent === null || game.final_score_opponent === undefined) {
    return "";
  }
  return `${game.final_score_tron}-${game.final_score_opponent}`;
}

async function apiFetch(path, options = {}) {
  const init = {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.headers || {}),
    },
  };

  if (init.body && !init.headers["Content-Type"]) {
    init.headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_PREFIX}${path}`, init);
  const contentType = response.headers.get("content-type") || "";
  let payload = {};

  if (contentType.includes("application/json")) {
    payload = await response.json();
  } else {
    payload = { error: `Unexpected response (${response.status})` };
  }

  if (!response.ok) {
    throw new Error(payload.error || `Request failed (${response.status})`);
  }

  return payload;
}

function canManageComment(comment, currentUser) {
  if (!currentUser || !currentUser.username) {
    return false;
  }
  return Boolean(currentUser.isAdmin) || comment.author_name === currentUser.username;
}

function removeCommentFromTree(comments, commentId) {
  return comments
    .filter((comment) => comment.id !== commentId)
    .map((comment) => ({
      ...comment,
      replies: (comment.replies || []).filter((reply) => reply.id !== commentId),
    }));
}

function FilmRoomApp() {
  const initialGameId = toInt(bootstrap.initialGameId);

  const [games, setGames] = useState([]);
  const [gamesLoading, setGamesLoading] = useState(true);
  const [selectedGameId, setSelectedGameId] = useState(initialGameId);
  const [game, setGame] = useState(null);
  const [gameLoading, setGameLoading] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [commentType, setCommentType] = useState("Comment");
  const [commentText, setCommentText] = useState("");
  const [commentTimestamp, setCommentTimestamp] = useState("");
  const [commentBusy, setCommentBusy] = useState(false);
  const [videoStart, setVideoStart] = useState(0);
  const [videoVersion, setVideoVersion] = useState(0);

  useEffect(() => {
    let ignore = false;
    setGamesLoading(true);
    apiFetch("/games")
      .then((payload) => {
        if (ignore) {
          return;
        }
        const nextGames = payload.games || [];
        setGames(nextGames);
        if (!initialGameId && nextGames.length > 0) {
          setSelectedGameId(nextGames[0].id);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (!ignore) {
          setGamesLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [initialGameId]);

  useEffect(() => {
    if (!selectedGameId) {
      setGame(null);
      return;
    }

    let ignore = false;
    setGameLoading(true);
    setError("");

    apiFetch(`/games/${selectedGameId}`)
      .then((payload) => {
        if (!ignore) {
          setGame(payload.game);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (!ignore) {
          setGameLoading(false);
        }
      });

    const targetPath = `/film/app/games/${selectedGameId}`;
    if (window.location.pathname !== targetPath) {
      window.history.replaceState({}, "", targetPath);
    }

    return () => {
      ignore = true;
    };
  }, [selectedGameId]);

  const filteredGames = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return games;
    }
    return games.filter((item) => {
      const title = (item.title || "").toLowerCase();
      const opponent = (item.opponent || "").toLowerCase();
      return title.includes(normalized) || opponent.includes(normalized);
    });
  }, [games, query]);

  function jumpToTimestamp(seconds) {
    const target = toInt(seconds);
    if (target === null || target < 0) {
      return;
    }
    setVideoStart(target);
    setVideoVersion((current) => current + 1);
  }

  async function submitComment(event) {
    event.preventDefault();
    if (!game || commentBusy) {
      return;
    }

    const content = commentText.trim();
    if (!content && commentType !== "Event") {
      setError("Comment text is required unless type is Event.");
      return;
    }

    const timestamp = commentTimestamp.trim() ? toInt(commentTimestamp) : null;
    if (commentTimestamp.trim() && timestamp === null) {
      setError("Timestamp must be a whole number in seconds.");
      return;
    }

    setCommentBusy(true);
    setError("");

    try {
      const payload = await apiFetch(`/games/${game.id}/comments`, {
        method: "POST",
        body: JSON.stringify({
          content,
          comment_type: commentType,
          timestamp,
        }),
      });

      setGame((prev) => {
        if (!prev) {
          return prev;
        }
        return {
          ...prev,
          comments: [...prev.comments, payload.comment],
        };
      });

      setCommentText("");
      setCommentTimestamp("");
      setCommentType("Comment");
    } catch (err) {
      setError(err.message);
    } finally {
      setCommentBusy(false);
    }
  }

  async function deleteComment(commentId) {
    if (!game) {
      return;
    }
    if (!window.confirm("Delete this comment?")) {
      return;
    }

    try {
      await apiFetch(`/games/${game.id}/comments/${commentId}`, {
        method: "DELETE",
      });
      setGame((prev) => {
        if (!prev) {
          return prev;
        }
        return {
          ...prev,
          comments: removeCommentFromTree(prev.comments, commentId),
        };
      });
    } catch (err) {
      setError(err.message);
    }
  }

  async function editComment(comment) {
    if (!game) {
      return;
    }

    const updated = window.prompt("Update comment text", comment.content || "");
    if (updated === null) {
      return;
    }

    try {
      const payload = await apiFetch(`/games/${game.id}/comments/${comment.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          content: updated,
          comment_type: comment.comment_type || "Comment",
        }),
      });

      setGame((prev) => {
        if (!prev) {
          return prev;
        }
        return {
          ...prev,
          comments: prev.comments.map((item) => {
            if (item.id === payload.comment.id) {
              return { ...item, ...payload.comment };
            }
            return {
              ...item,
              replies: (item.replies || []).map((reply) =>
                reply.id === payload.comment.id ? { ...reply, ...payload.comment } : reply
              ),
            };
          }),
        };
      });
    } catch (err) {
      setError(err.message);
    }
  }

  const youtubeUrl = game?.youtube_id
    ? `https://www.youtube.com/embed/${game.youtube_id}?rel=0&modestbranding=1&start=${videoStart}`
    : "";

  return html`
    <div className="film-app">
      <aside className="film-app__panel">
        <div className="film-app__panel-header">
          <div>
            <div className="film-app__panel-title">Games</div>
            <div className="film-app__panel-subtitle">API-driven list</div>
          </div>
        </div>
        <div style=${{ padding: "0 10px 10px" }}>
          <input
            className="film-app__search"
            type="search"
            placeholder="Search game or opponent"
            value=${query}
            onChange=${(event) => setQuery(event.target.value)}
          />
        </div>
        <div className="film-app__games-list">
          ${gamesLoading
            ? html`<div className="film-app__status">Loading games...</div>`
            : filteredGames.length === 0
              ? html`<div className="film-app__status">No matching games.</div>`
              : filteredGames.map((item) => html`
                  <button
                    key=${item.id}
                    className=${`film-app__game-row ${selectedGameId === item.id ? "is-active" : ""}`}
                    onClick=${() => setSelectedGameId(item.id)}
                  >
                    <div className="film-app__game-title">${item.title || "Untitled game"}</div>
                    <div className="film-app__meta">vs ${item.opponent || "Unknown opponent"}</div>
                    <div className="film-app__meta">
                      ${item.game_date || "No date"} ${scoreLabel(item) ? `| ${scoreLabel(item)}` : ""}
                    </div>
                  </button>
                `)}
        </div>
      </aside>

      <main className="film-app__content">
        ${error ? html`<div className="film-app__status is-error">${error}</div>` : null}

        ${gameLoading
          ? html`<section className="film-app__panel"><div className="film-app__status">Loading game...</div></section>`
          : game
            ? html`
                <section className="film-app__panel">
                  <div className="film-app__game-summary">
                    <div className="film-app__summary-title">${game.title}</div>
                    <div className="film-app__summary-meta">
                      <span>vs ${game.opponent}</span>
                      ${game.game_date ? html`<span>${game.game_date}</span>` : null}
                      ${scoreLabel(game) ? html`<span>Score ${scoreLabel(game)}</span>` : null}
                      ${game.tournament ? html`<span>${game.tournament.name}</span>` : null}
                    </div>
                  </div>
                  ${youtubeUrl
                    ? html`<iframe
                        key=${`${game.id}-${videoVersion}`}
                        className="film-app__video"
                        src=${youtubeUrl}
                        title="Game video"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowFullScreen
                      ></iframe>`
                    : html`<div className="film-app__status">No video configured for this game.</div>`}
                </section>

                <section className="film-app__grid">
                  <section className="film-app__panel">
                    <div className="film-app__panel-header">
                      <div className="film-app__panel-title">Points</div>
                      <a className="film-app__inline-btn" href=${`/film/games/${game.id}`}>Legacy View</a>
                    </div>
                    <div className="film-app__scroll">
                      <table className="film-app__table">
                        <thead>
                          <tr>
                            <th>#</th>
                            <th>O/D</th>
                            <th>Result</th>
                            <th>Time</th>
                            <th>Pull</th>
                            <th>Defense</th>
                            <th>Offense Faced</th>
                          </tr>
                        </thead>
                        <tbody>
                          ${(game.points || []).map((point) => html`
                            <tr key=${point.id}>
                              <td>${point.point_index}</td>
                              <td>${point.tron_o ? "O" : "D"}</td>
                              <td>${point.tron_point ? "Tron" : "Opponent"}</td>
                              <td>
                                ${point.timestamp_start === null || point.timestamp_start === undefined
                                  ? "-"
                                  : html`
                                      <button onClick=${() => jumpToTimestamp(point.timestamp_start)}>
                                        ${formatClock(point.timestamp_start)}
                                      </button>
                                    `}
                              </td>
                              <td>${point.pull_play || "-"}</td>
                              <td>${point.defense_type || "-"}</td>
                              <td>${point.offense_faced || "-"}</td>
                            </tr>
                          `)}
                        </tbody>
                      </table>
                    </div>
                  </section>

                  <section className="film-app__panel">
                    <div className="film-app__panel-header">
                      <div>
                        <div className="film-app__panel-title">Comments</div>
                        <div className="film-app__panel-subtitle">Threaded, API-backed</div>
                      </div>
                    </div>

                    <form className="film-app__comment-form" onSubmit=${submitComment}>
                      <textarea
                        rows="3"
                        placeholder="Add a comment"
                        value=${commentText}
                        onChange=${(event) => setCommentText(event.target.value)}
                      ></textarea>
                      <div className="film-app__comment-form-row">
                        <select
                          value=${commentType}
                          onChange=${(event) => setCommentType(event.target.value)}
                        >
                          <option value="Comment">Comment</option>
                          <option value="Question">Question</option>
                          <option value="Highlight">Highlight</option>
                          <option value="Event">Event</option>
                        </select>
                        <input
                          type="number"
                          min="0"
                          step="1"
                          placeholder="Sec"
                          value=${commentTimestamp}
                          onChange=${(event) => setCommentTimestamp(event.target.value)}
                        />
                        <button disabled=${commentBusy} type="submit">
                          ${commentBusy ? "Saving..." : "Post"}
                        </button>
                      </div>
                    </form>

                    <div className="film-app__comments film-app__scroll">
                      ${(game.comments || []).length === 0
                        ? html`<div className="film-app__status">No comments yet.</div>`
                        : (game.comments || []).map((comment) => html`
                            <article key=${comment.id} className="film-app__comment">
                              <div className="film-app__comment-meta">
                                <span className="film-app__badge">${comment.comment_type}</span>
                                <span>${comment.author_name}</span>
                                <span>${comment.created_at || ""}</span>
                                ${comment.timestamp !== null && comment.timestamp !== undefined
                                  ? html`
                                      <button onClick=${() => jumpToTimestamp(comment.timestamp)}>
                                        @ ${formatClock(comment.timestamp)}
                                      </button>
                                    `
                                  : null}
                              </div>
                              <div className="film-app__comment-body">${comment.content}</div>
                              ${canManageComment(comment, bootstrap.currentUser)
                                ? html`
                                    <div className="film-app__comment-actions">
                                      <button onClick=${() => editComment(comment)}>Edit</button>
                                      <button onClick=${() => deleteComment(comment.id)}>Delete</button>
                                    </div>
                                  `
                                : null}
                              ${(comment.replies || []).map((reply) => html`
                                <div key=${reply.id} className="film-app__reply">
                                  <div className="film-app__comment-meta">
                                    <span>${reply.author_name}</span>
                                    <span>${reply.created_at || ""}</span>
                                  </div>
                                  <div className="film-app__comment-body">${reply.content}</div>
                                  ${canManageComment(reply, bootstrap.currentUser)
                                    ? html`
                                        <div className="film-app__comment-actions">
                                          <button onClick=${() => editComment(reply)}>Edit</button>
                                          <button onClick=${() => deleteComment(reply.id)}>Delete</button>
                                        </div>
                                      `
                                    : null}
                                </div>
                              `)}
                            </article>
                          `)}
                    </div>
                  </section>
                </section>
              `
            : html`<section className="film-app__panel"><div className="film-app__status">Pick a game to start.</div></section>`}
      </main>
    </div>
  `;
}

const container = document.getElementById("film-room-app-root");
if (container) {
  createRoot(container).render(html`<${FilmRoomApp} />`);
}
