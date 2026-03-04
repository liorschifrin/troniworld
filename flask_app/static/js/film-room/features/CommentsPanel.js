import { html, useEffect, useMemo, useRef, useState } from "../deps.js";
import { ensureVisible, renderTextWithMentions } from "../utils/dom.js";
import { formatClock, relativeTime } from "../utils/time.js";

function canManage(comment, viewer) {
  if (!viewer || !viewer.username) {
    return false;
  }
  return Boolean(viewer.is_admin) || viewer.username === comment.author_name;
}

function totalCommentCount(comments) {
  return (comments || []).reduce((acc, comment) => {
    return acc + 1 + ((comment.replies || []).length || 0);
  }, 0);
}

// ─── Mention-aware textarea ──────────────────────────────────────────────────

function MentionTextarea({ value, onChange, mentionables, rows, placeholder }) {
  const [mention, setMention] = useState({
    active: false,
    query: "",
    selIdx: 0,
    triggerStart: -1,
  });
  const textareaRef = useRef(null);

  const suggestions = useMemo(() => {
    if (!mention.active || !mentionables || !mentionables.length) return [];
    const q = mention.query.toLowerCase();
    return mentionables.filter((name) => name.toLowerCase().includes(q));
  }, [mention.active, mention.query, mentionables]);

  function detectMention(val, pos) {
    const before = val.slice(0, pos);
    const match = before.match(/@([A-Za-z0-9_-]*)$/);
    if (match) {
      setMention({
        active: true,
        query: match[1],
        selIdx: 0,
        triggerStart: pos - match[0].length,
      });
    } else {
      setMention({ active: false, query: "", selIdx: 0, triggerStart: -1 });
    }
  }

  function handleInput(e) {
    const ta = e.target;
    onChange(ta.value);
    detectMention(ta.value, ta.selectionStart);
  }

  function handleKeyDown(e) {
    if (!mention.active || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setMention((prev) => ({
        ...prev,
        selIdx: Math.min(prev.selIdx + 1, suggestions.length - 1),
      }));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setMention((prev) => ({ ...prev, selIdx: Math.max(prev.selIdx - 1, 0) }));
    } else if (e.key === "Enter" || e.key === "Tab") {
      const pick = suggestions[mention.selIdx] || suggestions[0];
      if (pick) {
        e.preventDefault();
        commitMention(pick);
      }
    } else if (e.key === "Escape") {
      setMention({ active: false, query: "", selIdx: 0, triggerStart: -1 });
    }
  }

  function commitMention(name) {
    const ta = textareaRef.current;
    if (!ta) return;
    const pos = ta.selectionStart;
    const val = ta.value;
    const before = val.slice(0, mention.triggerStart);
    const after = val.slice(pos);
    const newVal = `${before}@${name} ${after}`;
    onChange(newVal);
    setMention({ active: false, query: "", selIdx: 0, triggerStart: -1 });
    const newPos = mention.triggerStart + name.length + 2;
    requestAnimationFrame(() => {
      if (ta) {
        ta.focus();
        ta.setSelectionRange(newPos, newPos);
      }
    });
  }

  function handleBlur() {
    setTimeout(
      () => setMention((prev) => ({ ...prev, active: false })),
      150
    );
  }

  return html`
    <div style=${{ position: "relative" }}>
      <textarea
        ref=${textareaRef}
        rows=${rows || 3}
        placeholder=${placeholder || ""}
        value=${value}
        onInput=${handleInput}
        onKeyDown=${handleKeyDown}
        onBlur=${handleBlur}
      ></textarea>
      ${mention.active && suggestions.length > 0
        ? html`
            <div className="film-app__mention-dropdown">
              ${suggestions.map(
                (name, idx) => html`
                  <div
                    key=${name}
                    className=${`film-app__mention-dropdown-item ${
                      idx === mention.selIdx ? "is-selected" : ""
                    }`}
                    onMouseDown=${(e) => {
                      e.preventDefault();
                      commitMention(name);
                    }}
                  >
                    <span className="film-app__mention-dropdown-at">@</span>${name}
                  </div>
                `
              )}
            </div>
          `
        : null}
    </div>
  `;
}

// ─── CommentsPanel ────────────────────────────────────────────────────────────

