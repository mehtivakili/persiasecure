import { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
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
  TextField,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import BoltIcon from "@mui/icons-material/Bolt";
import { useTranslation } from "react-i18next";

import {
  useAutomationRulesQuery,
  useCreateAutomationRuleMutation,
  useDeleteAutomationRuleMutation,
  useUpdateAutomationRuleMutation,
} from "../../api/endpointsOps";
import { useCamerasQuery } from "../../api/endpoints";
import { useDoorsQuery } from "../../api/endpointsPhase2";
import { formatDateTime, toFa } from "../../utils/format";

const EVENT_TYPES = ["", "motion", "tripwire", "fire", "smoke", "alpr", "object", "offline", "tamper", "manual"];
const ACTIONS = ["send_sms", "voice_call", "webhook", "unlock_door", "lock_door", "set_threat"] as const;

export default function AutomationPage() {
  const { t } = useTranslation();
  const { data: rules } = useAutomationRulesQuery();
  const { data: cameras } = useCamerasQuery();
  const { data: doors } = useDoorsQuery();
  const [createRule] = useCreateAutomationRuleMutation();
  const [updateRule] = useUpdateAutomationRuleMutation();
  const [deleteRule] = useDeleteAutomationRuleMutation();

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<any>({
    name: "",
    event_type: "",
    min_severity: "info",
    camera: "",
    action: "webhook",
    params: {},
  });
  const set = (k: string, v: any) => setForm((f: any) => ({ ...f, [k]: v }));
  const setParam = (k: string, v: any) =>
    setForm((f: any) => ({ ...f, params: { ...f.params, [k]: v } }));

  const save = async () => {
    const body: any = { ...form, camera: form.camera === "" ? null : Number(form.camera) };
    await createRule(body);
    setOpen(false);
    setForm({ name: "", event_type: "", min_severity: "info", camera: "", action: "webhook", params: {} });
  };

  const triggerSummary = (r: any) =>
    `${r.event_type ? t(`eventTypes.${r.event_type}`) : t("automation.anyEvent")} · ${t(
      `severity.${r.min_severity}`
    )}+${r.camera_name ? ` · ${r.camera_name}` : ""}`;

  const actionSummary = (r: any) => {
    if (r.action === "webhook") return `${t("automation.actions.webhook")}: ${r.params?.url || ""}`;
    if (r.action === "set_threat")
      return `${t("automation.actions.set_threat")}: ${t(`threat.${r.params?.level || "green"}`)}`;
    if (r.action === "send_sms" || r.action === "voice_call")
      return `${t(`automation.actions.${r.action}`)}: ${r.params?.phone || ""}`;
    const door = (doors || []).find((d) => d.id === r.params?.door);
    return `${t(`automation.actions.${r.action}`)}: ${door?.name || r.params?.door || ""}`;
  };

  return (
    <Box>
      <Stack direction="row" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h4">{t("automation.title")}</Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)}>
          {t("automation.addRule")}
        </Button>
      </Stack>

      <Grid container spacing={2}>
        {(rules || []).map((r) => (
          <Grid item xs={12} md={6} lg={4} key={r.id}>
            <Card>
              <CardContent>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <BoltIcon color={r.enabled ? "warning" : "disabled"} />
                  <Typography variant="h6" sx={{ flexGrow: 1 }}>
                    {r.name}
                  </Typography>
                  <Switch
                    checked={r.enabled}
                    onChange={(e) => updateRule({ id: r.id, body: { enabled: e.target.checked } })}
                  />
                  <IconButton size="small" color="error" onClick={() => deleteRule(r.id)}>
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Stack>
                <Stack spacing={0.5} sx={{ mt: 1 }}>
                  <Chip size="small" variant="outlined" label={`${t("automation.trigger")}: ${triggerSummary(r)}`} />
                  <Chip size="small" variant="outlined" color="info" label={actionSummary(r)} />
                  <Typography variant="caption" color="text.secondary">
                    {t("automation.runs")}: {toFa(r.run_count)}
                    {r.last_run ? ` — ${formatDateTime(r.last_run)}` : ""}
                  </Typography>
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        ))}
        {!rules?.length && (
          <Grid item xs={12}>
            <Typography color="text.secondary">{t("automation.empty")}</Typography>
          </Grid>
        )}
      </Grid>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{t("automation.addRule")}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label={t("automation.ruleName")} value={form.name} onChange={(e) => set("name", e.target.value)} />
            <Typography variant="subtitle2" color="text.secondary">
              {t("automation.trigger")}
            </Typography>
            <TextField select label={t("events.type")} value={form.event_type} onChange={(e) => set("event_type", e.target.value)}>
              {EVENT_TYPES.map((et) => (
                <MenuItem key={et || "any"} value={et}>
                  {et ? t(`eventTypes.${et}`) : t("automation.anyEvent")}
                </MenuItem>
              ))}
            </TextField>
            <TextField select label={t("events.severity")} value={form.min_severity} onChange={(e) => set("min_severity", e.target.value)}>
              {["info", "warning", "critical"].map((s) => (
                <MenuItem key={s} value={s}>
                  {t(`severity.${s}`)}+
                </MenuItem>
              ))}
            </TextField>
            <TextField select label={t("playback.camera")} value={form.camera} onChange={(e) => set("camera", e.target.value)}>
              <MenuItem value="">{t("automation.anyCamera")}</MenuItem>
              {(cameras || []).map((c) => (
                <MenuItem key={c.id} value={c.id}>
                  {c.name}
                </MenuItem>
              ))}
            </TextField>
            <Typography variant="subtitle2" color="text.secondary">
              {t("automation.action")}
            </Typography>
            <TextField select label={t("automation.action")} value={form.action} onChange={(e) => set("action", e.target.value)}>
              {ACTIONS.map((a) => (
                <MenuItem key={a} value={a}>
                  {t(`automation.actions.${a}`)}
                </MenuItem>
              ))}
            </TextField>
            {form.action === "webhook" && (
              <TextField label="URL" dir="ltr" placeholder="https://example.com/hook" value={form.params.url || ""} onChange={(e) => setParam("url", e.target.value)} />
            )}
            {(form.action === "send_sms" || form.action === "voice_call") && (
              <>
                <TextField
                  label={t("automation.phone")}
                  dir="ltr"
                  placeholder="+98912XXXXXXX"
                  value={form.params.phone || ""}
                  onChange={(e) => setParam("phone", e.target.value)}
                />
                <TextField
                  label={t("automation.message")}
                  multiline
                  rows={2}
                  placeholder={t("automation.messageHint")}
                  value={form.params.message || ""}
                  onChange={(e) => setParam("message", e.target.value)}
                />
              </>
            )}
            {(form.action === "unlock_door" || form.action === "lock_door") && (
              <TextField select label={t("access.door")} value={form.params.door || ""} onChange={(e) => setParam("door", Number(e.target.value))}>
                {(doors || []).map((d) => (
                  <MenuItem key={d.id} value={d.id}>
                    {d.name}
                  </MenuItem>
                ))}
              </TextField>
            )}
            {form.action === "set_threat" && (
              <TextField select label={t("threat.title")} value={form.params.level || "yellow"} onChange={(e) => setParam("level", e.target.value)}>
                {["green", "yellow", "red"].map((l) => (
                  <MenuItem key={l} value={l}>
                    {t(`threat.${l}`)}
                  </MenuItem>
                ))}
              </TextField>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
          <Button variant="contained" onClick={save} disabled={!form.name}>
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
