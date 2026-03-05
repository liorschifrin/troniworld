import { html } from "../deps.js";
import { formatClock, scoreLabel } from "../utils/time.js";

export function VideoPane({
  game,
  viewer,
  hostRef,
  isPlayerReady,
  currentTime,
  duration,
  score,
  onFieldPlayers,
  togglePlayPause,
  seekRelative,
  fullscreen,
}) {
  return html`
    <section className="film-app__video-pane film-app__panel">
      <div className="film-app__panel-header">
        <div>
          <h2 className="film-app__panel-title">${game.title}</h2>
          <p className="film-app__panel-subtitle">
            vs ${game.opponent}
            ${game.game_date ? ` | ${game.game_date}` : ""}
            ${scoreLabel(game) ? ` | Final ${scoreLabel(game)}` : ""}
          </p>
        </div>
        <a className="film-app__inline-btn" href=${`/film/games/${game.id}`}>Legacy View</a>
      </div>

      <div className=${`film-app__on-field ${onFieldPlayers.length === 0 ? "is-empty" : ""}`}>
        <span className="film-app__on-field-label">On Field:</span>
        <div className="film-app__on-field-list">
          ${onFieldPlayers.length === 0
            ? html`<span className="film-app__player-chip is-empty">Waiting for first point...</span>`
            : onFieldPlayers.map((name) => html`
                <span
                  key=${name}
                  className=${`film-app__player-chip ${
                    viewer.player_name && viewer.player_name === name ? "is-self" : ""
                  }`}
                >
                  ${name}
                </span>
              `)}
        </div>
      </div>

      <div className="film-app__player-wrap">
        ${game.youtube_id
          ? html`<div className="film-app__player-host" ref=${hostRef}></div>`
          : html`
              <div className="film-app__player-placeholder">
                <p>No video configured for this game yet.</p>
              </div>
            `}

        <div className="film-app__scoreboard">
          <span className="film-app__scoreboard-label">Score</span>
          <span className="film-app__scoreboard-tron">${score.tron}</span>
          <span className="film-app__scoreboard-sep">-</span>
          <span className="film-app__scoreboard-opp">${score.opp}</span>
        </div>

        <div className="film-app__clock">
          ${formatClock(currentTime)} / ${formatClock(duration)}
        </div>
      </div>

      <div className="film-app__video-controls">
        <button onClick=${togglePlayPause} disabled=${!isPlayerReady}>Play/Pause</button>
        <button onClick=${() => seekRelative(-10)} disabled=${!isPlayerReady}>-10s</button>
        <button onClick=${() => seekRelative(10)} disabled=${!isPlayerReady}>+10s</button>
        <button onClick=${fullscreen} disabled=${!isPlayerReady}>Fullscreen</button>
      </div>
    </section>
  `;
}
