import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Grid,
  LinearProgress,
  MenuItem,
  Stack,
  Step,
  StepLabel,
  Stepper,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import TravelExploreIcon from "@mui/icons-material/TravelExplore";
import WifiFindIcon from "@mui/icons-material/WifiFind";
import { useTranslation } from "react-i18next";

import {
  useCameraBrandsQuery,
  useCreateCameraMutation,
  useOnvifProbeMutation,
  useSchedulesQuery,
  useTestConnectionMutation,
  useUpdateCameraMutation,
} from "../../api/endpoints";
import type { Camera, ProbeResult, WeeklyWindows } from "../../api/types";
import VideoPlayer from "../../components/VideoPlayer";
import WeeklyScheduleEditor from "./WeeklyScheduleEditor";

interface Props {
  open: boolean;
  camera: Camera | null;
  onClose: () => void;
}

const emptyForm = {
  name: "",
  location: "",
  rtsp_url: "",
  host: "",
  port: 554,
  path: "/",
  username: "",
  password: "",
  onvif_host: "",
  onvif_port: 80,
  manufacturer: "",
  enabled: true,
  ptz_enabled: false,
};

// Main-stream video codec. h265 (incl. Hikvision/Dahua "H.265+") is recorded
// natively for the storage savings, and transcoded on demand for browser view.
const CODECS = ["h264", "h265"] as const;
const RECORD_MODES = ["off", "continuous", "motion", "scheduled"] as const;

// Wizard step keys (i18n under cameras.steps.*).
const STEP_KEYS = ["connection", "test", "stream", "recording", "review"] as const;

