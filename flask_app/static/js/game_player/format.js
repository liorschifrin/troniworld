// Pure text and time helpers for the game player page (no DOM, no page state).
// Loaded as a classic script before the inline player script; the functions are globals.

function relativeTime(dateStr) {
  if (!dateStr) return '';
  // Server sends e.g. "Feb 27, 2026 03:14 PM" — parse it
  const d = new Date(dateStr);
  if (isNaN(d)) return dateStr;
  const diffMs  = Date.now() - d.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr  = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr  / 24);
  if (diffSec < 60)  return 'just now';
  if (diffMin < 60)  return `${diffMin}m ago`;
  if (diffHr  < 24)  return `${diffHr}h ago`;
  if (diffDay <  7)  return `${diffDay}d ago`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatTimestamp(seconds) {
  if (!seconds && seconds !== 0) return null;
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function extractVideoId(input) {
  input = input.trim();
  // Already just an ID (11 chars, no slashes)
  if (/^[a-zA-Z0-9_-]{11}$/.test(input)) return input;
  // youtu.be/ID
  let m = input.match(/youtu\.be\/([a-zA-Z0-9_-]{11})/);
  if (m) return m[1];
  // youtube.com/watch?v=ID
  m = input.match(/[?&]v=([a-zA-Z0-9_-]{11})/);
  if (m) return m[1];
  // youtube.com/embed/ID
  m = input.match(/embed\/([a-zA-Z0-9_-]{11})/);
  if (m) return m[1];
  return null;
}

function formatTime(seconds) {
  if (!seconds || seconds < 0) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${String(secs).padStart(2, '0')}`;
}