export function CommentsPanel({
  comments,
  viewer,
  mentionables,
  activeCommentId,
  onSeek,
  onCreateComment,
  onUpdateComment,
  onDeleteComment,
  getCurrentVideoTime,
}) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState({});
  const [replyingToId, setReplyingToId] = useState(null);
  const [replyDraft, setReplyDraft] = useState("");
  const [editingCommentId, setEditingCommentId] = useState(null);
  const [editingDraft, setEditingDraft] = useState("");

  const listRef = useRef(null);
  const commentRefs = useRef({});

  const mentionList = useMemo(() => mentionables || [], [mentionables]);

  useEffect(() => {
    if (!activeCommentId) return;
    const node = commentRefs.current[String(activeCommentId)];
    ensureVisible(listRef.current, node);
  }, [activeCommentId]);

  async function submitComment(event) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || busy) return;
    setBusy(true);
    try {
      const currentVideoTime = getCurrentVideoTime();
      await onCreateComment({
        content,
        parent_id: null,
        timestamp: Number.isFinite(currentVideoTime) ? Math.floor(currentVideoTime) : null,
      });
      setDraft("");
    } finally {
      setBusy(false);
    }
  }

  async function submitReply(parentId) {
    const content = replyDraft.trim();
    if (!content || busy) return;
    setBusy(true);
    try {
      const currentVideoTime = getCurrentVideoTime();
      await onCreateComment({
        content,
        parent_id: parentId,
        timestamp: Number.isFinite(currentVideoTime) ? Math.floor(currentVideoTime) : null,
      });
      setReplyDraft("");
      setReplyingToId(null);
      setExpanded((prev) => ({ ...prev, [String(parentId)]: true }));
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit(commentId) {
    const content = editingDraft.trim();
    if (!content || busy) return;
    setBusy(true);
    try {
      await onUpdateComment(commentId, content);
      setEditingCommentId(null);
      setEditingDraft("");
    } finally {
      setBusy(false);
    }
  }

  function openEdit(comment) {
    setEditingCommentId(comment.id);
    setEditingDraft(comment.content || "");
  }

  function renderComment(comment, isReply = false) {
    const isExpanded = expanded[String(comment.id)] || false;
    const replies = comment.replies || [];
    const ownOrAdmin = canManage(comment, viewer);
    const isEditing = editingCommentId === comment.id;

    return html`
      <article
        key=${comment.id}
        ref=${(node) => {
          commentRefs.current[String(comment.id)] = node;
        }}
        className=${`film-app__comment ${isReply ? "is-reply" : ""} ${
          activeCommentId === comment.id ? "is-active" : ""
        }`}
      >
        <div className="film-app__comment-meta">
          <span className="film-app__comment-author">${comment.author_name}</span>
          <span>${relativeTime(comment.created_at_iso, comment.created_at || "")}</span>
          ${comment.timestamp !== null && comment.timestamp !== undefined
            ? html`
                <button className="film-app__tiny-btn" onClick=${() => onSeek(comment.timestamp)}>
                  @ ${formatClock(comment.timestamp)}
                </button>
              `
            : null}
        </div>

        ${isEditing
          ? html`
              <div className="film-app__comment-edit">
                <${MentionTextarea}
                  value=${editingDraft}
                  onChange=${setEditingDraft}
                  mentionables=${mentionList}
                  rows=${3}
                  placeholder="Edit comment..."
                />
                <div className="film-app__comment-actions">
                  <button className="film-app__tiny-btn" disabled=${busy} onClick=${() => saveEdit(comment.id)}>Save</button>
                  <button className="film-app__tiny-btn" onClick=${() => setEditingCommentId(null)}>Cancel</button>
                </div>
              </div>
            `
          : html`
              <div
                className="film-app__comment-body"
                dangerouslySetInnerHTML=${{
                  __html: renderTextWithMentions(
                    comment.content || "",
                    mentionList,
                    viewer?.username || null
                  ),
                }}
              ></div>
            `}

        <div className="film-app__comment-actions">
          ${!isReply
            ? html`
                <button
                  className="film-app__tiny-btn"
                  onClick=${() => {
                    setReplyingToId(comment.id);
                    setExpanded((prev) => ({ ...prev, [String(comment.id)]: true }));
                  }}
                >
                  Reply
                </button>
              `
            : null}
          ${replies.length
            ? html`
                <button
                  className="film-app__tiny-btn"
                  onClick=${() =>
                    setExpanded((prev) => ({
                      ...prev,
                      [String(comment.id)]: !isExpanded,
                    }))}
                >
                  ${isExpanded ? "Hide" : "Show"} ${replies.length} repl${replies.length === 1 ? "y" : "ies"}
                </button>
              `
            : null}
          ${ownOrAdmin
            ? html`
                <button className="film-app__tiny-btn" onClick=${() => openEdit(comment)}>Edit</button>
                <button className="film-app__tiny-btn warn" onClick=${() => onDeleteComment(comment.id)}>Delete</button>
              `
            : null}
        </div>

        ${replyingToId === comment.id
          ? html`
              <div className="film-app__reply-compose">
                <${MentionTextarea}
                  value=${replyDraft}
                  onChange=${setReplyDraft}
                  mentionables=${mentionList}
                  rows=${2}
                  placeholder="Write a reply... type @ to mention"
                />
                <div className="film-app__comment-actions">
                  <button className="film-app__tiny-btn" disabled=${busy} onClick=${() => submitReply(comment.id)}>Reply</button>
                  <button
                    className="film-app__tiny-btn"
                    onClick=${() => {
                      setReplyingToId(null);
                      setReplyDraft("");
                    }}
                  >Cancel</button>
                </div>
              </div>
            `
          : null}

        ${replies.length && isExpanded
          ? html`
              <div className="film-app__reply-list">
                ${replies.map((reply) => renderComment(reply, true))}
              </div>
            `
          : null}
      </article>
    `;
  }

  return html`
    <section className="film-app__panel film-app__comments-panel">
      <div className="film-app__panel-header">
        <h2 className="film-app__panel-title">Comments</h2>
        <span className="film-app__count-badge">${totalCommentCount(comments)}</span>
      </div>

      <form className="film-app__comment-compose" onSubmit=${submitComment}>
        <${MentionTextarea}
          value=${draft}
          onChange=${setDraft}
          mentionables=${mentionList}
          rows=${3}
          placeholder="Share your thoughts... type @ to mention someone"
        />
        <div className="film-app__comment-actions">
          <button disabled=${busy} type="submit">${busy ? "Posting..." : "Post Comment"}</button>
        </div>
      </form>

      <div className="film-app__comments-list" ref=${listRef}>
        ${(comments || []).length === 0
          ? html`<div className="film-app__status">No comments yet. Be the first to post.</div>`
          : (comments || []).map((comment) => renderComment(comment, false))}
      </div>
    </section>
  `;
}
