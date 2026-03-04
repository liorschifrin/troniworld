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
    if (!activeCommentId) {
      return;
    }
    const node = commentRefs.current[String(activeCommentId)];
    ensureVisible(listRef.current, node);
  }, [activeCommentId]);

  function appendMention(name, mode = "main") {
    if (!name) {
      return;
    }
    const token = ` @${name}`;
    if (mode === "main") {
      setDraft((prev) => `${prev}${token}`.trimStart());
      return;
    }
    if (mode === "reply") {
      setReplyDraft((prev) => `${prev}${token}`.trimStart());
      return;
    }
    if (mode === "edit") {
      setEditingDraft((prev) => `${prev}${token}`.trimStart());
    }
  }

  async function submitComment(event) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || busy) {
      return;
    }

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
    if (!content || busy) {
      return;
    }

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
    if (!content || busy) {
      return;
    }

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

  function renderMentionButtons(mode) {
    if (!mentionList.length) {
      return null;
    }
    return html`
      <div className="film-app__mention-pills">
        ${mentionList.map((name) => html`
          <button
            key=${`${mode}-${name}`}
            type="button"
            className="film-app__mention-pill"
            onClick=${() => appendMention(name, mode)}
          >
            @${name}
          </button>
        `)}
      </div>
    `;
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
                <textarea
                  rows="3"
                  value=${editingDraft}
                  onInput=${(event) => setEditingDraft(event.target.value)}
                ></textarea>
                ${renderMentionButtons("edit")}
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
                  __html: renderTextWithMentions(comment.content || "", mentionList),
                }}
              ></div>
            `}

        <div className="film-app__comment-actions">
          ${!isReply
            ? html`
                <button className="film-app__tiny-btn" onClick=${() => {
                  setReplyingToId(comment.id);
                  setExpanded((prev) => ({ ...prev, [String(comment.id)]: true }));
                }}>
                  Reply
                </button>
              `
            : null}
          ${replies.length
            ? html`
                <button className="film-app__tiny-btn" onClick=${() => setExpanded((prev) => ({
                  ...prev,
                  [String(comment.id)]: !isExpanded,
                }))}>
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
                <textarea
                  rows="2"
                  placeholder="Write a reply"
                  value=${replyDraft}
                  onInput=${(event) => setReplyDraft(event.target.value)}
                ></textarea>
                ${renderMentionButtons("reply")}
                <div className="film-app__comment-actions">
                  <button className="film-app__tiny-btn" disabled=${busy} onClick=${() => submitReply(comment.id)}>Reply</button>
                  <button className="film-app__tiny-btn" onClick=${() => {
                    setReplyingToId(null);
                    setReplyDraft("");
                  }}>Cancel</button>
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
        <textarea
          rows="3"
          placeholder="Share your thoughts about this game..."
          value=${draft}
          onInput=${(event) => setDraft(event.target.value)}
        ></textarea>
        ${renderMentionButtons("main")}
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
