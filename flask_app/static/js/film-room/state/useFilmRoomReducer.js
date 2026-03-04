function readPlayerSheetState() {
  try {
    const raw = window.sessionStorage.getItem("film_app_player_sheet_open");
    if (raw === null) {
      return true;
    }
    return raw === "1";
  } catch {
    return true;
  }
}

export function createInitialState(initialGameId) {
  return {
    games: [],
    gamesLoading: false,
    gamesQuery: "",
    drawerOpen: !initialGameId,
    selectedGameId: initialGameId || null,
    game: null,
    gameLoading: false,
    error: "",
    activePointIndex: null,
    activeCommentId: null,
    videoCurrentTime: 0,
    videoDuration: 0,
    playerState: -1,
    playerSheetOpen: readPlayerSheetState(),
  };
}

export function reducer(state, action) {
  switch (action.type) {
    case "SET_ERROR":
      return {
        ...state,
        error: action.error || "",
      };
    case "SET_DRAWER_OPEN":
      return {
        ...state,
        drawerOpen: Boolean(action.open),
      };
    case "SET_GAMES_QUERY":
      return {
        ...state,
        gamesQuery: action.value || "",
      };
    case "LOAD_GAMES_START":
      return {
        ...state,
        gamesLoading: true,
      };
    case "LOAD_GAMES_SUCCESS":
      return {
        ...state,
        gamesLoading: false,
        games: action.games || [],
      };
    case "LOAD_GAMES_ERROR":
      return {
        ...state,
        gamesLoading: false,
        error: action.error || "Failed to load games.",
      };
    case "SELECT_GAME":
      return {
        ...state,
        selectedGameId: action.gameId || null,
        drawerOpen: false,
      };
    case "LOAD_GAME_START":
      return {
        ...state,
        gameLoading: true,
        error: "",
      };
    case "LOAD_GAME_SUCCESS":
      return {
        ...state,
        gameLoading: false,
        game: action.game || null,
        activePointIndex: null,
        activeCommentId: null,
      };
    case "LOAD_GAME_ERROR":
      return {
        ...state,
        gameLoading: false,
        error: action.error || "Failed to load game.",
      };
    case "VIDEO_TICK":
      return {
        ...state,
        videoCurrentTime: action.currentTime ?? state.videoCurrentTime,
        videoDuration: action.duration ?? state.videoDuration,
        playerState: action.playerState ?? state.playerState,
      };
    case "SET_ACTIVE_POINT":
      return {
        ...state,
        activePointIndex: action.pointIndex ?? null,
      };
    case "SET_ACTIVE_COMMENT":
      return {
        ...state,
        activeCommentId: action.commentId ?? null,
      };
    case "SET_PLAYER_SHEET_OPEN":
      return {
        ...state,
        playerSheetOpen: Boolean(action.open),
      };
    default:
      return state;
  }
}
