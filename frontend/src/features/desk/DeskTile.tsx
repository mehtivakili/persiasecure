import { useState } from "react";
import {
  Box,
  Chip,
  CircularProgress,
  IconButton,
  Popover,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import FullscreenIcon from "@mui/icons-material/Fullscreen";
import PhotoCameraIcon from "@mui/icons-material/PhotoCamera";
import ReplayIcon from "@mui/icons-material/Replay";
import LiveTvIcon from "@mui/icons-material/LiveTv";
import ControlCameraIcon from "@mui/icons-material/ControlCamera";
import BookmarkAddIcon from "@mui/icons-material/BookmarkAdd";
import LockOpenIcon from "@mui/icons-material/LockOpen";
import LockIcon from "@mui/icons-material/Lock";
import MeetingRoomIcon from "@mui/icons-material/MeetingRoom";
import AddIcon from "@mui/icons-material/Add";
import { useTranslation } from "react-i18next";

import { useLazyRecordingsQuery } from "../../api/endpoints";
import { useCreateBookmarkMutation } from "../../api/endpointsOps";
import { useLockDoorMutation, useUnlockDoorMutation } from "../../api/endpointsPhase2";
import { useAppSelector } from "../../app/hooks";
import type { Camera, DeskTileKind, Door, SiteMap } from "../../api/types";
import VideoPlayer from "../../components/VideoPlayer";
import { usePrompt } from "../../components/ConfirmProvider";
import { authedDownload } from "../../utils/download";
import CameraStatusDot from "../cameras/CameraStatusDot";
import PtzPad from "../liveview/PtzPad";

export interface TileContent {
  kind: DeskTileKind;
  object_id: number;
}

interface Props {
  index: number;
  content: TileContent | null;
  cameras: Camera[];
  doors: Door[];
  maps: SiteMap[];
  onDrop: (index: number, kind: DeskTileKind, id: number) => void;
  onClear: (index: number) => void;
  onMaximize: (index: number) => void;
  /** Highlight a tile that an alarm was just pushed into. */
  alarmed?: boolean;
}

const REPLAY_SECONDS = 60;

export default function DeskTile({
  index,
  content,
  cameras,
  doors,
  maps,
  onDrop,
  onClear,
  onMaximize,
  alarmed,
}: Props) {
  const { t } = useTranslation();
  const token = useAppSelector((s) => s.auth.access);
  const [over, setOver] = useState(false);
  const [mode, setMode] = useState<"live" | "playback">("live");
  const [replayUrl, setReplayUrl] = useState<string | null>(null);
  const [loadingReplay, setLoadingReplay] = useState(false);
  const [ptzAnchor, setPtzAnchor] = useState<null | HTMLElement>(null);

  const [fetchRecordings] = useLazyRecordingsQuery();
  const [createBookmark] = useCreateBookmarkMutation();
  const promptDialog = usePrompt();
  const [unlockDoor] = useUnlockDoorMutation();
  const [lockDoor] = useLockDoorMutation();

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setOver(false);
    const raw = e.dataTransfer.getData("application/x-ps-entity");
    if (!raw) return;
    try {
      const { kind, id } = JSON.parse(raw);
      setMode("live");
      setReplayUrl(null);
      onDrop(index, kind, id);
    } catch {
      /* ignore malformed payload */
    }
  };

  const shell = (children: React.ReactNode) => (
    <Box
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={handleDrop}
      sx={{
        position: "relative",
        aspectRatio: "16/9",
        borderRadius: 2,
        overflow: "hidden",
        bgcolor: "#05070a",
        border: alarmed
          ? "2px solid #ff5a5f"
          : over
          ? "2px dashed #3da5ff"
          : content
          ? "1px solid #243044"
          : "1px dashed #243044",
        transition: "border-color .15s ease",
        ...(alarmed ? { animation: "psPulse 1.6s infinite" } : {}),
      }}
    >
      {children}
    </Box>
  );

  // ---- Empty tile -------------------------------------------------------
  if (!content) {
    return shell(
      <Stack
        sx={{ position: "absolute", inset: 0, color: "text.disabled" }}
        alignItems="center"
        justifyContent="center"
        spacing={0.5}
      >
        <AddIcon sx={{ opacity: 0.35 }} />
        <Typography variant="caption">{t("desk.emptyTile")}</Typography>
      </Stack>
    );
  }

  const bar = (children: React.ReactNode) => (
    <Box
      sx={{
        position: "absolute",
        insetInline: 0,
        bottom: 0,
        px: 0.5,
        py: 0.25,
        display: "flex",
        alignItems: "center",
        gap: 0.25,
        background: "linear-gradient(0deg, rgba(0,0,0,.85), transparent)",
        opacity: 0,
        transition: "opacity .15s ease",
        ".ps-tile:hover &": { opacity: 1 },
      }}
    >
      {children}
    </Box>
  );

  // ---- Camera tile ------------------------------------------------------
  if (content.kind === "camera") {
    const cam = cameras.find((c) => c.id === content.object_id);
    if (!cam) return shell(<Typography sx={{ p: 2 }}>—</Typography>);

    const instantReplay = async () => {
      setLoadingReplay(true);
      try {
        const now = Date.now();
        const res = await fetchRecordings({
          camera: cam.id,
          after: new Date(now - REPLAY_SECONDS * 1000 * 5).toISOString(),
          before: new Date(now).toISOString(),
        }).unwrap();
        const latest = res?.[0];
        if (latest?.stream_url) {
          setReplayUrl(latest.stream_url);
          setMode("playback");
        }
      } finally {
        setLoadingReplay(false);
      }
    };

    const snapshot = () =>
      authedDownload(`/api/cameras/${cam.id}/snapshot/`, `${cam.name}.jpg`, token).catch(() => {});

    const bookmark = async () => {
      const note = await promptDialog({
        title: t("playback.addBookmark"),
        label: t("playback.bookmarkNote"),
      });
      if (note) createBookmark({ camera: cam.id, start: new Date().toISOString(), note } as any);
    };

    return shell(
      <Box className="ps-tile" sx={{ position: "absolute", inset: 0 }}>
        {mode === "live" || !replayUrl ? (
          <VideoPlayer playback={cam.playback} label={cam.name} />
        ) : (
          <>
            <video
              key={replayUrl}
              src={replayUrl}
              controls
              autoPlay
              style={{ width: "100%", height: "100%", objectFit: "contain" }}
            />
            <Chip
              size="small"
              color="warning"
              label={t("desk.replay")}
              sx={{ position: "absolute", top: 6, insetInlineStart: 8 }}
            />
          </>
        )}

        {bar(
          <>
            <Chip
              size="small"
              icon={<CameraStatusDot status={cam.status} />}
              label={cam.name}
              sx={{ bgcolor: "rgba(0,0,0,.6)", maxWidth: 150 }}
            />
            <Box sx={{ flexGrow: 1 }} />
            {mode === "playback" && (
              <Tooltip title={t("desk.backToLive")}>
                <IconButton size="small" onClick={() => setMode("live")}>
                  <LiveTvIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
            <Tooltip title={t("desk.instantReplay")}>
              <IconButton size="small" onClick={instantReplay} disabled={loadingReplay}>
                {loadingReplay ? <CircularProgress size={16} /> : <ReplayIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
            {cam.ptz_enabled && (
              <Tooltip title={t("liveview.ptz")}>
                <IconButton size="small" onClick={(e) => setPtzAnchor(e.currentTarget)}>
                  <ControlCameraIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
            <Tooltip title={t("liveview.snapshot")}>
              <IconButton size="small" onClick={snapshot}>
                <PhotoCameraIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title={t("playback.addBookmark")}>
              <IconButton size="small" onClick={bookmark}>
                <BookmarkAddIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title={t("desk.maximize")}>
              <IconButton size="small" onClick={() => onMaximize(index)}>
                <FullscreenIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title={t("desk.clearTile")}>
              <IconButton size="small" onClick={() => onClear(index)}>
                <CloseIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </>
        )}

        <Popover
          open={!!ptzAnchor}
          anchorEl={ptzAnchor}
          onClose={() => setPtzAnchor(null)}
          anchorOrigin={{ vertical: "top", horizontal: "center" }}
          transformOrigin={{ vertical: "bottom", horizontal: "center" }}
        >
          <PtzPad cameraId={cam.id} />
        </Popover>
      </Box>
    );
  }

  // ---- Door tile --------------------------------------------------------
  if (content.kind === "door") {
    const door = doors.find((d) => d.id === content.object_id);
    if (!door) return shell(<Typography sx={{ p: 2 }}>—</Typography>);
    const linked = cameras.find((c) => c.id === door.camera);
    return shell(
      <Box className="ps-tile" sx={{ position: "absolute", inset: 0 }}>
        {linked ? (
          <VideoPlayer playback={linked.playback} label={door.name} />
        ) : (
          <Stack sx={{ position: "absolute", inset: 0 }} alignItems="center" justifyContent="center" spacing={1}>
            <MeetingRoomIcon sx={{ fontSize: 44, opacity: 0.4 }} />
            <Typography variant="subtitle1">{door.name}</Typography>
          </Stack>
        )}
        <Chip
          size="small"
          color={door.state === "unlocked" ? "success" : door.state === "offline" ? "error" : "default"}
          label={t(`access.state.${door.state}`)}
          sx={{ position: "absolute", top: 6, insetInlineEnd: 8 }}
        />
        {bar(
          <>
            <Chip size="small" label={door.name} sx={{ bgcolor: "rgba(0,0,0,.6)" }} />
            <Box sx={{ flexGrow: 1 }} />
            <Tooltip title={t("access.unlock")}>
              <IconButton size="small" color="success" onClick={() => unlockDoor(door.id)}>
                <LockOpenIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title={t("access.lock")}>
              <IconButton size="small" onClick={() => lockDoor(door.id)}>
                <LockIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title={t("desk.clearTile")}>
              <IconButton size="small" onClick={() => onClear(index)}>
                <CloseIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </>
        )}
      </Box>
    );
  }

  // ---- Map tile ---------------------------------------------------------
  const map = maps.find((m) => m.id === content.object_id);
  if (!map) return shell(<Typography sx={{ p: 2 }}>—</Typography>);
  return shell(
    <Box className="ps-tile" sx={{ position: "absolute", inset: 0 }}>
      <Box sx={{ position: "absolute", inset: 0, overflow: "hidden" }}>
        <img src={map.image} alt={map.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        {map.markers?.map((mk) => (
          <Box
            key={mk.id}
            title={mk.label}
            sx={{
              position: "absolute",
              top: `${mk.y}%`,
              insetInlineStart: `${mk.x}%`,
              transform: "translate(-50%,-50%)",
              width: 18,
              height: 18,
              borderRadius: "50%",
              bgcolor: mk.kind === "camera" ? "primary.main" : "secondary.main",
              border: "2px solid rgba(0,0,0,.5)",
            }}
          />
        ))}
      </Box>
      {bar(
        <>
          <Chip size="small" label={map.name} sx={{ bgcolor: "rgba(0,0,0,.6)" }} />
          <Box sx={{ flexGrow: 1 }} />
          <Tooltip title={t("desk.clearTile")}>
            <IconButton size="small" onClick={() => onClear(index)}>
              <CloseIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </>
      )}
    </Box>
  );
}
