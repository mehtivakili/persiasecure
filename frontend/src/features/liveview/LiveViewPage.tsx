import { useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Button,
  Card,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";
import GridViewIcon from "@mui/icons-material/GridView";
import VideocamOffIcon from "@mui/icons-material/VideocamOff";
import SlideshowIcon from "@mui/icons-material/Slideshow";
import FullscreenIcon from "@mui/icons-material/Fullscreen";
import PhotoCameraIcon from "@mui/icons-material/PhotoCamera";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";
import StopCircleIcon from "@mui/icons-material/StopCircle";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import {
  useCamerasQuery,
  useStartRecordingMutation,
  useStopRecordingMutation,
} from "../../api/endpoints";
import { useAppSelector } from "../../app/hooks";
import { hasPerm } from "../auth/authSlice";
import VideoPlayer from "../../components/VideoPlayer";
import CameraStatusDot from "../cameras/CameraStatusDot";
import { authedDownload } from "../../utils/download";
import PtzPad from "./PtzPad";

const LAYOUTS = [
  { key: "1", cols: 1, count: 1 },
  { key: "4", cols: 2, count: 4 },
  { key: "9", cols: 3, count: 9 },
  { key: "16", cols: 4, count: 16 },
];

export default function LiveViewPage() {
  const { t } = useTranslation();
  const { data: cameras } = useCamerasQuery();
  const user = useAppSelector((s) => s.auth.user);
  const token = useAppSelector((s) => s.auth.access);
  const canPtz = hasPerm(user, "ptz.control");
  const canManage = hasPerm(user, "camera.manage");
  const [startRecording, { isLoading: starting }] = useStartRecordingMutation();
  const [stopRecording, { isLoading: stopping }] = useStopRecordingMutation();
  const [sp] = useSearchParams();
  const [layout, setLayout] = useState("4");
  const [selected, setSelected] = useState<number | null>(
    sp.get("camera") ? Number(sp.get("camera")) : null
  );
  const [tour, setTour] = useState(false);
  const [offset, setOffset] = useState(0);
  const gridRef = useRef<HTMLDivElement>(null);

  const conf = LAYOUTS.find((l) => l.key === layout)!;
  const allEnabled = useMemo(() => (cameras || []).filter((c) => c.enabled), [cameras]);

  // Camera tour (Genetec "sequence"): rotate which cameras fill the grid.
  useEffect(() => {
    if (!tour || allEnabled.length <= conf.count) return;
    const id = window.setInterval(() => setOffset((o) => o + 1), 8000);
    return () => clearInterval(id);
  }, [tour, allEnabled.length, conf.count]);

  const enabledCams = useMemo(() => {
    if (!allEnabled.length) return [];
    const start = tour ? offset % allEnabled.length : 0;
    const rotated = [...allEnabled.slice(start), ...allEnabled.slice(0, start)];
    return rotated.slice(0, conf.count);
  }, [allEnabled, conf.count, tour, offset]);

  const selectedCam = (cameras || []).find((c) => c.id === selected) || null;

  const goWall = () => gridRef.current?.requestFullscreen?.();
  const snapshot = async () => {
    if (!selectedCam) return;
    await authedDownload(
      `/api/cameras/${selectedCam.id}/snapshot/`,
      `${selectedCam.name}.jpg`,
      token
    ).catch(() => {});
  };

  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mb: 2 }} flexWrap="wrap">
        <Typography variant="h4">{t("liveview.title")}</Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Tooltip title={t("liveview.tour")}>
          <ToggleButton
            size="small"
            value="tour"
            selected={tour}
            onChange={() => setTour((v) => !v)}
          >
            <SlideshowIcon fontSize="small" sx={{ ml: 0.5 }} />
            {t("liveview.tour")}
          </ToggleButton>
        </Tooltip>
        <Tooltip title={t("liveview.wall")}>
          <Button size="small" variant="outlined" startIcon={<FullscreenIcon />} onClick={goWall}>
            {t("liveview.wall")}
          </Button>
        </Tooltip>
        <GridViewIcon color="disabled" />
        <ToggleButtonGroup
          size="small"
          exclusive
          value={layout}
          onChange={(_e, v) => v && setLayout(v)}
        >
          {LAYOUTS.map((l) => (
            <ToggleButton key={l.key} value={l.key}>
              {l.key}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Stack>

      <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start", minWidth: 0 }}>
        <Box
          ref={gridRef}
          sx={{
            flex: 1,
            minWidth: 0,
            display: "grid",
            gridTemplateColumns: `repeat(${conf.cols}, 1fr)`,
            gap: 1.5,
          }}
        >
          {Array.from({ length: conf.count }).map((_, i) => {
            const cam = enabledCams[i];
            if (!cam) {
              return (
                <Box
                  key={`empty-${i}`}
                  sx={{
                    aspectRatio: "16/9",
                    borderRadius: 2,
                    border: "1px dashed #2b3a4f",
                    bgcolor: "rgba(255,255,255,0.015)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "text.disabled",
                  }}
                >
                  <VideocamOffIcon sx={{ opacity: 0.35 }} />
                </Box>
              );
            }
            return (
              <Card
                key={cam.id}
                onClick={() => setSelected(cam.id)}
                sx={{
                  position: "relative",
                  aspectRatio: "16/9",
                  border:
                    selected === cam.id
                      ? "2px solid #3aa0ff"
                      : "1px solid #2b3a4f",
                  cursor: "pointer",
                  overflow: "hidden",
                }}
              >
                <VideoPlayer playback={cam.playback} label={cam.name} />
                <Chip
                  size="small"
                  icon={<CameraStatusDot status={cam.status} />}
                  label={t(`status.${cam.status}`)}
                  sx={{
                    position: "absolute",
                    bottom: 6,
                    insetInlineEnd: 6,
                    bgcolor: "rgba(0,0,0,0.6)",
                  }}
                />
              </Card>
            );
          })}
        </Box>

        <Box sx={{ width: 260, flexShrink: 0 }}>
          <FormControl fullWidth size="small" sx={{ mb: 2 }}>
            <InputLabel>{t("liveview.selectCamera")}</InputLabel>
            <Select
              label={t("liveview.selectCamera")}
              value={selected ?? ""}
              onChange={(e) => setSelected(Number(e.target.value))}
            >
              {(cameras || []).map((c) => (
                <MenuItem key={c.id} value={c.id}>
                  {c.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {selectedCam && (
            <Button
              fullWidth
              variant="outlined"
              startIcon={<PhotoCameraIcon />}
              onClick={snapshot}
              sx={{ mb: 2 }}
            >
              {t("liveview.snapshot")}
            </Button>
          )}
          {selectedCam && canManage && (
            <Button
              fullWidth
              variant={selectedCam.manual_recording ? "contained" : "outlined"}
              color={selectedCam.recording_active ? "error" : "primary"}
              disabled={
                starting ||
                stopping ||
                (Boolean(selectedCam.recording_active) && !selectedCam.manual_recording)
              }
              startIcon={
                selectedCam.manual_recording ? <StopCircleIcon /> : <FiberManualRecordIcon />
              }
              onClick={() =>
                selectedCam.manual_recording
                  ? stopRecording(selectedCam.id)
                  : startRecording(selectedCam.id)
              }
              sx={{ mb: 2 }}
            >
              {selectedCam.manual_recording
                ? t("cameras.stopRec")
                : selectedCam.recording_active
                  ? t("cameras.recScheduled")
                  : t("cameras.startRec")}
            </Button>
          )}
          {selectedCam && canPtz && selectedCam.ptz_enabled ? (
            <PtzPad cameraId={selectedCam.id} />
          ) : (
            <Typography variant="caption" color="text.secondary">
              {selectedCam
                ? "این دوربین از PTZ پشتیبانی نمی‌کند."
                : t("liveview.selectCamera")}
            </Typography>
          )}
        </Box>
      </Box>
    </Box>
  );
}
