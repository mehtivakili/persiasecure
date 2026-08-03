import { useEffect, useRef, useState } from "react";
import { Box, CircularProgress, Typography } from "@mui/material";
import VideocamOffIcon from "@mui/icons-material/VideocamOff";
import Hls from "hls.js";

import type { PlaybackUrls } from "../api/types";

interface Props {
  playback: PlaybackUrls;
  muted?: boolean;
  label?: string;
}

type State = "connecting" | "playing" | "error";

// MediaMTX pulls non-recording sources on demand, so the first WHEP/HLS request
// often arrives before the stream is published. Rather than fail (and force the
// user to navigate away and back), retry the whole WebRTC→HLS cycle a few times.
const MAX_ATTEMPTS = 6;
const RETRY_DELAY_MS = 2500;

/**
 * Live player: tries MediaMTX WebRTC (WHEP) for low latency, falls back to
 * HLS (hls.js / native), and auto-retries with backoff until the on-demand
 * source comes online.
 */
export default function VideoPlayer({ playback, muted = true, label }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [state, setState] = useState<State>("connecting");
  // Bumping `attempt` re-runs the connect effect; the ref caps total tries.
  const [attempt, setAttempt] = useState(0);
  const attemptRef = useRef(0);

  useEffect(() => {
    let pc: RTCPeerConnection | null = null;
    let hls: Hls | null = null;
    let cancelled = false;
    let retryTimer: number | undefined;

    const succeed = () => {
      if (cancelled) return;
      attemptRef.current = 0;
      setState("playing");
    };

    const fail = () => {
      if (cancelled) return;
      if (attemptRef.current < MAX_ATTEMPTS) {
        setState("connecting"); // still trying — show the spinner, not an error
        retryTimer = window.setTimeout(() => {
          attemptRef.current += 1;
          setAttempt((a) => a + 1);
        }, RETRY_DELAY_MS);
      } else {
        setState("error");
      }
    };

    const startHls = () => {
      const video = videoRef.current;
      if (!video) return;
      if (Hls.isSupported()) {
        hls = new Hls({ lowLatencyMode: true, liveSyncDurationCount: 2 });
        hls.loadSource(playback.hls);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          video.play().catch(() => {});
          succeed();
        });
        hls.on(Hls.Events.ERROR, (_e, data) => {
          if (data.fatal) {
            if (hls) hls.destroy();
            hls = null;
            fail();
          }
        });
      } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
        video.src = playback.hls;
        video.play().then(succeed).catch(fail);
      } else {
        fail();
      }
    };

    const startWebRtc = async () => {
      try {
        pc = new RTCPeerConnection();
        pc.addTransceiver("video", { direction: "recvonly" });
        pc.addTransceiver("audio", { direction: "recvonly" });
        pc.ontrack = (ev) => {
          const video = videoRef.current;
          if (video && ev.streams[0]) {
            video.srcObject = ev.streams[0];
            video.play().catch(() => {});
            succeed();
          }
        };
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        const res = await fetch(playback.webrtc, {
          method: "POST",
          headers: { "Content-Type": "application/sdp" },
          body: offer.sdp,
        });
        if (!res.ok) throw new Error("whep failed");
        const answer = await res.text();
        await pc.setRemoteDescription({ type: "answer", sdp: answer });
      } catch {
        // Fall back to HLS.
        if (pc) pc.close();
        pc = null;
        if (!cancelled) startHls();
      }
    };

    setState("connecting");
    startWebRtc();

    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
      if (pc) pc.close();
      if (hls) hls.destroy();
    };
  }, [playback.webrtc, playback.hls, attempt]);

  return (
    <Box
      sx={{
        position: "relative",
        width: "100%",
        height: "100%",
        bgcolor: "#000",
        borderRadius: 2,
        overflow: "hidden",
      }}
    >
      <video
        ref={videoRef}
        muted={muted}
        autoPlay
        playsInline
        style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }}
      />
      {state !== "playing" && (
        <Box
          sx={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 1,
            color: "text.secondary",
          }}
        >
          {state === "connecting" ? (
            <CircularProgress size={28} />
          ) : (
            <>
              <VideocamOffIcon />
              <Typography variant="caption">بدون سیگنال</Typography>
            </>
          )}
        </Box>
      )}
      {label && (
        <Box
          sx={{
            position: "absolute",
            top: 0,
            insetInline: 0,
            px: 1.25,
            py: 0.75,
            display: "flex",
            alignItems: "center",
            gap: 1,
            fontSize: 12.5,
            fontWeight: 700,
            background: "linear-gradient(180deg, rgba(0,0,0,0.75), transparent)",
          }}
        >
          {label}
          <Box sx={{ flexGrow: 1 }} />
          {state === "playing" && (
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 0.6,
                px: 0.9,
                py: 0.2,
                borderRadius: 1,
                bgcolor: "rgba(255,90,95,0.18)",
                border: "1px solid rgba(255,90,95,0.6)",
                color: "#ff8a8d",
                fontSize: 10.5,
                letterSpacing: "0.1em",
              }}
            >
              <Box
                sx={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  bgcolor: "#ff5a5f",
                  animation: "psPulse 1.6s infinite",
                }}
              />
              LIVE
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}
