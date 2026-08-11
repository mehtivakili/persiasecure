import { useEffect, useRef, useState } from "react";
import { Box, CircularProgress, Typography } from "@mui/material";
import VideocamOffIcon from "@mui/icons-material/VideocamOff";
import Hls from "hls.js";

import type { PlaybackUrls } from "../api/types";
import { useCameraDetectionsQuery } from "../api/endpoints";

interface Props {
  playback: PlaybackUrls;
  muted?: boolean;
  label?: string;
  // When set, poll the camera's live AI detections and draw bounding boxes.
  cameraId?: number;
  showDetections?: boolean;
}

const VEHICLE_LABELS = new Set(["car", "truck", "bus", "motorbike", "bicycle"]);

function boxColor(label: string) {
  if (label === "person") return "#2ee6a6"; // green
  if (VEHICLE_LABELS.has(label)) return "#ffb02e"; // amber
  return "#ffd93b"; // yellow
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
export default function VideoPlayer({
  playback,
  muted = true,
  label,
  cameraId,
  showDetections = false,
}: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [state, setState] = useState<State>("connecting");

  // Live AI overlay: poll the latest detections for this camera and draw them.
  const overlayOn = Boolean(showDetections && cameraId);
  const { data: det } = useCameraDetectionsQuery(cameraId as number, {
    skip: !overlayOn,
    pollingInterval: 500, // ~2 refreshes/sec — smooth with the GPU multi-fps loop
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;

    const draw = () => {
      const cw = canvas.clientWidth;
      const ch = canvas.clientHeight;
      if (canvas.width !== cw) canvas.width = cw;
      if (canvas.height !== ch) canvas.height = ch;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.clearRect(0, 0, cw, ch);
      if (!overlayOn || !det?.active) return;
      const vw = video.videoWidth;
      const vh = video.videoHeight;
      if (!vw || !vh) return;
      // Map normalized boxes onto the video's displayed rect (objectFit: contain).
      const scale = Math.min(cw / vw, ch / vh);
      const dw = vw * scale;
      const dh = vh * scale;
      const ox = (cw - dw) / 2;
      const oy = (ch - dh) / 2;
      ctx.lineWidth = 2;
      ctx.font = "600 12px sans-serif";
      for (const d of det.detections || []) {
        if (!d.bbox || d.bbox.length < 4) continue;
        const [x, y, w, h] = d.bbox;
        const rx = ox + x * dw;
        const ry = oy + y * dh;
        const rw = w * dw;
        const rh = h * dh;
        const color = boxColor(d.label);
        ctx.strokeStyle = color;
        ctx.strokeRect(rx, ry, rw, rh);
        const text = `${d.label} ${Math.round(d.confidence * 100)}%`;
        const tw = ctx.measureText(text).width + 8;
        ctx.fillStyle = color;
        ctx.fillRect(rx, Math.max(0, ry - 16), tw, 16);
        ctx.fillStyle = "#00120c";
        ctx.fillText(text, rx + 4, Math.max(11, ry - 4));
      }
    };

    draw();
    const ro = new ResizeObserver(draw);
    ro.observe(canvas);
    return () => ro.disconnect();
  }, [det, overlayOn]);
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
      {overlayOn && (
        <canvas
          ref={canvasRef}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
          }}
        />
      )}
      {overlayOn && det?.active && (
        <Box
          sx={{
            position: "absolute",
            bottom: 6,
            insetInlineStart: 6,
            px: 0.9,
            py: 0.25,
            borderRadius: 1,
            display: "flex",
            alignItems: "center",
            gap: 0.5,
            fontSize: 10.5,
            fontWeight: 700,
            letterSpacing: "0.08em",
            color: "#7ef2c8",
            bgcolor: "rgba(46,230,166,0.16)",
            border: "1px solid rgba(46,230,166,0.55)",
          }}
        >
          AI{det.detections?.length ? ` • ${det.detections.length}` : ""}
        </Box>
      )}
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
