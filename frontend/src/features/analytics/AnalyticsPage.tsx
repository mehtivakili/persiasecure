import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Card,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
  MenuItem,
  Stack,
  Switch,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { DataGrid, GridColDef } from "@mui/x-data-grid";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import { useTranslation } from "react-i18next";

import {
  useAnalyticsRulesQuery,
  useCreateAnalyticsRuleMutation,
  useCreateWatchlistItemMutation,
  useDeleteAnalyticsRuleMutation,
  useDeleteWatchlistItemMutation,
  useMotionHeatmapQuery,
  useObjectDetectionsQuery,
  usePlateReadsQuery,
  usePlateWatchlistQuery,
  useRunRuleNowMutation,
  useUpdateAnalyticsRuleMutation,
} from "../../api/endpointsPhase2";
import { useCamerasQuery } from "../../api/endpoints";
import { useAppSelector } from "../../app/hooks";
import { formatDateTime, toFa } from "../../utils/format";

const KIND_COLORS: Record<string, "secondary" | "warning" | "info" | "error" | "default"> = {
  alpr: "secondary",
  object: "warning",
  motion: "info",
  fire: "error",
  smoke: "default",
  tripwire: "error",
};

/** Authenticated camera snapshot as a blob URL (for line editor / heatmap bg). */
function useSnapshotUrl(cameraId: number | null) {
  const token = useAppSelector((s) => s.auth.access);
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let revoke: string | null = null;
    setUrl(null);
    if (!cameraId) return;
    fetch(`/api/cameras/${cameraId}/snapshot/`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => (r.ok ? r.blob() : Promise.reject()))
      .then((b) => {
        revoke = URL.createObjectURL(b);
        setUrl(revoke);
      })
      .catch(() => setUrl(null));
    return () => {
      if (revoke) URL.revokeObjectURL(revoke);
    };
  }, [cameraId, token]);
  return url;
}

export default function AnalyticsPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState(0);
  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        {t("analytics.title")}
      </Typography>
      <Tabs value={tab} onChange={(_e, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label={t("analytics.rules")} />
        <Tab label={t("analytics.heatmap")} />
        <Tab label={t("analytics.plateReads")} />
        <Tab label={t("analytics.objects")} />
        <Tab label={t("analytics.watchlist")} />
      </Tabs>
      {tab === 0 && <RulesTab />}
      {tab === 1 && <HeatmapTab />}
      {tab === 2 && <PlateReadsTab />}
      {tab === 3 && <ObjectsTab />}
      {tab === 4 && <WatchlistTab />}
    </Box>
  );
}

