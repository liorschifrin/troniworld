export function escapeHtml(value) {
  const text = value == null ? "" : String(value);
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function renderTextWithMentions(rawText, mentionables = []) {
  const escaped = escapeHtml(rawText);
  if (!escaped) {
    return "";
  }

  const mentionSet = new Set((mentionables || []).map((item) => String(item).toLowerCase()));
  const withMentions = escaped.replace(/@([A-Za-z0-9_-]+)/g, (full, name) => {
    if (!mentionSet.has(name.toLowerCase())) {
      return full;
    }
    return `<span class=\"film-app__mention\">@${name}</span>`;
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
