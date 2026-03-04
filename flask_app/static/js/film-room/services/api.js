export function createApiClient(apiPrefix) {
  const prefix = apiPrefix || "/api/v1";

  async function request(path, options = {}) {
    const init = {
      credentials: "same-origin",
      ...options,
      headers: {
        ...(options.headers || {}),
      },
    };

    if (init.body && !init.headers["Content-Type"]) {
      init.headers["Content-Type"] = "application/json";
    }

    const response = await fetch(`${prefix}${path}`, init);
    const contentType = response.headers.get("content-type") || "";
    let payload = {};

    if (contentType.includes("application/json")) {
      payload = await response.json();
    } else if (response.status >= 400) {
      payload = { error: `Request failed (${response.status})` };
    }

    if (!response.ok) {
      throw new Error(payload.error || `Request failed (${response.status})`);
    }

    return payload;
  }

  return {
    getGames() {
      return request("/games");
    },
    getGame(gameId) {
      return request(`/games/${gameId}`);
    },
    createComment(gameId, payload) {
      return request(`/games/${gameId}/comments`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    updateComment(gameId, commentId, payload) {
      return request(`/games/${gameId}/comments/${commentId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    },
    deleteComment(gameId, commentId) {
      return request(`/games/${gameId}/comments/${commentId}`, {
        method: "DELETE",
      });
    },
    updatePoint(gameId, pointId, payload) {
      return request(`/games/${gameId}/points/${pointId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    },
    trackWatchTime(gameId, payload) {
      return request(`/games/${gameId}/track-watch-time`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
  };
}
