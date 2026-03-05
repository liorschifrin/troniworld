import { html, useMemo } from "../deps.js";
import { formatClock } from "../utils/time.js";

function computeRunningScores(points) {
  const tron = [];
  const opp = [];
  let tronScore = 0;
  let oppScore = 0;
  for (const point of points) {
    if (point.tron_point) {
      tronScore += 1;
    } else {
      oppScore += 1;
    }
    tron.push(tronScore);
    opp.push(oppScore);
  }
  return { tron, opp };
}

export function PlayerSheet({ game, open, onToggle, activePointIndex, onSeekPoint }) {
  const points = game?.points || [];
  const sheet = game?.player_sheet || {};
  const players = sheet.players || game?.roster || [];
  const pointPlayers = sheet.point_players || {};
  const separatorIndex = sheet.separator_index;

  const running = useMemo(() => computeRunningScores(points), [points]);

  if (!points.length) {
    return null;
  }

  function cellClass(point) {
    const classes = [];
    classes.push(point.tron_o ? "offense" : "defense");
    if (point.point_index === activePointIndex) {
      classes.push("column-active");
    }
    if (point.timestamp_start !== null && point.timestamp_start !== undefined) {
      classes.push("is-clickable");
    }
    return classes.join(" ");
  }

  function cellButton(point, content) {
    if (point.timestamp_start === null || point.timestamp_start === undefined) {
      return content;
    }
    return html`
      <button
        className="film-app__sheet-seek"
        title=${`Jump to ${formatClock(point.timestamp_start)}`}
        onClick=${() => onSeekPoint(point.timestamp_start)}
      >
        ${content}
      </button>
    `;
  }

  return html`
    <section className="film-app__panel film-app__player-sheet">
      <button className="film-app__sheet-toggle" onClick=${onToggle}>
        <span>📋 Player Sheet</span>
        <span>${open ? "▲" : "▼"}</span>
      </button>

      ${open
        ? html`
            <div className="film-app__sheet-scroll">
              <table className="film-app__sheet-table">
                <thead>
                  <tr>
                    <th>O/D</th>
                    ${points.map(
                      (point) => html`
                        <th key=${point.id} className=${cellClass(point)}>
                          ${cellButton(point, point.point_index)}
                        </th>
                      `,
                    )}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="row-label">O/D</td>
                    ${points.map(
                      (point) => html`
                        <td key=${`od-${point.id}`} className=${cellClass(point)}>
                          ${cellButton(point, point.tron_o ? "O" : "X")}
                        </td>
                      `,
                    )}
                  </tr>
                  <tr>
                    <td className="row-label">TRON</td>
                    ${points.map(
                      (point, idx) => html`
                        <td key=${`tron-${point.id}`} className=${cellClass(point)}>
                          ${point.tron_point ? cellButton(point, running.tron[idx]) : ""}
                        </td>
                      `,
                    )}
                  </tr>
                  <tr>
                    <td className="row-label">Enemy</td>
                    ${points.map(
                      (point, idx) => html`
                        <td key=${`opp-${point.id}`} className=${cellClass(point)}>
                          ${!point.tron_point ? cellButton(point, running.opp[idx]) : ""}
                        </td>
                      `,
                    )}
                  </tr>
                  <tr>
                    <td colSpan=${points.length + 1} className="film-app__sheet-spacer"></td>
                  </tr>

                  ${players.map((playerName, playerIdx) => html`
                    <tr key=${`player-${playerName}`}>
                      <td className="player-name">${playerName}</td>
                      ${points.map((point, idx) => {
                        const names = pointPlayers[String(point.point_index)] || [];
                        const total = points
                          .slice(0, idx + 1)
                          .filter((p) => (pointPlayers[String(p.point_index)] || []).includes(playerName)).length;

                        return html`
                          <td key=${`player-${playerName}-${point.id}`} className=${cellClass(point)}>
                            ${names.includes(playerName) ? cellButton(point, total) : ""}
                          </td>
                        `;
                      })}
                    </tr>
                    ${separatorIndex && playerIdx + 1 === separatorIndex
                      ? html`
                          <tr key=${`spacer-${playerName}`}>
                            <td colSpan=${points.length + 1} className="film-app__sheet-spacer"></td>
                          </tr>
                        `
                      : null}
                  `)}
                </tbody>
              </table>
            </div>
          `
        : null}
    </section>
  `;
}
