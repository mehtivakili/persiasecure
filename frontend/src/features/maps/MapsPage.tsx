import { useRef, useState } from "react";
import {
  Box,
  Button,
  Card,
  Chip,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import UploadIcon from "@mui/icons-material/Upload";
import VideocamIcon from "@mui/icons-material/Videocam";
import MeetingRoomIcon from "@mui/icons-material/MeetingRoom";
import { useTranslation } from "react-i18next";

import {
  useCreateMapMutation,
  useCreateMarkerMutation,
  useDeleteMarkerMutation,
  useDoorsQuery,
  useMapsQuery,
} from "../../api/endpointsPhase2";
import { useCamerasQuery } from "../../api/endpoints";
import { useConfirm } from "../../components/ConfirmProvider";

export default function MapsPage() {
  const { t } = useTranslation();
  const { data: maps } = useMapsQuery();
  const { data: cameras } = useCamerasQuery();
  const { data: doors } = useDoorsQuery();
  const [createMap] = useCreateMapMutation();
  const [createMarker] = useCreateMarkerMutation();
  const [deleteMarker] = useDeleteMarkerMutation();
  const confirm = useConfirm();
  const fileRef = useRef<HTMLInputElement>(null);

  const [activeId, setActiveId] = useState<number | null>(null);
  const [placing, setPlacing] = useState<{ kind: "camera" | "door"; object_id: number; label: string } | null>(null);

  const active = (maps || []).find((m) => m.id === activeId) || (maps || [])[0] || null;

  const upload = async (file: File) => {
    const fd = new FormData();
    fd.append("name", file.name.replace(/\.[^.]+$/, ""));
    fd.append("image", file);
    await createMap(fd);
  };

  const onMapClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!placing || !active) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    createMarker({ site_map: active.id, kind: placing.kind, object_id: placing.object_id, label: placing.label, x, y });
    setPlacing(null);
  };

  return (
    <Box>
      <Stack direction="row" alignItems="center" sx={{ mb: 2 }} spacing={2}>
        <Typography variant="h4">{t("maps.title")}</Typography>
        <Box sx={{ flexGrow: 1 }} />
        <TextField
          select
          size="small"
          label={t("maps.select")}
          value={active?.id ?? ""}
          onChange={(e) => setActiveId(Number(e.target.value))}
          sx={{ minWidth: 180 }}
        >
          {(maps || []).map((m) => (
            <MenuItem key={m.id} value={m.id}>
              {m.name}
            </MenuItem>
          ))}
        </TextField>
        <Button variant="contained" startIcon={<UploadIcon />} onClick={() => fileRef.current?.click()}>
          {t("maps.upload")}
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
        />
      </Stack>

      {active ? (
        <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
          <Card sx={{ border: "1px solid #2b3a4f", flex: 1, p: 1 }}>
            <Box
              onClick={onMapClick}
              sx={{
                position: "relative",
                width: "100%",
                cursor: placing ? "crosshair" : "default",
                lineHeight: 0,
              }}
            >
              <img src={active.image} alt={active.name} style={{ width: "100%", borderRadius: 8 }} />
              {active.markers.map((mk) => (
                <Tooltip key={mk.id} title={mk.label}>
                  <Box
                    onClick={async (e) => {
                      e.stopPropagation();
                      const ok = await confirm({
                        message: t("maps.removeMarker"),
                        destructive: true,
                        confirmLabel: t("common.delete"),
                      });
                      if (ok) deleteMarker(mk.id);
                    }}
                    sx={{
                      position: "absolute",
                      top: `${mk.y}%`,
                      insetInlineStart: `${mk.x}%`,
                      transform: "translate(-50%, -50%)",
                      bgcolor: mk.kind === "camera" ? "primary.main" : "secondary.main",
                      color: "#fff",
                      borderRadius: "50%",
                      width: 30,
                      height: 30,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      boxShadow: 3,
                      cursor: "pointer",
                    }}
                  >
                    {mk.kind === "camera" ? <VideocamIcon fontSize="small" /> : <MeetingRoomIcon fontSize="small" />}
                  </Box>
                </Tooltip>
              ))}
            </Box>
          </Card>

          <Card sx={{ border: "1px solid #2b3a4f", width: { md: 260 }, p: 2 }}>
            <Typography variant="subtitle1" sx={{ mb: 1 }}>
              {placing ? t("maps.clickToPlace") : t("maps.addMarker")}
            </Typography>
            {placing && <Chip color="info" label={placing.label} onDelete={() => setPlacing(null)} sx={{ mb: 1 }} />}
            <Typography variant="caption" color="text.secondary">
              {t("nav.cameras")}
            </Typography>
            <Stack spacing={0.5} sx={{ my: 1 }}>
              {(cameras || []).map((c) => (
                <Button
                  key={c.id}
                  size="small"
                  variant="outlined"
                  startIcon={<VideocamIcon />}
                  onClick={() => setPlacing({ kind: "camera", object_id: c.id, label: c.name })}
                >
                  {c.name}
                </Button>
              ))}
            </Stack>
            <Typography variant="caption" color="text.secondary">
              {t("access.doors")}
            </Typography>
            <Stack spacing={0.5} sx={{ mt: 1 }}>
              {(doors || []).map((d) => (
                <Button
                  key={d.id}
                  size="small"
                  variant="outlined"
                  color="secondary"
                  startIcon={<MeetingRoomIcon />}
                  onClick={() => setPlacing({ kind: "door", object_id: d.id, label: d.name })}
                >
                  {d.name}
                </Button>
              ))}
            </Stack>
          </Card>
        </Stack>
      ) : (
        <Typography color="text.secondary">{t("maps.empty")}</Typography>
      )}
    </Box>
  );
}
