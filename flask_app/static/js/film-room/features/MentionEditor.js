import { html, useEffect, useMemo, useRef, useState } from "../deps.js";

/**
 * MentionEditor - contenteditable input with visual mention tokens
 * Mimics the game_player.html mention system with inline chips and X buttons
 */
export function MentionEditor({ value, onChange, mentionables, placeholder, minHeight = "60px" }) {
  const [mention, setMention] = useState({
    active: false,
    query: "",
    selIdx: 0,
    triggerStart: -1,
  });
  const editorRef = useRef(null);
  const placeholderText = placeholder || "Type @ to mention someone...";

  const suggestions = useMemo(() => {
    if (!mention.active || !mentionables || !mentionables.length) return [];
    const q = mention.query.toLowerCase();
    return mentionables.filter((name) => name.toLowerCase().includes(q));
  }, [mention.active, mention.query, mentionables]);

  // Load initial content when value prop changes from outside
  useEffect(() => {
    const editor = editorRef.current;
    if (!editor) return;
    
    // Only update if the extracted content differs from value
    const current = extractContent(editor);
    if (current !== value) {
      loadContentWithMentions(editor, value || "");
    }
  }, [value]);

  // Extract content from contenteditable, converting mention tokens to @[username]
  function extractContent(editor) {
    let result = "";
    
    function walk(node) {
      if (node.nodeType === Node.TEXT_NODE) {
        result += node.textContent;
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        if (node.classList && node.classList.contains("film-app__mention-token")) {
          result += `@[${node.dataset.username}]`;
        } else if (node.tagName === "BR") {
          result += "\n";
        } else if ((node.tagName === "DIV" || node.tagName === "P") && result.length > 0 && !result.endsWith("\n")) {
          result += "\n";
          node.childNodes.forEach(walk);
        } else {
          node.childNodes.forEach(walk);
        }
      }
    }
    
    editor.childNodes.forEach(walk);
    return result.trim();
  }

  // Load content into editor, converting @[username] to mention tokens
  function loadContentWithMentions(editor, rawText) {
    editor.innerHTML = "";
    const parts = rawText.split(/(@\[[^\]]+\])/g);
    
    for (const part of parts) {
      const m = part.match(/^@\[(.+)\]$/);
      if (m) {
        editor.appendChild(makeMentionTokenEl(m[1]));
      } else if (part) {
        editor.appendChild(document.createTextNode(part));
      }
    }
    
    updateEmptyState(editor);
  }

  // Create a mention token element (chip with X button)
  function makeMentionTokenEl(username) {
    const span = document.createElement("span");
    span.className = "film-app__mention-token";
    span.contentEditable = "false";
    span.dataset.username = username;
    span.appendChild(document.createTextNode(username));
    
    const btn = document.createElement("button");
    btn.className = "film-app__mention-token-remove";
    btn.type = "button";
    btn.textContent = "×";
    btn.title = "Remove mention";
    
    btn.addEventListener("mousedown", (e) => {
      e.preventDefault();
      e.stopPropagation();
      
      // Replace token with plain text
      const plain = document.createTextNode(username);
      span.parentNode.replaceChild(plain, span);
      
      // Place cursor after the text
      const range = document.createRange();
      range.setStartAfter(plain);
      range.collapse(true);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      
      // Notify parent of change
      const editor = plain.parentNode && plain.parentNode.closest && plain.parentNode.closest("[contenteditable]");
      if (editor) {
        updateEmptyState(editor);
        onChange(extractContent(editor));
      }
    });
    
    span.appendChild(btn);
    return span;
  }

  // Update empty state for placeholder display
  function updateEmptyState(editor) {
    const h = editor.innerHTML;
    const noContent = h === "" || h === "<br>" || h === "<div><br></div>";
    const hasToken = !!editor.querySelector(".film-app__mention-token");
    
    if (noContent && !hasToken) {
      editor.classList.add("is-empty");
    } else {
      editor.classList.remove("is-empty");
    }
  }

  // Detect @ mention trigger
  function detectMention(editor) {
    const sel = window.getSelection();
    if (!sel.rangeCount) return null;
    
    const range = sel.getRangeAt(0);
    const node = range.startContainer;
    
    // Don't trigger inside mention tokens
    if (node.parentElement && node.parentElement.closest(".film-app__mention-token")) {
      return null;
    }
    
    if (node.nodeType !== Node.TEXT_NODE) return null;
    
    const text = node.textContent;
    const pos = range.startOffset;
    const before = text.slice(0, pos);
    const match = before.match(/@([A-Za-z0-9_-]*)$/);
    
    if (match) {
      return {
        active: true,
        query: match[1],
        selIdx: 0,
        triggerStart: pos - match[0].length,
        textNode: node,
      };
    }
    
    return null;
  }

  // Handle input events
  function handleInput(e) {
    const editor = e.target;
    updateEmptyState(editor);
    
    const content = extractContent(editor);
    onChange(content);
    
    // Check for mention trigger
    const mentionState = detectMention(editor);
    if (mentionState) {
      setMention(mentionState);
    } else {
      setMention({ active: false, query: "", selIdx: 0, triggerStart: -1 });
    }
  }

  // Handle keydown for mention dropdown navigation
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
    } else if (e.key === "Enter" && !e.shiftKey) {
      const pick = suggestions[mention.selIdx] || suggestions[0];
      if (pick) {
        e.preventDefault();
        commitMention(pick);
      }
    } else if (e.key === "Tab") {
      const pick = suggestions[mention.selIdx] || suggestions[0];
      if (pick) {
        e.preventDefault();
        commitMention(pick);
      }
    } else if (e.key === "Escape") {
      setMention({ active: false, query: "", selIdx: 0, triggerStart: -1 });
    }
  }

  // Commit a mention selection
  function commitMention(username) {
    const editor = editorRef.current;
    if (!editor || !mention.textNode) return;
    
    const node = mention.textNode;
    const text = node.textContent;
    const pos = node === window.getSelection().getRangeAt(0).startContainer
      ? window.getSelection().getRangeAt(0).startOffset
      : text.length;
    
    // Split the text node
    const before = text.slice(0, mention.triggerStart);
    const after = text.slice(pos);
    
    // Create token
    const token = makeMentionTokenEl(username);
    
    // Replace text node with before text + token + after text
    if (before) {
      node.textContent = before;
      node.parentNode.insertBefore(token, node.nextSibling);
    } else {
      node.parentNode.replaceChild(token, node);
    }
    
    // Add space after token
    const space = document.createTextNode(" ");
    token.parentNode.insertBefore(space, token.nextSibling);
    
    // If there's after text, add it
    if (after) {
      const afterNode = document.createTextNode(after);
      space.parentNode.insertBefore(afterNode, space.nextSibling);
    }
    
    // Place cursor after space
    const range = document.createRange();
    range.setStartAfter(space);
    range.collapse(true);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    
    // Update state
    setMention({ active: false, query: "", selIdx: 0, triggerStart: -1 });
    updateEmptyState(editor);
    onChange(extractContent(editor));
  }

  // Handle blur to close dropdown
  function handleBlur() {
    setTimeout(() => {
      setMention((prev) => ({ ...prev, active: false }));
    }, 150);
  }

  // Handle paste to strip formatting
  function handlePaste(e) {
    e.preventDefault();
    const text = e.clipboardData.getData("text/plain");
    document.execCommand("insertText", false, text);
  }

  return html`
    <div style=${{ position: "relative" }}>
      <div
        ref=${editorRef}
        className="film-app__mention-editor is-empty"
        contentEditable="true"
        data-placeholder=${placeholderText}
        style=${{ minHeight }}
        onInput=${handleInput}
        onKeyDown=${handleKeyDown}
        onBlur=${handleBlur}
        onPaste=${handlePaste}
      ></div>
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
                    <span style=${{ opacity: 0.6, marginRight: "3px" }}>@</span>${name}
                  </div>
                `
              )}
            </div>
          `
        : null}
    </div>
  `;
}