function RulesTab() {
  const { t } = useTranslation();
  const { data: rules } = useAnalyticsRulesQuery();
  const { data: cameras } = useCamerasQuery();
  const [createRule] = useCreateAnalyticsRuleMutation();
  const [updateRule] = useUpdateAnalyticsRuleMutation();
  const [deleteRule] = useDeleteAnalyticsRuleMutation();
  const [runNow] = useRunRuleNowMutation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<any>({ camera: "", kind: "alpr", interval_seconds: 30, enabled: true });
  const [line, setLine] = useState<number[][]>([]);

  const save = async () => {
    const config: Record<string, unknown> = {};
    if (form.kind === "tripwire") {
      config.line = line;
      config.sensitivity = 6.0;
    }
    if (form.kind === "fire" || form.kind === "smoke") config.demo = true;
    await createRule({ ...form, camera: Number(form.camera), config });
    setOpen(false);
    setLine([]);
  };

  return (
    <Box>
      <Stack direction="row" sx={{ mb: 1 }}>
        <Box sx={{ flexGrow: 1 }} />
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)}>
          {t("analytics.addRule")}
        </Button>
      </Stack>
      <Grid container spacing={2}>
        {(rules || []).map((r) => (
          <Grid item xs={12} md={6} lg={4} key={r.id}>
            <Card sx={{ border: "1px solid #2b3a4f", p: 2 }}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <Chip
                  size="small"
                  color={KIND_COLORS[r.kind] || "info"}
                  label={t(`analytics.kind.${r.kind}`)}
                />
                <Typography sx={{ flexGrow: 1 }}>{r.camera_name}</Typography>
                <Switch
                  checked={r.enabled}
                  onChange={(e) => updateRule({ id: r.id, body: { enabled: e.target.checked } })}
                />
              </Stack>
              <Typography variant="caption" color="text.secondary">
                {t("analytics.interval")}: {toFa(r.interval_seconds)}s
              </Typography>
              <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                <Button size="small" startIcon={<PlayArrowIcon />} onClick={() => runNow(r.id)}>
                  {t("analytics.runNow")}
                </Button>
                <Box sx={{ flexGrow: 1 }} />
                <IconButton size="small" color="error" onClick={() => deleteRule(r.id)}>
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Stack>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{t("analytics.addRule")}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              select
              label={t("playback.camera")}
              value={form.camera}
              onChange={(e) => setForm({ ...form, camera: e.target.value })}
            >
              {(cameras || []).map((c) => (
                <MenuItem key={c.id} value={c.id}>
                  {c.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label={t("analytics.ruleType")}
              value={form.kind}
              onChange={(e) => setForm({ ...form, kind: e.target.value })}
            >
              {["alpr", "object", "motion", "fire", "smoke", "tripwire"].map((k) => (
                <MenuItem key={k} value={k}>
                  {t(`analytics.kind.${k}`)}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              type="number"
              label={t("analytics.interval")}
              value={form.interval_seconds}
              onChange={(e) => setForm({ ...form, interval_seconds: Number(e.target.value) })}
            />
            {form.camera &&
              cameras?.find((c) => c.id === Number(form.camera))?.record_mode === "off" && (
                <Typography variant="caption" color="warning.main">
                  {t("analytics.notRecordingWarning")}
                </Typography>
              )}
            {form.kind === "tripwire" && (
              <LineEditor cameraId={form.camera ? Number(form.camera) : null} line={line} onChange={setLine} />
            )}
            {(form.kind === "fire" || form.kind === "smoke") && (
              <Typography variant="caption" color="text.secondary">
                {t("analytics.demoNote")}
              </Typography>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
          <Button
            variant="contained"
            onClick={save}
            disabled={!form.camera || (form.kind === "tripwire" && line.length !== 2)}
          >
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

function PlateReadsTab() {
  const { t } = useTranslation();
  const { data } = usePlateReadsQuery();
  const columns: GridColDef[] = [
    {
      field: "plate",
      headerName: t("analytics.plate"),
      width: 160,
      renderCell: (p) => (
        <Chip
          label={p.value}
          color={p.row.watchlist_hit ? "error" : "default"}
          sx={{ fontFamily: "monospace", fontWeight: 700 }}
        />
      ),
    },
    { field: "camera_name", headerName: t("playback.camera"), flex: 1 },
    {
      field: "confidence",
      headerName: t("analytics.confidence"),
      width: 120,
      valueFormatter: (v: number) => `${toFa(Math.round((v || 0) * 100))}٪`,
    },
    { field: "country", headerName: t("analytics.country"), width: 100 },
    {
      field: "ts",
      headerName: t("events.time"),
      width: 180,
      valueFormatter: (v: string) => formatDateTime(v),
    },
  ];
  return (
    <Card sx={{ border: "1px solid #2b3a4f" }}>
      <DataGrid autoHeight rows={data || []} columns={columns} sx={{ border: 0 }} />
    </Card>
  );
}

function ObjectsTab() {
  const { t } = useTranslation();
  const { data } = useObjectDetectionsQuery();
  const columns: GridColDef[] = [
    { field: "label", headerName: t("analytics.label"), width: 160 },
    { field: "camera_name", headerName: t("playback.camera"), flex: 1 },
    {
      field: "confidence",
      headerName: t("analytics.confidence"),
      width: 120,
      valueFormatter: (v: number) => `${toFa(Math.round((v || 0) * 100))}٪`,
    },
    {
      field: "ts",
      headerName: t("events.time"),
      width: 180,
      valueFormatter: (v: string) => formatDateTime(v),
    },
  ];
  return (
    <Card sx={{ border: "1px solid #2b3a4f" }}>
      <DataGrid autoHeight rows={data || []} columns={columns} sx={{ border: 0 }} />
    </Card>
  );
}

function WatchlistTab() {
  const { t } = useTranslation();
  const { data } = usePlateWatchlistQuery();
  const [create] = useCreateWatchlistItemMutation();
  const [remove] = useDeleteWatchlistItemMutation();
  const [plate, setPlate] = useState("");
  const [reason, setReason] = useState("");

  return (
    <Box>
      <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
        <TextField
          size="small"
          label={t("analytics.plate")}
          value={plate}
          onChange={(e) => setPlate(e.target.value)}
        />
        <TextField
          size="small"
          label={t("analytics.reason")}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <Button
          variant="contained"
          disabled={!plate}
          onClick={() => {
            create({ plate, reason, active: true });
            setPlate("");
            setReason("");
          }}
        >
          {t("common.save")}
        </Button>
      </Stack>
      <Grid container spacing={1}>
        {(data || []).map((w) => (
          <Grid item key={w.id}>
            <Chip
              color="error"
              label={`${w.plate} — ${w.reason}`}
              onDelete={() => remove(w.id)}
              sx={{ fontFamily: "monospace" }}
            />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}

/**
 * Tripwire line editor: shows a live snapshot of the camera; two clicks set
 * the virtual line's endpoints (stored normalized 0..1).
 */
function LineEditor({
  cameraId,
  line,
  onChange,
}: {
  cameraId: number | null;
  line: number[][];
  onChange: (l: number[][]) => void;
}) {
  const { t } = useTranslation();
  const snapshot = useSnapshotUrl(cameraId);

  const click = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    if (line.length >= 2) onChange([[x, y]]);
    else onChange([...line, [x, y]]);
  };

  if (!cameraId)
    return (
      <Typography variant="caption" color="text.secondary">
        {t("analytics.pickCameraFirst")}
      </Typography>
    );

  return (
    <Box>
      <Stack direction="row" alignItems="center" sx={{ mb: 0.5 }}>
        <Typography variant="subtitle2">{t("analytics.drawLine")}</Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Button size="small" onClick={() => onChange([])}>
          {t("analytics.clearLine")}
        </Button>
      </Stack>
      <Box
        onClick={click}
        sx={{
          position: "relative",
          borderRadius: 2,
          overflow: "hidden",
          border: "1px solid #33415a",
          cursor: "crosshair",
          aspectRatio: "16/9",
          bgcolor: "#05070a",
        }}
      >
        {snapshot && (
          <img
            src={snapshot}
            alt=""
            style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
          />
        )}
        <svg
          viewBox="0 0 100 56.25"
          preserveAspectRatio="none"
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
        >
          {line.length === 2 && (
            <line
              x1={line[0][0] * 100}
              y1={line[0][1] * 56.25}
              x2={line[1][0] * 100}
              y2={line[1][1] * 56.25}
              stroke="#ff5a5f"
              strokeWidth="1.2"
              strokeDasharray="3 1.5"
            />
          )}
          {line.map((p, i) => (
            <circle key={i} cx={p[0] * 100} cy={p[1] * 56.25} r="1.6" fill="#ff5a5f" />
          ))}
        </svg>
      </Box>
      <Typography variant="caption" color="text.secondary">
        {line.length === 2 ? t("analytics.lineSet") : t("analytics.lineHint")}
      </Typography>
    </Box>
  );
}

/** Motion heatmap: snapshot background + red intensity grid overlay. */
function HeatmapTab() {
  const { t } = useTranslation();
  const { data: cameras } = useCamerasQuery();
  const [camera, setCamera] = useState<number | "">("");
  const [days, setDays] = useState(7);
  const snapshot = useSnapshotUrl(camera ? Number(camera) : null);
  const { data: hm } = useMotionHeatmapQuery(
    { camera: Number(camera), days },
    { skip: !camera, pollingInterval: 60000 }
  );

  return (
    <Box>
      <Stack direction="row" spacing={2} sx={{ mb: 2 }} alignItems="center" flexWrap="wrap">
        <TextField
          select
          size="small"
          label={t("playback.camera")}
          value={camera}
          onChange={(e) => setCamera(Number(e.target.value))}
          sx={{ minWidth: 200 }}
        >
          {(cameras || []).map((c) => (
            <MenuItem key={c.id} value={c.id}>
              {c.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label={t("analytics.range")}
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          sx={{ minWidth: 140 }}
        >
          {[1, 7, 30].map((d) => (
            <MenuItem key={d} value={d}>
              {toFa(d)} {t("analytics.days")}
            </MenuItem>
          ))}
        </TextField>
        {hm && (
          <Chip
            size="small"
            variant="outlined"
            label={`${t("analytics.samples")}: ${toFa(hm.samples)}`}
          />
        )}
      </Stack>

      {camera ? (
        <Card sx={{ p: 1, maxWidth: 960 }}>
          <Box
            sx={{
              position: "relative",
              aspectRatio: "16/9",
              borderRadius: 2,
              overflow: "hidden",
              bgcolor: "#05070a",
            }}
          >
            {snapshot && (
              <img
                src={snapshot}
                alt=""
                style={{
                  position: "absolute",
                  inset: 0,
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  filter: "grayscale(35%) brightness(0.75)",
                }}
              />
            )}
            {hm && hm.max > 0 && (
              <Box
                sx={{
                  position: "absolute",
                  inset: 0,
                  display: "grid",
                  gridTemplateColumns: `repeat(${hm.w}, 1fr)`,
                  gridTemplateRows: `repeat(${hm.h}, 1fr)`,
                }}
              >
                {hm.grid.flatMap((row, y) =>
                  row.map((v, x) => {
                    const a = v / hm.max;
                    return (
                      <Box
                        key={`${x}-${y}`}
                        sx={{
                          background:
                            a > 0.02
                              ? `rgba(255, ${Math.round(150 - a * 130)}, 0, ${Math.min(0.78, a)})`
                              : "transparent",
                        }}
                      />
                    );
                  })
                )}
              </Box>
            )}
            {hm && hm.max === 0 && (
              <Stack sx={{ position: "absolute", inset: 0 }} alignItems="center" justifyContent="center">
                <Typography color="text.secondary">{t("analytics.noHeat")}</Typography>
              </Stack>
            )}
          </Box>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1, px: 0.5 }}>
            <Typography variant="caption" color="text.secondary">
              {t("analytics.low")}
            </Typography>
            <Box
              sx={{
                flexGrow: 1,
                height: 8,
                borderRadius: 4,
                background: "linear-gradient(90deg, rgba(255,150,0,0.15), rgba(255,60,0,0.8))",
              }}
            />
            <Typography variant="caption" color="text.secondary">
              {t("analytics.high")}
            </Typography>
          </Stack>
        </Card>
      ) : (
        <Typography color="text.secondary">{t("analytics.pickCameraFirst")}</Typography>
      )}
    </Box>
  );
}
