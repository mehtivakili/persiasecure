import { Box, Tooltip } from "@mui/material";

import type { TimelineSegment, VmsEvent, Bookmark } from "../../api/types";

const DAY_MS = 24 * 60 * 60 * 1000;

interface Props {
  dayStart: number; // ms at local 00:00
  segments: TimelineSegment[];
  events: VmsEvent[];
  bookmarks: Bookmark[];
  time: number; // playhead, ms
  selection: { start: number; end: number } | null;
  onSeek: (ms: number) => void;
}

const sevColor: Record<string, string> = {
  info: "#3aa0ff",
  warning: "#ffb020",
  critical: "#ff5a5f",
};

/**
 * A 24-hour timeline: recorded coverage, motion/event and bookmark markers, an
 * export selection and a click-to-seek playhead.
 *
 * IMPORTANT (RTL): the app runs through stylis-plugin-rtl, which rewrites the
 * physical `left` property to `right` at build time — that mirrored the whole bar
 * while the click math still measured from the left edge, so clicks landed on the
 * wrong time. We position everything with the LOGICAL `insetInlineStart` (which
 * the RTL plugin leaves alone) inside a `dir="ltr"` box, so time flows left→right
 * and `clientX - rect.left` maps correctly.
 */
export default function Timeline({
  dayStart, segments, events, bookmarks, time, selection, onSeek,
}: Props) {
  const pct = (ms: number) => Math.max(0, Math.min(100, ((ms - dayStart) / DAY_MS) * 100));

  const seekFromEvent = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    onSeek(dayStart + frac * DAY_MS);
  };

  return (
    <Box dir="ltr" sx={{ userSelect: "none" }}>
      {/* Hour ticks */}
      <Box sx={{ position: "relative", height: 16, mb: 0.5 }}>
        {Array.from({ length: 25 }).map((_, h) => (
          <Box
            key={h}
            sx={{
              position: "absolute",
              insetInlineStart: `${(h / 24) * 100}%`,
              transform: "translateX(-50%)",
              fontSize: 9,
              color: "text.disabled",
            }}
          >
            {h % 3 === 0 ? String(h).padStart(2, "0") : "·"}
          </Box>
        ))}
      </Box>

      <Box
        onClick={seekFromEvent}
        sx={{
          position: "relative",
          height: 54,
          bgcolor: "#0b1017",
          borderRadius: 1,
          border: "1px solid #2b3a4f",
          cursor: "pointer",
          overflow: "hidden",
        }}
      >
        {/* Recorded coverage */}
        {segments.map((s) => {
          const start = new Date(s.start).getTime();
          const end = s.end ? new Date(s.end).getTime() : start + (s.duration || 0) * 1000;
          const left = pct(start);
          const width = Math.max(0.15, pct(end) - left);
          return (
            <Box
              key={s.id}
              sx={{
                position: "absolute",
                top: 8,
                height: 38,
                insetInlineStart: `${left}%`,
                width: `${width}%`,
                bgcolor: s.has_motion ? "rgba(255,176,32,0.55)" : "rgba(58,160,255,0.40)",
              }}
            />
          );
        })}

        {/* Export selection */}
        {selection && (
          <Box
            sx={{
              position: "absolute",
              top: 0,
              bottom: 0,
              insetInlineStart: `${pct(Math.min(selection.start, selection.end))}%`,
              width: `${Math.abs(pct(selection.end) - pct(selection.start))}%`,
              bgcolor: "rgba(124,214,160,0.20)",
              borderInline: "1px solid #7cd6a0",
            }}
          />
        )}

        {/* Event markers */}
        {events.map((ev) => {
          const t = new Date(ev.ts).getTime();
          if (t < dayStart || t > dayStart + DAY_MS) return null;
          return (
            <Tooltip key={ev.id} title={`${ev.type} — ${new Date(ev.ts).toLocaleTimeString()}`}>
              <Box
                sx={{
                  position: "absolute",
                  top: 0,
                  height: 8,
                  width: 3,
                  insetInlineStart: `${pct(t)}%`,
                  marginInlineStart: "-1.5px",
                  bgcolor: sevColor[ev.severity] || "#fff",
                }}
              />
            </Tooltip>
          );
        })}

        {/* Bookmark markers */}
        {bookmarks.map((b) => {
          const t = new Date(b.start).getTime();
          if (t < dayStart || t > dayStart + DAY_MS) return null;
          return (
            <Tooltip key={b.id} title={b.note}>
              <Box
                sx={{
                  position: "absolute",
                  bottom: 0,
                  height: 8,
                  width: 3,
                  insetInlineStart: `${pct(t)}%`,
                  marginInlineStart: "-1.5px",
                  bgcolor: "#c792ea",
                }}
              />
            </Tooltip>
          );
        })}

        {/* Playhead */}
        <Box
          sx={{
            position: "absolute",
            top: 0,
            bottom: 0,
            insetInlineStart: `${pct(time)}%`,
            marginInlineStart: "-1px",
            width: 2,
            bgcolor: "#fff",
            boxShadow: "0 0 4px rgba(255,255,255,0.8)",
          }}
        />
      </Box>
    </Box>
  );
}
