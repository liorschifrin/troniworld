import { html } from "../deps.js";
import { scoreLabel } from "../utils/time.js";

export function GamesDrawer({
  open,
  onClose,
  games,
  loading,
  query,
  onQueryChange,
  selectedGameId,
  onSelectGame,
}) {
  return html`
    <div className=${`film-app__drawer-overlay ${open ? "is-open" : ""}`} onClick=${onClose}></div>
    <aside className=${`film-app__drawer ${open ? "is-open" : ""}`}>
      <div className="film-app__drawer-header">
        <div>
          <h2 className="film-app__drawer-title">Games</h2>
          <p className="film-app__drawer-subtitle">Switch game without losing screen space</p>
        </div>
        <button className="film-app__ghost-btn" onClick=${onClose}>Close</button>
      </div>

      <div className="film-app__drawer-search-wrap">
        <input
          className="film-app__search"
          type="search"
          placeholder="Search game or opponent"
          value=${query}
          onChange=${(event) => onQueryChange(event.target.value)}
        />
      </div>

      <div className="film-app__drawer-body">
        ${loading
          ? html`<div className="film-app__status">Loading games...</div>`
          : games.length === 0
            ? html`<div className="film-app__status">No matching games.</div>`
            : games.map(
                (game) => html`
                  <button
                    key=${game.id}
                    className=${`film-app__game-row ${selectedGameId === game.id ? "is-active" : ""}`}
                    onClick=${() => onSelectGame(game.id)}
                  >
                    <div className="film-app__game-title">${game.title || "Untitled game"}</div>
                    <div className="film-app__meta">vs ${game.opponent || "Unknown opponent"}</div>
                    <div className="film-app__meta">
                      ${game.game_date || "No date"}
                      ${scoreLabel(game) ? ` | ${scoreLabel(game)}` : ""}
                    </div>
                  </button>
                `,
              )}
      </div>
    </aside>
  `;
}
