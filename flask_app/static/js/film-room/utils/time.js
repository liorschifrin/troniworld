export function toInt(value) {
  const num = Number.parseInt(value, 10);
  return Number.isFinite(num) ? num : null;
}

export function formatClock(seconds) {
  const total = toInt(seconds);
  if (total === null || total < 0) {
    return "";
  }
  const mins = Math.floor(total / 60);
  const secs = String(total % 60).padStart(2, "0");
  return `${mins}:${secs}`;
}

export function scoreLabel(game) {
  if (!game) {
    return "";
  }
  if (game.final_score_tron === null || game.final_score_tron === undefined) {
    return "";
  }
  if (game.final_score_opponent === null || game.final_score_opponent === undefined) {
    return "";
  }
  return `${game.final_score_tron}-${game.final_score_opponent}`;
}

export function relativeTime(isoDate, fallback = "") {
  if (!isoDate) {
    return fallback;
  }

  const dt = new Date(isoDate);
  if (Number.isNaN(dt.getTime())) {
    return fallback || isoDate;
  }

  const diffSec = Math.floor((Date.now() - dt.getTime()) / 1000);
  if (diffSec < 60) {
    return "just now";
  }
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) {
    return `${diffMin}m ago`;
  }
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) {
    return `${diffHr}h ago`;
  }
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) {
    return `${diffDay}d ago`;
  }
  return dt.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function safeTimestamp(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? Math.max(0, Math.floor(numeric)) : null;
}
