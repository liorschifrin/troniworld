import { html, useEffect, useMemo, useRef, useState } from "../deps.js";
import { ensureVisible } from "../utils/dom.js";
import { formatClock } from "../utils/time.js";

const FIELD_LABELS = {
  pull_play: "Pull Play",
  defense_type: "Defensive Style",
  offense_faced: "Offense Faced",
};

function availableOptions(pointFieldOptions, fieldName) {
  return (pointFieldOptions && pointFieldOptions[fieldName]) || [];
}

export function PointTimeline({
  points,
  pointFieldOptions,
  viewer,
  activePointIndex,
  onSeekPoint,
  onUpdatePoint,
}) {
  const scrollRef = useRef(null);
  const pointRefs = useRef({});
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);

  const pointsByIndex = useMemo(() => {
    const out = {};
    for (const point of points || []) {
      out[point.point_index] = point;
    }
    return out;
  }, [points]);

  useEffect(() => {
    if (!activePointIndex) {
      return;
    }
    const target = pointRefs.current[String(activePointIndex)];
    ensureVisible(scrollRef.current, target);
  }, [activePointIndex]);

  if (!points || points.length === 0) {
    return null;
  }

  function startEdit(point, fieldName) {
    if (!viewer.is_admin) {
      return;
    }
    setEditing({ pointId: point.id, fieldName });
    setDraft(point[fieldName] || "");
  }

  async function saveEdit(point) {
    if (!editing) {
      return;
    }
    setSaving(true);
    try {
      await onUpdatePoint(point.id, { [editing.fieldName]: draft.trim() || null });
      setEditing(null);
      setDraft("");
    } finally {
      setSaving(false);
    }
  }

  async function setTimestamp(point) {
    if (!viewer.is_admin) {
      return;
    }
    const raw = window.prompt("Set timestamp in seconds", point.timestamp_start ?? "");
    if (raw === null) {
      return;
    }
    const numeric = Number.parseInt(raw, 10);
    if (!Number.isFinite(numeric) || numeric < 0) {
      window.alert("Timestamp must be a positive number.");
      return;
    }
    await onUpdatePoint(point.id, { timestamp_start: numeric });
  }

  async function clearTimestamp(point) {
    if (!viewer.is_admin) {
      return;
    }
    await onUpdatePoint(point.id, { timestamp_start: null });
  }

  function fieldValue(point, fieldName) {
    const value = point[fieldName];
    return value || (viewer.is_admin ? "Add..." : "-");
  }

  return html`
    <section className="film-app__panel">
      <div className="film-app__panel-header">
        <h2 className="film-app__panel-title">Points</h2>
        <p className="film-app__panel-subtitle">Timeline synced to video</p>
      </div>
      <div className="film-app__point-scroll" ref=${scrollRef}>
        ${(points || []).map((point) => {
          const pointIsActive = activePointIndex === point.point_index;
          const isMyPoint =
            viewer.player_name && Array.isArray(point.players) && point.players.includes(viewer.player_name);

          return html`
            <article
              key=${point.id}
              ref=${(node) => {
                pointRefs.current[String(point.point_index)] = node;
              }}
              className=${`film-app__point-card ${pointIsActive ? "is-active" : ""} ${
                isMyPoint ? "is-my-point" : ""
              }`}
            >
              <div className="film-app__point-head">
                <span className="film-app__point-number">P${point.point_index}</span>
                <span className=${`film-app__point-od ${point.tron_o ? "offense" : "defense"}`}>
                  ${point.tron_o ? "O" : "D"}
                </span>
                <span className=${`film-app__point-result ${point.tron_point ? "tron" : "opp"}`}>
                  ${point.tron_point ? "Tron" : "Opponent"}
                </span>
                ${isMyPoint ? html`<span className="film-app__point-you">YOU</span>` : null}
              </div>

              <div className="film-app__point-time-wrap">
                ${point.timestamp_start === null || point.timestamp_start === undefined
                  ? html`<span className="film-app__point-time film-app__point-time-empty">No timestamp</span>`
                  : html`
                      <button
                        className="film-app__point-time"
                        onClick=${() => onSeekPoint(point.timestamp_start)}
                      >
                        ${formatClock(point.timestamp_start)}
                      </button>
                    `}
                ${viewer.is_admin
                  ? html`
                      ${point.timestamp_start === null || point.timestamp_start === undefined
                        ? html`<button className="film-app__tiny-btn" onClick=${() => setTimestamp(point)}>+ Time</button>`
                        : html`
                            <button className="film-app__tiny-btn" onClick=${() => setTimestamp(point)}>Edit</button>
                            <button className="film-app__tiny-btn warn" onClick=${() => clearTimestamp(point)}>Clear</button>
                          `}
                    `
                  : null}
              </div>

              <div className="film-app__point-fields">
                ${Object.keys(FIELD_LABELS).map((fieldName) => {
                  const isEditing = editing && editing.pointId === point.id && editing.fieldName === fieldName;
                  const options = availableOptions(pointFieldOptions, fieldName);

                  return html`
                    <div key=${`${point.id}-${fieldName}`} className="film-app__point-field">
                      <span className="film-app__point-field-label">${FIELD_LABELS[fieldName]}</span>

                      ${isEditing
                        ? html`
                            <div className="film-app__point-edit-row">
                              <input
                                className="film-app__point-input"
                                value=${draft}
                                list=${`film-app-options-${fieldName}`}
                                onInput=${(event) => setDraft(event.target.value)}
                              />
                              <button
                                className="film-app__tiny-btn"
                                disabled=${saving}
                                onClick=${() => saveEdit(point)}
                              >
                                Save
                              </button>
                              <button className="film-app__tiny-btn" onClick=${() => setEditing(null)}>Cancel</button>
                            </div>
                          `
                        : html`
                            <button
                              className=${`film-app__point-value ${!point[fieldName] ? "is-empty" : ""}`}
                              onClick=${() => startEdit(point, fieldName)}
                              disabled=${!viewer.is_admin}
                            >
                              ${fieldValue(point, fieldName)}
                            </button>
                          `}

                      <datalist id=${`film-app-options-${fieldName}`}>
                        ${options.map((value) => html`<option key=${value} value=${value}></option>`)}
                      </datalist>
                    </div>
                  `;
                })}
              </div>
            </article>
          `;
        })}
      </div>
    </section>
  `;
}
