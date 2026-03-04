export function escapeHtml(value) {
  const text = value == null ? "" : String(value);
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function renderTextWithMentions(rawText, mentionables = [], currentUsername = null, opponentName = null) {
  const escaped = escapeHtml(rawText);
  if (!escaped) {
    return "";
  }

  const mentionSet   = new Set((mentionables || []).map((item) => String(item).toLowerCase()));
  const selfLower    = currentUsername ? currentUsername.toLowerCase() : null;
  const enemyLower   = opponentName   ? opponentName.toLowerCase()    : null;

  // First, handle @[username] format (from contenteditable mentions)
  let withBracketMentions = escaped.replace(/@\[([^\]]+)\]/g, (full, name) => {
    if (!mentionSet.has(name.toLowerCase())) {
      return full;
    }
    const nameLower = name.toLowerCase();
    let cls = "film-app__mention";
    if (selfLower && nameLower === selfLower) {
      cls += " is-self";
    } else if (enemyLower && nameLower === enemyLower) {
      cls += " is-enemy";
    }
    return `<span class="${cls}">@${name}</span>`;
  });

  // Then, handle plain @username format (for backwards compatibility)
  const withMentions = withBracketMentions.replace(/@([A-Za-z0-9_-]+)/g, (full, name) => {
    if (!mentionSet.has(name.toLowerCase())) {
      return full;
    }
    const nameLower = name.toLowerCase();
    let cls = "film-app__mention";
    if (selfLower && nameLower === selfLower) {
      cls += " is-self";
    } else if (enemyLower && nameLower === enemyLower) {
      cls += " is-enemy";
    }
    return `<span class="${cls}">@${name}</span>`;
  });

  return withMentions.replace(/\n/g, "<br>");
}

function isOutsideView(container, target) {
  const cRect = container.getBoundingClientRect();
  const tRect = target.getBoundingClientRect();
  return tRect.top < cRect.top || tRect.bottom > cRect.bottom;
}

export function ensureVisible(container, target) {
  if (!container || !target) {
    return;
  }
  if (isOutsideView(container, target)) {
    target.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
  }
}
