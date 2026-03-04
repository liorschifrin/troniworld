import { html, useEffect, useMemo, useRef, useState } from "../deps.js";
import { ensureVisible, renderTextWithMentions } from "../utils/dom.js";
import { formatClock, relativeTime } from "../utils/time.js";
import { MentionEditor } from "./MentionEditor.js";

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

// ─── CommentsPanel ────────────────────────────────────────────────────────────

export function CommentsPanel({
  comments,
  viewer,
  mentionables,
  opponentName,
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
    const isReplying = replyingToId === comment.id;

    return html`
      <div
        key=${comment.id}
        ref=${(node) => {
          commentRefs.current[String(comment.id)] = node;
        }}
      >
        <article
          className=${`film-app__comment ${isReply ? "is-reply" : ""} ${
            activeCommentId === comment.id ? "is-active" : ""
          }`}
        >
          <div className="film-app__comment-content">
            ${!isEditing
              ? html`
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
                  <div
                    className="film-app__comment-body"
                    dangerouslySetInnerHTML=${{
                      __html: renderTextWithMentions(
                        comment.content || "",
                        mentionList,
                        viewer?.username || null,
                        opponentName || null
                      ),
                    }}
                  ></div>
                  <div className="film-app__comment-footer">
                    ${!isReply && replies.length === 0
                      ? html`
                          <button
                            className="film-app__tiny-btn-reply"
                            onClick=${() => {
                              setReplyingToId(comment.id);
                              setExpanded((prev) => ({ ...prev, [String(comment.id)]: true }));
                            }}
                          >
                            ↩ Reply
                          </button>
                        `
                      : null}
                    ${replies.length
                      ? html`
                          <button
                            className="film-app__tiny-btn-toggle"
                            onClick=${() =>
                              setExpanded((prev) => ({
                                ...prev,
                                [String(comment.id)]: !isExpanded,
                              }))}
                          >
                            ${isExpanded ? "▲ Hide" : "↩"} ${replies.length} ${replies.length === 1 ? "reply" : "replies"}
                          </button>
                        `
                      : null}
                  </div>
                `
              : html`
                  <${MentionEditor}
                    value=${editingDraft}
                    onChange=${setEditingDraft}
                    mentionables=${mentionList}
                    placeholder="Edit comment..."
                  />
                  <div className="film-app__form-actions">
                    <button className="film-app__action-btn-cancel" onClick=${() => setEditingCommentId(null)}>Cancel</button>
                    <button className="film-app__action-btn-submit" disabled=${busy} onClick=${() => saveEdit(comment.id)}>Save</button>
                  </div>
                `}
          </div>
          ${ownOrAdmin && !isEditing
            ? html`
                <div className="film-app__comment-top-actions">
                  <button className="film-app__tiny-btn-edit" onClick=${() => openEdit(comment)}>✎</button>
                  <button className="film-app__tiny-btn-delete" onClick=${() => onDeleteComment(comment.id)}>🗑</button>
                </div>
              `
            : null}
        </article>

        ${replies.length && isExpanded
          ? html`
              <div className="film-app__thread-replies">
                ${replies.map((reply) => renderComment(reply, true))}
                ${!isReplying && !isReply
                  ? html`
                      <button
                        className="film-app__tiny-btn-reply-inline"
                        onClick=${() => {
                          setReplyingToId(comment.id);
                        }}
                      >
                        ↩ Reply
                      </button>
                    `
                  : null}
              </div>
            `
          : null}

        ${isReplying
          ? html`
              <div className="film-app__reply-compose">
                <${MentionEditor}
                  value=${replyDraft}
                  onChange=${setReplyDraft}
                  mentionables=${mentionList}
                  placeholder="Write a reply... type @ to mention"
                />
                <div className="film-app__form-actions">
                  <button
                    className="film-app__action-btn-cancel"
                    onClick=${() => {
                      setReplyingToId(null);
                      setReplyDraft("");
                    }}
                  >Cancel</button>
                  <button className="film-app__action-btn-submit" disabled=${busy} onClick=${() => submitReply(comment.id)}>Reply</button>
                </div>
              </div>
            `
          : null}
      </div>
    `;
  }

  return html`
    <section className="film-app__panel film-app__comments-panel">
      <div className="film-app__panel-header">
        <h2 className="film-app__panel-title">Comments</h2>
        <span className="film-app__count-badge">${totalCommentCount(comments)}</span>
      </div>

      <form className="film-app__comment-compose" onSubmit=${submitComment}>
        <${MentionEditor}
          value=${draft}
          onChange=${setDraft}
          mentionables=${mentionList}
          placeholder="Share your thoughts... type @ to mention someone"
        />
        <div className="film-app__form-actions">
          <button disabled=${busy} type="submit" className="film-app__action-btn-submit">${busy ? "Posting..." : "Post Comment"}</button>
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
