import { useMemo, useState } from "react";
import {
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { DataGrid, GridColDef } from "@mui/x-data-grid";
import DoneIcon from "@mui/icons-material/Done";
import DoneAllIcon from "@mui/icons-material/DoneAll";
import ClearIcon from "@mui/icons-material/Clear";
import CircleIcon from "@mui/icons-material/Circle";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import ReplayIcon from "@mui/icons-material/Replay";
import RefreshIcon from "@mui/icons-material/Refresh";
import AddAlertIcon from "@mui/icons-material/AddAlert";
import { useTranslation } from "react-i18next";

import {
  useAcknowledgeAllMutation,
  useAcknowledgeEventMutation,
  useCamerasQuery,
  useClearEventMutation,
  useCreateEventMutation,
  useEventsQuery,
  useRetryEventClipMutation,
} from "../../api/endpoints";
import type { EventFilters } from "../../api/endpoints";
import { useAppSelector } from "../../app/hooks";
import { hasPerm } from "../auth/authSlice";
import type { VmsEvent } from "../../api/types";
import { formatDateTime } from "../../utils/format";
import SeverityChip from "./SeverityChip";
import ClipPlayerDialog from "./ClipPlayerDialog";
import EventDetailDrawer from "./EventDetailDrawer";

const EVENT_TYPES = [
  "motion", "alpr", "object", "fire", "smoke", "tripwire", "offline", "tamper", "manual", "storage",
];
const SEVERITIES = ["info", "warning", "critical"];

export default function EventsPage() {
  const { t } = useTranslation();
  const [ackFilter, setAckFilter] = useState<"all" | "unack">("all");
  const [camera, setCamera] = useState<number | "">("");
  const [type, setType] = useState("");
  const [severity, setSeverity] = useState("");
  const [q, setQ] = useState("");
  const [clip, setClip] = useState<"all" | "with" | "without">("all");

  const params = useMemo<EventFilters>(() => {
    const p: EventFilters = {};
    if (ackFilter === "unack") p.acknowledged = false;
    if (camera) p.camera = Number(camera);
    if (type) p.type = type;
    if (severity) p.severity = severity;
    if (q.trim()) p.q = q.trim();
    if (clip === "with") p.has_clip = true;
    else if (clip === "without") p.has_clip = false;
    return p;
  }, [ackFilter, camera, type, severity, q, clip]);

  const { data: events, isLoading, refetch, isFetching } = useEventsQuery(params);
  const { data: cameras } = useCamerasQuery();
  const [ack] = useAcknowledgeEventMutation();
  const [clear] = useClearEventMutation();
  const [ackAll] = useAcknowledgeAllMutation();
  const [createEvent, { isLoading: creating }] = useCreateEventMutation();
  const [retryClip] = useRetryEventClipMutation();
  const user = useAppSelector((s) => s.auth.user);
  const canAck = hasPerm(user, "event.ack");

  const [playUrl, setPlayUrl] = useState<string | null>(null);
  const [selected, setSelected] = useState<VmsEvent | null>(null);
  const [markOpen, setMarkOpen] = useState(false);
  const [markCamera, setMarkCamera] = useState<number | "">("");

  const submitMark = async () => {
    if (!markCamera) return;
    await createEvent({
      camera: Number(markCamera),
      severity: "warning",
      details: { message: "رویداد آزمایشی — تولید کلیپ رویداد" },
    });
    setMarkOpen(false);
  };

  const columns: GridColDef<VmsEvent>[] = [
    {
      field: "snapshot",
      headerName: "",
      width: 70,
      sortable: false,
      renderCell: (p) =>
        p.value ? (
          <img src={p.value} alt="" style={{ width: 58, height: 34, objectFit: "cover", borderRadius: 6, display: "block" }} />
        ) : null,
    },
    { field: "severity", headerName: t("events.severity"), width: 100, renderCell: (p) => <SeverityChip severity={p.value} /> },
    { field: "type", headerName: t("events.type"), width: 110, valueFormatter: (v: string) => t(`eventTypes.${v}` as any) },
    { field: "camera_name", headerName: t("events.camera"), flex: 1, minWidth: 110 },
    {
      field: "clip",
      headerName: t("events.clip"),
      width: 120,
      sortable: false,
      renderCell: (p) => {
        const c = p.row.clip;
        if (!c) return <Typography variant="caption" color="text.disabled">—</Typography>;
        if (c.status === "ready" && c.stream_url) {
          return (
            <IconButton size="small" color="primary" onClick={(e) => { e.stopPropagation(); setPlayUrl(c.stream_url); }}>
              <PlayArrowIcon fontSize="small" />
            </IconButton>
          );
        }
        if (c.status === "failed") {
          return (
            <IconButton size="small" color="warning" onClick={(e) => { e.stopPropagation(); retryClip(c.id); }}>
              <ReplayIcon fontSize="small" />
            </IconButton>
          );
        }
        return <CircularProgress size={14} />;
      },
    },
    { field: "ts", headerName: t("events.time"), width: 160, valueFormatter: (v) => formatDateTime(v as string) },
    {
      field: "acknowledged",
      headerName: t("events.status"),
      width: 120,
      renderCell: (p) =>
        p.row.cleared ? (
          <Chip size="small" color="success" label={t("events.clear")} />
        ) : p.value ? (
          <Chip size="small" color="info" label={t("events.acknowledged")} />
        ) : (
          <Chip size="small" color="error" icon={<CircleIcon sx={{ fontSize: 10 }} />} label={t("events.unacknowledged")} />
        ),
    },
    {
      field: "actions",
      headerName: t("common.actions"),
      width: 90,
      sortable: false,
      renderCell: (p) => (
        <>
          <Tooltip title={t("events.acknowledge")}>
            <span>
              <IconButton size="small" onClick={(e) => { e.stopPropagation(); ack(p.row.id); }} disabled={!canAck || p.row.acknowledged}>
                <DoneIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title={t("events.clear")}>
            <span>
              <IconButton size="small" color="success" onClick={(e) => { e.stopPropagation(); clear(p.row.id); }} disabled={!canAck || p.row.cleared}>
                <ClearIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </>
      ),
    },
  ];

  return (
    <Box>
      <Stack direction="row" alignItems="center" sx={{ mb: 2 }} spacing={2}>
        <Typography variant="h4">{t("events.title")}</Typography>
        <Chip color="error" size="small" icon={<CircleIcon sx={{ fontSize: 10 }} />} label={t("events.live")} />
        <Box sx={{ flexGrow: 1 }} />
        <Tooltip title={t("common.refresh")}>
          <span><IconButton onClick={() => refetch()} disabled={isFetching}><RefreshIcon /></IconButton></span>
        </Tooltip>
        {canAck && (
          <Button variant="outlined" startIcon={<AddAlertIcon />} onClick={() => setMarkOpen(true)}>
            {t("events.markEvent")}
          </Button>
        )}
        {canAck && (
          <Button variant="outlined" startIcon={<DoneAllIcon />} onClick={() => ackAll()}>
            {t("events.acknowledgeAll")}
          </Button>
        )}
      </Stack>

      {/* Filters */}
      <Card sx={{ border: "1px solid #2b3a4f", mb: 2, p: 1.5 }}>
        <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap alignItems="center">
          <TextField size="small" label={t("common.search")} value={q} onChange={(e) => setQ(e.target.value)} sx={{ minWidth: 160 }} />
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>{t("events.camera")}</InputLabel>
            <Select label={t("events.camera")} value={camera} onChange={(e) => setCamera(Number(e.target.value) || "")}>
              <MenuItem value="">{t("common.none")}</MenuItem>
              {(cameras || []).map((c) => <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>{t("events.type")}</InputLabel>
            <Select label={t("events.type")} value={type} onChange={(e) => setType(e.target.value)}>
              <MenuItem value="">{t("common.none")}</MenuItem>
              {EVENT_TYPES.map((tp) => <MenuItem key={tp} value={tp}>{t(`eventTypes.${tp}`)}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 130 }}>
            <InputLabel>{t("events.severity")}</InputLabel>
            <Select label={t("events.severity")} value={severity} onChange={(e) => setSeverity(e.target.value)}>
              <MenuItem value="">{t("common.none")}</MenuItem>
              {SEVERITIES.map((s) => <MenuItem key={s} value={s}>{t(`severity.${s}`)}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>{t("events.clip")}</InputLabel>
            <Select label={t("events.clip")} value={clip} onChange={(e) => setClip(e.target.value as any)}>
              <MenuItem value="all">{t("events.allClips")}</MenuItem>
              <MenuItem value="with">{t("events.withClip")}</MenuItem>
              <MenuItem value="without">{t("events.withoutClip")}</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 130 }}>
            <InputLabel>{t("events.status")}</InputLabel>
            <Select label={t("events.status")} value={ackFilter} onChange={(e) => setAckFilter(e.target.value as any)}>
              <MenuItem value="all">{t("events.allClips")}</MenuItem>
              <MenuItem value="unack">{t("events.unacknowledged")}</MenuItem>
            </Select>
          </FormControl>
        </Stack>
      </Card>

      <Card sx={{ border: "1px solid #2b3a4f" }}>
        <DataGrid
          autoHeight
          rows={events || []}
          columns={columns}
          loading={isLoading}
          onRowClick={(p) => setSelected(p.row as VmsEvent)}
          disableRowSelectionOnClick
          pageSizeOptions={[10, 25, 50]}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          sx={{ border: 0, cursor: "pointer", "& .MuiDataGrid-cell": { borderColor: "#2b3a4f" } }}
        />
      </Card>

      {playUrl && <ClipPlayerDialog url={playUrl} onClose={() => setPlayUrl(null)} />}
      <EventDetailDrawer event={selected} onClose={() => setSelected(null)} onOpenEvent={(e) => setSelected(e)} />

      <Dialog open={markOpen} onClose={() => setMarkOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>{t("events.markEvent")}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{t("events.markEventHint")}</Typography>
          <TextField select fullWidth label={t("events.camera")} value={markCamera} onChange={(e) => setMarkCamera(Number(e.target.value))}>
            {(cameras || []).map((c) => <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>)}
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setMarkOpen(false)}>{t("common.cancel")}</Button>
          <Button variant="contained" onClick={submitMark} disabled={!markCamera || creating}>{t("common.confirm")}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
