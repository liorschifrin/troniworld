// Pure scoreboard arithmetic for the game player page (no DOM, no page state).
// Loaded as a classic script before the inline player script; the functions are globals.

function getCurrentScore(points) {
  let tron = 0, opp = 0;
  for (const point of points) {
    if (point.tron_point) tron++;
    else opp++;
  }
  return { tron, opp };
}

function getTimestampValue(point) {
  if (!point) return null;
  const raw = point.timestamp_start;
  if (raw === null || raw === undefined || raw === '') return null;
  const numeric = Number(raw);
  return Number.isFinite(numeric) ? numeric : null;
}

function getCompletedPoints(points, currentTime, duration) {
  const timestampedPoints = points
    .map((point, index) => ({ point, index, ts: getTimestampValue(point) }))
    .filter(entry => entry.ts !== null)
    .sort((a, b) => a.ts - b.ts || a.index - b.index);

  if (timestampedPoints.length === 0) return [];

  // Find the current point: the last timestamped point whose timestamp has been reached.
  let currentEntry = null;
  for (const entry of timestampedPoints) {
    if (currentTime >= entry.ts) currentEntry = entry;
  }

  if (!currentEntry) return [];

  // When the video is ending, count every point (including unfilmed trailing ones)
  // so the scoreboard shows the true final score.
  const isVideoEnding = Number.isFinite(duration) && duration > 0 && currentTime >= (duration - 0.25);
  if (isVideoEnding) return points;

  // Otherwise: all points before the current point (by original array index) are
  // completed. The current point is still in progress, so exclude it.
  return points.slice(0, currentEntry.index);
}