export default function CameraDialog({ open, camera, onClose }: Props) {
  const { t } = useTranslation();
  const [activeStep, setActiveStep] = useState(0);
  const [form, setForm] = useState<any>(emptyForm);
  const [codec, setCodec] = useState<string>("h264");
  const [brand, setBrand] = useState<string>("onvif");
  const [channel, setChannel] = useState<number>(1);
  const [recordMode, setRecordMode] = useState("off");
  const [retention, setRetention] = useState(14);
  const [weekly, setWeekly] = useState<WeeklyWindows>({});
  const [testResult, setTestResult] = useState<ProbeResult | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedCamera, setSavedCamera] = useState<Camera | null>(null);
  const { data: brands } = useCameraBrandsQuery();

  const [createCamera, { isLoading: creating }] = useCreateCameraMutation();
  const [updateCamera, { isLoading: updating }] = useUpdateCameraMutation();
  const [testConnection, { isLoading: testing }] = useTestConnectionMutation();
  const [onvifProbe, { isLoading: probing }] = useOnvifProbeMutation();
  const { data: schedules } = useSchedulesQuery();

  useEffect(() => {
    if (!open) return;
    if (camera) {
      setForm({ ...emptyForm, ...camera, password: "" });
      const main = camera.stream_profiles?.find((p) => p.kind === "main");
      setCodec(main?.codec || "h264");
      const sched = schedules?.find((s) => s.camera === camera.id);
      setRecordMode(camera.record_mode || sched?.mode || "off");
      setRetention(sched?.retention_days || 14);
      setWeekly((sched?.weekly as WeeklyWindows) || {});
    } else {
      setForm(emptyForm);
      setCodec("h264");
      setRecordMode("off");
      setRetention(14);
      setWeekly({});
    }
    setActiveStep(0);
    setTestResult(null);
    setSaveError(null);
    setSavedCamera(null);
  }, [camera, open, schedules]);

  const set = (k: string, v: any) => setForm((f: any) => ({ ...f, [k]: v }));

  /** Applying a brand fills in that vendor's stream path + default ports. */
  const applyBrand = (brandId: string, ch: number) => {
    const b = brands?.find((x) => x.id === brandId);
    if (!b) return;
    setForm((f: any) => ({
      ...f,
      port: b.rtsp_port,
      onvif_port: b.onvif_port,
      manufacturer: b.id === "custom" || b.id === "onvif" ? f.manufacturer : b.label,
      path: b.main ? b.main.replace("{ch}", String(ch)) : f.path,
      rtsp_url: b.main ? "" : f.rtsp_url,
    }));
  };

  const connectionBody = () => {
    const body: any = { ...form };
    if (!body.password) delete body.password;
    if (body.host) body.rtsp_url = "";
    return body;
  };

  const doProbe = async () => {
    try {
      const r = await onvifProbe({
        host: form.onvif_host || form.host,
        port: form.onvif_port,
        username: form.username,
        password: form.password,
      }).unwrap();
      if (r.rtsp_url) {
        try {
          const parsed = new URL(r.rtsp_url);
          set("host", parsed.hostname);
          set("port", Number(parsed.port) || 554);
          set("path", `${parsed.pathname || "/"}${parsed.search || ""}`);
          set("rtsp_url", "");
        } catch {
          set("rtsp_url", r.rtsp_url);
        }
      }
      if (r.info?.manufacturer) set("manufacturer", r.info.manufacturer);
    } catch {
      setSaveError(t("cameras.probe.forbidden"));
    }
  };

  const runTest = async () => {
    setTestResult(null);
    const body: any = { ...connectionBody(), rtsp_transport: "tcp" };
    if (camera) body.camera = camera.id; // reuse stored password on edit
    try {
      const r = await testConnection(body).unwrap();
      setTestResult(r);
      // Auto-detect the stream codec so the next step is pre-filled.
      if (r.reachable && r.codec) {
        setCodec(r.codec === "hevc" || r.codec === "h265" ? "h265" : "h264");
      }
    } catch (e: any) {
      setTestResult({
        ok: false,
        reachable: false,
        reason: e?.data?.reason || "unknown",
        detail: e?.data?.detail,
      });
    }
  };

  const save = async () => {
    setSaveError(null);
    const body: any = connectionBody();
    const main = camera?.stream_profiles?.find((p) => p.kind === "main");
    body.stream_profiles = [
      {
        kind: "main",
        codec,
        resolution: main?.resolution || "1280x720",
        fps: main?.fps ?? 25,
        bitrate_kbps: main?.bitrate_kbps ?? 0,
        rtsp_transport: main?.rtsp_transport || "tcp",
      },
    ];
    // Recording policy travels WITH the camera so the backend creates the
    // camera and its schedule atomically (fixes the "new camera ignores record
    // mode" bug). Weekly windows are only meaningful for scheduled mode.
    body.recording = {
      mode: recordMode,
      retention_days: retention,
      ...(recordMode === "scheduled" ? { weekly } : {}),
    };
    try {
      const saved = camera
        ? await updateCamera({ id: camera.id, body }).unwrap()
        : await createCamera(body).unwrap();
      setSavedCamera(saved);
    } catch (error: any) {
      const data = error?.data;
      if (data?.organization) setSaveError(String(data.organization));
      else if (data?.detail) setSaveError(String(data.detail));
      else if (error?.status) setSaveError(t("cameras.saveFailedCode", { code: error.status }));
      else setSaveError(t("cameras.saveFailed"));
    }
  };

  const canGoNext = useMemo(() => {
    if (activeStep === 0) return Boolean(form.name && (form.host || form.rtsp_url));
    return true;
  }, [activeStep, form.name, form.host, form.rtsp_url]);

  const isLast = activeStep === STEP_KEYS.length - 1;
  const busy = creating || updating;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{camera ? t("cameras.edit") : t("cameras.add")}</DialogTitle>
      <DialogContent dividers>
        <Stepper activeStep={activeStep} sx={{ mb: 3 }} alternativeLabel>
          {STEP_KEYS.map((key) => (
            <Step key={key}>
              <StepLabel>{t(`cameras.steps.${key}`)}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {activeStep === 0 && (
          <ConnectionStep
            form={form}
            set={set}
            brand={brand}
            setBrand={setBrand}
            channel={channel}
            setChannel={setChannel}
            applyBrand={applyBrand}
            brands={brands}
            doProbe={doProbe}
            probing={probing}
            t={t}
          />
        )}

        {activeStep === 1 && (
          <TestStep testResult={testResult} testing={testing} runTest={runTest} t={t} />
        )}

        {activeStep === 2 && (
          <StreamStep codec={codec} setCodec={setCodec} testResult={testResult} t={t} />
        )}

        {activeStep === 3 && (
          <RecordingStep
            recordMode={recordMode}
            setRecordMode={setRecordMode}
            retention={retention}
            setRetention={setRetention}
            weekly={weekly}
            setWeekly={setWeekly}
            form={form}
            set={set}
            t={t}
          />
        )}

        {activeStep === 4 && (
          <ReviewStep
            form={form}
            codec={codec}
            recordMode={recordMode}
            retention={retention}
            testResult={testResult}
            savedCamera={savedCamera}
            saveError={saveError}
            t={t}
          />
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>
          {savedCamera ? t("common.close") : t("cameras.cancel")}
        </Button>
        <Box sx={{ flexGrow: 1 }} />
        {activeStep > 0 && !savedCamera && (
          <Button onClick={() => setActiveStep((s) => s - 1)} disabled={busy}>
            {t("common.back")}
          </Button>
        )}
        {!isLast && (
          <Button
            variant="contained"
            onClick={() => setActiveStep((s) => s + 1)}
            disabled={!canGoNext}
          >
            {t("common.next")}
          </Button>
        )}
        {isLast && !savedCamera && (
          <Button variant="contained" onClick={save} disabled={busy}>
            {t("cameras.save")}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Steps
// ---------------------------------------------------------------------------

type StepProps = { t: any };

function ConnectionStep({
  form, set, brand, setBrand, channel, setChannel, applyBrand, brands, doProbe, probing, t,
}: any) {
  return (
    <Grid container spacing={2}>
      <Grid item xs={12} sm={6}>
        <TextField label={t("cameras.name")} value={form.name}
          onChange={(e) => set("name", e.target.value)} fullWidth required />
      </Grid>
      <Grid item xs={12} sm={6}>
        <TextField label={t("cameras.location")} value={form.location}
          onChange={(e) => set("location", e.target.value)} fullWidth />
      </Grid>
      <Grid item xs={12} sm={6}>
        <TextField select label={t("cameras.brand")} value={brand}
          onChange={(e) => { setBrand(e.target.value); applyBrand(e.target.value, channel); }} fullWidth>
          {(brands || []).map((b: any) => (
            <MenuItem key={b.id} value={b.id}>{b.label}</MenuItem>
          ))}
        </TextField>
      </Grid>
      <Grid item xs={6} sm={3}>
        <TextField type="number" label={t("cameras.channel")} value={channel}
          onChange={(e) => { const ch = Math.max(1, Number(e.target.value) || 1); setChannel(ch); applyBrand(brand, ch); }}
          fullWidth />
      </Grid>
      <Grid item xs={12}>
        <Typography variant="caption" color="text.secondary">
          {brands?.find((b: any) => b.id === brand)?.note || t("cameras.brandHint")}
        </Typography>
      </Grid>

      <Grid item xs={12}>
        <TextField label={t("cameras.rtspUrl")} placeholder="rtsp://user:pass@host:554/stream"
          value={form.rtsp_url} onChange={(e) => set("rtsp_url", e.target.value)} fullWidth dir="ltr"
          helperText={t("cameras.rtspUrlHint")} />
      </Grid>
      <Grid item xs={6} sm={4}>
        <TextField label={t("cameras.host")} value={form.host}
          onChange={(e) => set("host", e.target.value)} fullWidth dir="ltr" />
      </Grid>
      <Grid item xs={6} sm={2}>
        <TextField label={t("cameras.port")} type="number" value={form.port}
          onChange={(e) => set("port", Number(e.target.value))} fullWidth />
      </Grid>
      <Grid item xs={12} sm={6}>
        <TextField label={t("cameras.path")} value={form.path}
          onChange={(e) => set("path", e.target.value)} fullWidth dir="ltr" />
      </Grid>
      <Grid item xs={12} sm={6}>
        <TextField label={t("cameras.username")} value={form.username}
          onChange={(e) => set("username", e.target.value)} fullWidth dir="ltr" />
      </Grid>
      <Grid item xs={12} sm={6}>
        <TextField label={t("cameras.password")} type="password" value={form.password}
          onChange={(e) => set("password", e.target.value)} fullWidth dir="ltr"
          helperText={t("cameras.passwordEditHint")} />
      </Grid>

      <Grid item xs={12}>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 1 }}>{t("cameras.onvif")}</Typography>
      </Grid>
      <Grid item xs={6} sm={4}>
        <TextField label="ONVIF host" value={form.onvif_host}
          onChange={(e) => set("onvif_host", e.target.value)} fullWidth dir="ltr" />
      </Grid>
      <Grid item xs={6} sm={2}>
        <TextField label="ONVIF port" type="number" value={form.onvif_port}
          onChange={(e) => set("onvif_port", Number(e.target.value))} fullWidth />
      </Grid>
      <Grid item xs={12} sm={6}>
        <Button variant="outlined" startIcon={<WifiFindIcon />} onClick={doProbe} disabled={probing} sx={{ mt: 1 }}>
          {t("cameras.onvifProbe")}
        </Button>
      </Grid>
    </Grid>
  );
}

function TestStep({ testResult, testing, runTest, t }: {
  testResult: ProbeResult | null; testing: boolean; runTest: () => void; } & StepProps) {
  return (
    <Stack spacing={2} alignItems="flex-start">
      <Typography variant="body2" color="text.secondary">{t("cameras.testIntro")}</Typography>
      <Button variant="contained" startIcon={<TravelExploreIcon />} onClick={runTest} disabled={testing}>
        {t("cameras.test")}
      </Button>
      {testing && <Box sx={{ width: "100%" }}><LinearProgress /></Box>}
      {testResult && !testing && <ProbeResultAlert result={testResult} t={t} />}
    </Stack>
  );
}

function ProbeResultAlert({ result, t }: { result: ProbeResult } & StepProps) {
  if (result.reachable && result.ok) {
    return (
      <Alert severity="success" icon={<CheckCircleIcon />} sx={{ width: "100%" }}>
        <AlertTitle>{t("cameras.reachable")}</AlertTitle>
        {t("cameras.detectedCodec", { codec: (result.codec || "").toUpperCase() })}
        {result.width ? ` — ${result.width}×${result.height}` : ""}
      </Alert>
    );
  }
  const severity = result.reason === "unsupported_codec" ? "warning" : "error";
  return (
    <Alert severity={severity} icon={<ErrorOutlineIcon />} sx={{ width: "100%" }}>
      <AlertTitle>{t(`cameras.probe.${result.reason}`)}</AlertTitle>
      {result.reason === "unsupported_codec" && result.codec
        ? t("cameras.unsupportedCodecDetail", { codec: (result.codec || "").toUpperCase() })
        : t("cameras.probeHelp")}
      {result.detail ? (
        <Box component="pre" dir="ltr" sx={{ mt: 1, fontSize: 11, whiteSpace: "pre-wrap", opacity: 0.8 }}>
          {result.detail}
        </Box>
      ) : null}
    </Alert>
  );
}

function StreamStep({ codec, setCodec, testResult, t }: {
  codec: string; setCodec: (v: string) => void; testResult: ProbeResult | null; } & StepProps) {
  return (
    <Grid container spacing={2}>
      {testResult?.codec && (
        <Grid item xs={12}>
          <Alert severity="info">{t("cameras.detectedCodec", { codec: testResult.codec.toUpperCase() })}</Alert>
        </Grid>
      )}
      <Grid item xs={12} sm={6}>
        <TextField select label={t("cameras.videoCodec")} value={codec}
          onChange={(e) => setCodec(e.target.value)} fullWidth>
          {CODECS.map((c) => (<MenuItem key={c} value={c}>{t(`cameras.codecs.${c}`)}</MenuItem>))}
        </TextField>
      </Grid>
      <Grid item xs={12} sm={6}>
        <Typography variant="caption" color="text.secondary">
          {codec === "h265" ? t("cameras.h265Hint") : t("cameras.h264Hint")}
        </Typography>
      </Grid>
    </Grid>
  );
}

function RecordingStep({
  recordMode, setRecordMode, retention, setRetention, weekly, setWeekly, form, set, t,
}: any) {
  return (
    <Grid container spacing={2}>
      <Grid item xs={12} sm={6}>
        <TextField select label={t("cameras.recordMode")} value={recordMode}
          onChange={(e) => setRecordMode(e.target.value)} fullWidth>
          {RECORD_MODES.map((m) => (<MenuItem key={m} value={m}>{t(`recordModes.${m}`)}</MenuItem>))}
        </TextField>
      </Grid>
      <Grid item xs={12} sm={6}>
        <TextField label={t("cameras.retention")} type="number" value={retention}
          onChange={(e) => setRetention(Number(e.target.value))} fullWidth
          inputProps={{ min: 1, max: 3650 }} />
      </Grid>
      {recordMode === "motion" && (
        <Grid item xs={12}>
          <Alert severity="info">{t("cameras.motionBufferNote")}</Alert>
        </Grid>
      )}
      {recordMode === "scheduled" && (
        <Grid item xs={12}>
          <WeeklyScheduleEditor value={weekly} onChange={setWeekly} />
        </Grid>
      )}
      <Grid item xs={12}>
        <Stack direction="row" spacing={3} alignItems="center">
          <FormControlLabel control={<Switch checked={form.enabled}
            onChange={(e) => set("enabled", e.target.checked)} />} label={t("cameras.enabled")} />
          <FormControlLabel control={<Switch checked={form.ptz_enabled}
            onChange={(e) => set("ptz_enabled", e.target.checked)} />} label={t("cameras.ptzEnabled")} />
        </Stack>
      </Grid>
    </Grid>
  );
}

function ReviewStep({ form, codec, recordMode, retention, testResult, savedCamera, saveError, t }: any) {
  if (savedCamera) {
    return (
      <Stack spacing={2}>
        <Alert severity="success" icon={<CheckCircleIcon />}>
          <AlertTitle>{t("cameras.savedTitle")}</AlertTitle>
          {t("cameras.savedBody")}
        </Alert>
        <Typography variant="subtitle2">{t("cameras.livePreview")}</Typography>
        <Box sx={{ height: 300, bgcolor: "#000", borderRadius: 2, overflow: "hidden" }}>
          {savedCamera.playback ? (
            <VideoPlayer playback={savedCamera.playback} label={savedCamera.name} />
          ) : null}
        </Box>
        <Typography variant="caption" color="text.secondary">{t("cameras.livePreviewHint")}</Typography>
      </Stack>
    );
  }
  return (
    <Stack spacing={1.5}>
      <Typography variant="subtitle2">{t("cameras.reviewTitle")}</Typography>
      <ReviewRow label={t("cameras.name")} value={form.name} />
      <ReviewRow label={t("cameras.location")} value={form.location || "—"} />
      <ReviewRow label={t("cameras.host")} value={form.host || form.rtsp_url} dir="ltr" />
      <ReviewRow label={t("cameras.videoCodec")} value={codec.toUpperCase()} />
      <ReviewRow label={t("cameras.recordMode")} value={t(`recordModes.${recordMode}`)} />
      <ReviewRow label={t("cameras.retention")} value={String(retention)} />
      <Box>
        {testResult?.reachable ? (
          <Chip color="success" size="small" icon={<CheckCircleIcon />} label={t("cameras.reachable")} />
        ) : (
          <Chip color="warning" size="small" icon={<ErrorOutlineIcon />} label={t("cameras.notTested")} />
        )}
      </Box>
      {saveError && <Alert severity="error">{saveError}</Alert>}
    </Stack>
  );
}

function ReviewRow({ label, value, dir }: { label: string; value: string; dir?: string }) {
  return (
    <Stack direction="row" spacing={2}>
      <Typography variant="body2" color="text.secondary" sx={{ minWidth: 120 }}>{label}</Typography>
      <Typography variant="body2" dir={dir as any} sx={{ fontWeight: 600 }}>{value}</Typography>
    </Stack>
  );
}
