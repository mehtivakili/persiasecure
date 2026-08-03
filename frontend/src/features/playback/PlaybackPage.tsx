import { useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import MovieIcon from "@mui/icons-material/Movie";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import PauseIcon from "@mui/icons-material/Pause";
import Replay10Icon from "@mui/icons-material/Replay10";
import Forward10Icon from "@mui/icons-material/Forward10";
import SkipPreviousIcon from "@mui/icons-material/SkipPrevious";
import SkipNextIcon from "@mui/icons-material/SkipNext";
import PhotoCameraIcon from "@mui/icons-material/PhotoCamera";
import BookmarkAddIcon from "@mui/icons-material/BookmarkAdd";
import FlagIcon from "@mui/icons-material/Flag";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import {
  useCamerasQuery,
  useCreateExportMutation,
  useEventsQuery,
  useRecordingsTimelineQuery,
} from "../../api/endpoints";
import { useBookmarksQuery, useCreateBookmarkMutation } from "../../api/endpointsOps";
import { usePrompt } from "../../components/ConfirmProvider";
import JalaliDatePicker from "../../components/JalaliDatePicker";
import Timeline from "./Timeline";

const SPEEDS = [0.5, 1, 2, 4];

function fmtClock(ms: number) {
  const d = new Date(ms);
  return d.toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function PlaybackPage() {
  const { t } = useTranslation();
  const { data: cameras } = useCamerasQuery();
  const [sp] = useSearchParams();
  const today = new Date().toISOString().slice(0, 10);
  const [camera, setCamera] = useState<number | "">(sp.get("camera") ? Number(sp.get("camera")) : "");
  const [date, setDate] = useState(sp.get("date") || today);
  // Deep-link seek target (from the event drawer's "Open in playback").
  const pendingSeek = useRef<number | null>(sp.get("t") ? new Date(sp.get("t")!).getTime() : null);
  const promptDialog = usePrompt();

  const dayStart = useMemo(() => new Date(date + "T00:00:00").getTime(), [date]);
  const after = useMemo(() => new Date(dayStart).toISOString(), [dayStart]);
  const before = useMemo(() => new Date(dayStart + 86400000).toISOString(), [dayStart]);

  // Poll so freshly-recorded segments + new events appear on the timeline
  // without a manual refresh.
  const { data: segments, isFetching } = useRecordingsTimelineQuery(
    { camera: Number(camera) || 0, after, before },
    { skip: !camera, pollingInterval: 15000 }
  );
  const { data: allEvents } = useEventsQuery(
    camera ? { camera: Number(camera) } : undefined,
    { pollingInterval: 15000 }
  );
  const { data: bookmarks } = useBookmarksQuery(
    camera ? { camera: Number(camera) } : undefined,
    { skip: !camera }
  );
  const [createBookmark] = useCreateBookmarkMutation();
  const [exportJob] = useCreateExportMutation();

  // Segments in ms, sorted — the model the player seeks against.
  const segs = useMemo(
    () =>
      (segments || [])
        .map((s) => ({
          id: s.id,
          start: new Date(s.start).getTime(),
          end: s.end ? new Date(s.end).getTime() : new Date(s.start).getTime() + (s.duration || 0) * 1000,
          url: s.stream_url,
        }))
        .sort((a, b) => a.start - b.start),
    [segments]
  );
  const dayEvents = useMemo(
    () => (allEvents || []).filter((e) => {
      const ts = new Date(e.ts).getTime();
      return ts >= dayStart && ts < dayStart + 86400000;
    }),
    [allEvents, dayStart]
  );

  const videoRef = useRef<HTMLVideoElement>(null);
  const curSeg = useRef<{ id: number; start: number; end: number; url: string } | null>(null);
  const pendingOffset = useRef(0);
  const [activeSrc, setActiveSrc] = useState<string | null>(null);
  const [time, setTime] = useState(dayStart);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [noData, setNoData] = useState(false);
  const [selection, setSelection] = useState<{ start: number; end: number } | null>(null);

  const segmentAt = (ms: number) => segs.find((s) => ms >= s.start && ms < s.end);

  const seek = (targetMs: number) => {
    let seg = segmentAt(targetMs);
    if (!seg) {
      const next = segs.find((s) => s.start > targetMs);
      if (!next) {
        setNoData(true);
        setTime(targetMs);
        return;
      }
      seg = next;
      targetMs = next.start;
    }
    setNoData(false);
    const offset = (targetMs - seg.start) / 1000;
    if (curSeg.current?.id === seg.id && videoRef.current) {
      videoRef.current.currentTime = offset;
    } else {
      curSeg.current = seg;
      pendingOffset.current = offset;
      setActiveSrc(seg.url);
    }
    setTime(targetMs);
  };

  // Reset the player when the camera or day changes.
  useEffect(() => {
    curSeg.current = null;
    setActiveSrc(null);
    setSelection(null);
    setPlaying(false);
    setTime(dayStart);
  }, [camera, date, dayStart]);

  // Auto-select the first segment (or a deep-linked time) once segments arrive.
  useEffect(() => {
    if (segs.length && curSeg.current === null) {
      const target = pendingSeek.current;
      pendingSeek.current = null;
      seek(target && target >= dayStart && target < dayStart + 86400000 ? target : segs[0].start);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [segs]);

  useEffect(() => {
    if (videoRef.current) videoRef.current.playbackRate = speed;
  }, [speed, activeSrc]);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    if (playing) v.play().catch(() => {});
    else v.pause();
  }, [playing]);

  const onLoadedMetadata = () => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = pendingOffset.current;
    v.playbackRate = speed;
    if (playing) v.play().catch(() => {});
  };
  const onTimeUpdate = () => {
    const v = videoRef.current;
    if (v && curSeg.current) setTime(curSeg.current.start + v.currentTime * 1000);
  };
  const onEnded = () => {
    const cur = curSeg.current;
    if (!cur) return;
    const next = segs.find((s) => s.start >= cur.end);
    if (next) seek(next.start);
    else setPlaying(false);
  };

  const jumpEvent = (dir: 1 | -1) => {
    const sorted = dayEvents
      .map((e) => new Date(e.ts).getTime())
      .sort((a, b) => a - b);
    const target = dir === 1 ? sorted.find((ts) => ts > time + 500) : [...sorted].reverse().find((ts) => ts < time - 500);
    if (target) seek(target);
  };

  const snapshot = () => {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    canvas.getContext("2d")?.drawImage(v, 0, 0);
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/jpeg", 0.9);
    a.download = `snapshot_${fmtClock(time)}.jpg`;
    a.click();
  };

  const addBookmark = async () => {
    if (!camera) return;
    const note = await promptDialog({ title: t("playback.addBookmark"), label: t("playback.bookmarkNote") });
    if (!note) return;
    createBookmark({ camera: Number(camera), start: new Date(time).toISOString(), note } as any);
  };

  const doExport = () => {
    if (!camera || !selection) return;
    const s = Math.min(selection.start, selection.end);
    const e = Math.max(selection.start, selection.end);
    exportJob({ camera: Number(camera), start: new Date(s).toISOString(), end: new Date(e).toISOString() });
  };

  const hasSelection = selection && Math.abs(selection.end - selection.start) > 1000;

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>{t("playback.title")}</Typography>

      <Card sx={{ border: "1px solid #2b3a4f", mb: 2 }}>
        <CardContent>
          <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
            <FormControl size="small" sx={{ minWidth: 200 }}>
              <InputLabel>{t("playback.camera")}</InputLabel>
              <Select
                label={t("playback.camera")}
                value={camera}
                onChange={(e) => setCamera(Number(e.target.value))}
              >
                {(cameras || []).map((c) => (
                  <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <JalaliDatePicker label={t("playback.date")} value={date} onChange={(d) => d && setDate(d)} />
            <Box sx={{ flexGrow: 1 }} />
            <Typography variant="h6" sx={{ fontVariantNumeric: "tabular-nums" }}>{fmtClock(time)}</Typography>
          </Stack>
        </CardContent>
      </Card>

      <Card sx={{ overflow: "hidden", mb: 2 }}>
        <Box sx={{ aspectRatio: "16/9", bgcolor: "#05070a", position: "relative" }}>
          {activeSrc ? (
            <video
              ref={videoRef}
              key={activeSrc}
              src={activeSrc}
              onLoadedMetadata={onLoadedMetadata}
              onTimeUpdate={onTimeUpdate}
              onEnded={onEnded}
              onClick={() => setPlaying((p) => !p)}
              style={{ width: "100%", height: "100%", objectFit: "contain" }}
            />
          ) : (
            <Stack sx={{ height: "100%", alignItems: "center", justifyContent: "center", color: "text.secondary" }} spacing={1}>
              <MovieIcon sx={{ fontSize: 48, opacity: 0.4 }} />
              <Typography variant="body2">
                {!camera
                  ? t("playback.pickCamera")
                  : isFetching
                    ? t("common.loading")
                    : segs.length
                      ? t("playback.pickSegment")
                      : t("playback.noRecordings")}
              </Typography>
            </Stack>
          )}
          {noData && activeSrc === null && camera && segs.length > 0 && (
            <Box sx={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", color: "text.secondary" }}>
              <Typography variant="body2">{t("playback.gap")}</Typography>
            </Box>
          )}
        </Box>
      </Card>

      <Card sx={{ border: "1px solid #2b3a4f", mb: 2 }}>
        <CardContent>
          <Timeline
            dayStart={dayStart}
            segments={segments || []}
            events={dayEvents}
            bookmarks={bookmarks || []}
            time={time}
            selection={selection}
            onSeek={seek}
          />
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1.5 }} flexWrap="wrap" useFlexGap>
            <Tooltip title={t("playback.prevEvent")}>
              <span><IconButton onClick={() => jumpEvent(-1)} disabled={!segs.length}><SkipPreviousIcon /></IconButton></span>
            </Tooltip>
            <Tooltip title="-10s">
              <span><IconButton onClick={() => seek(time - 10000)} disabled={!segs.length}><Replay10Icon /></IconButton></span>
            </Tooltip>
            <IconButton
              color="primary"
              onClick={() => setPlaying((p) => !p)}
              disabled={!activeSrc}
              sx={{ bgcolor: "rgba(58,160,255,0.12)" }}
            >
              {playing ? <PauseIcon /> : <PlayArrowIcon />}
            </IconButton>
            <Tooltip title="+10s">
              <span><IconButton onClick={() => seek(time + 10000)} disabled={!segs.length}><Forward10Icon /></IconButton></span>
            </Tooltip>
            <Tooltip title={t("playback.nextEvent")}>
              <span><IconButton onClick={() => jumpEvent(1)} disabled={!segs.length}><SkipNextIcon /></IconButton></span>
            </Tooltip>

            <ToggleButtonGroup size="small" exclusive value={speed} onChange={(_e, v) => v && setSpeed(v)} sx={{ ml: 1 }}>
              {SPEEDS.map((s) => (
                <ToggleButton key={s} value={s}>{s}×</ToggleButton>
              ))}
            </ToggleButtonGroup>

            <Box sx={{ flexGrow: 1 }} />

            <Tooltip title={t("playback.snapshot")}>
              <span><IconButton onClick={snapshot} disabled={!activeSrc}><PhotoCameraIcon /></IconButton></span>
            </Tooltip>
            <Tooltip title={t("playback.addBookmark")}>
              <span><IconButton onClick={addBookmark} disabled={!camera}><BookmarkAddIcon /></IconButton></span>
            </Tooltip>
            <Button size="small" startIcon={<FlagIcon />} onClick={() => setSelection({ start: time, end: time })} disabled={!segs.length}>
              {t("playback.markIn")}
            </Button>
            <Button size="small" onClick={() => setSelection((s) => (s ? { ...s, end: time } : { start: time, end: time }))} disabled={!selection}>
              {t("playback.markOut")}
            </Button>
            {hasSelection && (
              <Chip size="small" color="success" variant="outlined"
                label={`${fmtClock(Math.min(selection!.start, selection!.end))} — ${fmtClock(Math.max(selection!.start, selection!.end))}`} />
            )}
            <Button variant="outlined" startIcon={<DownloadIcon />} onClick={doExport} disabled={!hasSelection}>
              {t("playback.exportRange")}
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
