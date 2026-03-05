import { useEffect, useRef, useState } from "../deps.js";

function loadYouTubeApi() {
  if (window.YT && window.YT.Player) {
    return Promise.resolve(window.YT);
  }
  if (window.__filmRoomYouTubePromise) {
    return window.__filmRoomYouTubePromise;
  }

  window.__filmRoomYouTubePromise = new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = "https://www.youtube.com/iframe_api";
    script.async = true;
    document.head.appendChild(script);

    const prevReady = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      if (typeof prevReady === "function") {
        prevReady();
      }
      resolve(window.YT);
    };
  });

  return window.__filmRoomYouTubePromise;
}

export function useYouTubePlayer({ videoId, onTimeUpdate }) {
  const hostRef = useRef(null);
  const playerRef = useRef(null);
  const rafRef = useRef(null);
  const lastTickMsRef = useRef(0);
  const [isReady, setIsReady] = useState(false);
  const [playerState, setPlayerState] = useState(-1);

  function stopLoop() {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }

  function startLoop() {
    stopLoop();

    const tick = (ts) => {
      const player = playerRef.current;
      if (player && typeof onTimeUpdate === "function") {
        if (!lastTickMsRef.current || ts - lastTickMsRef.current >= 120) {
          lastTickMsRef.current = ts;
          try {
            onTimeUpdate({
              currentTime: player.getCurrentTime(),
              duration: player.getDuration(),
              playerState: player.getPlayerState(),
            });
          } catch {
            // Ignore transient player errors while iframe initializes.
          }
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
  }

  useEffect(() => {
    let cancelled = false;

    if (!videoId) {
      setIsReady(false);
      setPlayerState(-1);
      if (playerRef.current) {
        try {
          playerRef.current.destroy();
        } catch {
          // Ignore no-op destroy.
        }
      }
      playerRef.current = null;
      stopLoop();
      return undefined;
    }

    async function mountPlayer() {
      const yt = await loadYouTubeApi();
      if (cancelled || !hostRef.current) {
        return;
      }

      if (playerRef.current) {
        try {
          playerRef.current.loadVideoById(videoId);
          setIsReady(true);
          startLoop();
          return;
        } catch {
          try {
            playerRef.current.destroy();
          } catch {
            // Ignore destroy errors.
          }
          playerRef.current = null;
        }
      }

      playerRef.current = new yt.Player(hostRef.current, {
        videoId,
        width: "100%",
        height: "100%",
        playerVars: {
          rel: 0,
          modestbranding: 1,
          playsinline: 1,
          origin: window.location.origin,
        },
        events: {
          onReady: () => {
            if (cancelled) {
              return;
            }
            setIsReady(true);
            startLoop();
          },
          onStateChange: (evt) => {
            if (cancelled) {
              return;
            }
            setPlayerState(evt.data);
          },
        },
      });
    }

    mountPlayer();

    return () => {
      cancelled = true;
    };
  }, [videoId]);

  useEffect(() => {
    return () => {
      stopLoop();
      if (playerRef.current) {
        try {
          playerRef.current.destroy();
        } catch {
          // Ignore no-op destroy.
        }
        playerRef.current = null;
      }
    };
  }, []);

  function seekTo(seconds) {
    const player = playerRef.current;
    if (!player || !isReady) {
      return;
    }
    const numeric = Number(seconds);
    if (!Number.isFinite(numeric)) {
      return;
    }
    player.seekTo(Math.max(0, numeric), true);
  }

  function togglePlayPause() {
    const player = playerRef.current;
    if (!player || !isReady) {
      return;
    }
    if (player.getPlayerState() === 1) {
      player.pauseVideo();
    } else {
      player.playVideo();
    }
  }

  function seekRelative(deltaSeconds) {
    const player = playerRef.current;
    if (!player || !isReady) {
      return;
    }
    const next = player.getCurrentTime() + deltaSeconds;
    player.seekTo(Math.max(0, next), true);
  }

  function fullscreen() {
    const player = playerRef.current;
    if (!player || !isReady) {
      return;
    }
    try {
      const iframe = player.getIframe();
      if (iframe && iframe.requestFullscreen) {
        iframe.requestFullscreen();
      }
    } catch {
      // Ignore browser-level fullscreen denial.
    }
  }

  function getCurrentTime() {
    const player = playerRef.current;
    if (!player || !isReady) {
      return null;
    }
    try {
      return player.getCurrentTime();
    } catch {
      return null;
    }
  }

  return {
    hostRef,
    isReady,
    playerState,
    seekTo,
    togglePlayPause,
    seekRelative,
    fullscreen,
    getCurrentTime,
  };
}
