import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  FormControlLabel,
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
import SaveIcon from "@mui/icons-material/Save";
import SmsIcon from "@mui/icons-material/Sms";
import CallIcon from "@mui/icons-material/Call";
import SendIcon from "@mui/icons-material/Send";
import { useTranslation } from "react-i18next";

import {
  useNotificationSettingsQuery,
  useTestNotificationMutation,
  useUpdateNotificationSettingsMutation,
} from "../../api/endpointsOps";
import type { NotifyRecipient } from "../../api/types";

const PROVIDERS = ["console", "kavenegar", "twilio"] as const;

export default function SettingsPage() {
  const { t } = useTranslation();
  const { data } = useNotificationSettingsQuery();
  const [update, { isLoading: saving }] = useUpdateNotificationSettingsMutation();
  const [testNotify] = useTestNotificationMutation();

  const [form, setForm] = useState<any>(null);
  const [saved, setSaved] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  useEffect(() => {
    if (data) setForm({ ...data, recipients: [...(data.recipients || [])] });
  }, [data]);

  if (!form) return null;
  const set = (k: string, v: any) => setForm((f: any) => ({ ...f, [k]: v }));

  const setRecipient = (i: number, patch: Partial<NotifyRecipient>) =>
    setForm((f: any) => {
      const recipients = [...f.recipients];
      recipients[i] = { ...recipients[i], ...patch };
      return { ...f, recipients };
    });
  const addRecipient = () =>
    set("recipients", [
      ...form.recipients,
      { name: "", phone: "", sms: true, call: false, active: true },
    ]);
  const removeRecipient = (i: number) =>
    set("recipients", form.recipients.filter((_: any, idx: number) => idx !== i));

  const save = async () => {
    await update(form).unwrap();
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const runTest = async (phone: string, channel: "sms" | "call") => {
    setTestResult(null);
    try {
      const res = await testNotify({ phone, channel }).unwrap();
      setTestResult(
        res.ok
          ? t("settings.testOk", { provider: res.provider })
          : t("settings.testFail")
      );
    } catch {
      setTestResult(t("settings.testFail"));
    }
  };

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        {t("settings.title")}
      </Typography>

      <Grid container spacing={2}>
        {/* Recipients panel */}
        <Grid item xs={12} md={7}>
          <Card>
            <CardContent>
              <Stack direction="row" alignItems="center" sx={{ mb: 1 }}>
                <SmsIcon color="primary" sx={{ ml: 1 }} />
                <Typography variant="h6" sx={{ flexGrow: 1 }}>
                  {t("settings.recipients")}
                </Typography>
                <Button size="small" startIcon={<AddIcon />} onClick={addRecipient}>
                  {t("settings.addNumber")}
                </Button>
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {t("settings.recipientsHint")}
              </Typography>

              <Stack spacing={1.5}>
                {form.recipients.map((r: NotifyRecipient, i: number) => (
                  <Box
                    key={i}
                    sx={{
                      p: 1.5,
                      border: "1px solid #243044",
                      borderRadius: 2,
                      bgcolor: "rgba(255,255,255,0.02)",
                    }}
                  >
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems="center">
                      <TextField
                        size="small"
                        label={t("settings.name")}
                        value={r.name}
                        onChange={(e) => setRecipient(i, { name: e.target.value })}
                        sx={{ minWidth: 130 }}
                      />
                      <TextField
                        size="small"
                        label={t("settings.phone")}
                        value={r.phone}
                        dir="ltr"
                        placeholder="+98912XXXXXXX"
                        onChange={(e) => setRecipient(i, { phone: e.target.value })}
                        sx={{ flexGrow: 1, minWidth: 160 }}
                      />
                      <FormControlLabel
                        control={
                          <Switch
                            size="small"
                            checked={r.sms}
                            onChange={(e) => setRecipient(i, { sms: e.target.checked })}
                          />
                        }
                        label={t("settings.sms")}
                      />
                      <FormControlLabel
                        control={
                          <Switch
                            size="small"
                            checked={r.call}
                            onChange={(e) => setRecipient(i, { call: e.target.checked })}
                          />
                        }
                        label={t("settings.call")}
                      />
                      <IconButton size="small" color="error" onClick={() => removeRecipient(i)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Stack>
                    <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                      <Button
                        size="small"
                        variant="text"
                        startIcon={<SendIcon sx={{ fontSize: 16 }} />}
                        disabled={!r.phone}
                        onClick={() => runTest(r.phone, "sms")}
                      >
                        {t("settings.testSms")}
                      </Button>
                      <Button
                        size="small"
                        variant="text"
                        startIcon={<CallIcon sx={{ fontSize: 16 }} />}
                        disabled={!r.phone}
                        onClick={() => runTest(r.phone, "call")}
                      >
                        {t("settings.testCall")}
                      </Button>
                    </Stack>
                  </Box>
                ))}
                {form.recipients.length === 0 && (
                  <Typography variant="body2" color="text.secondary">
                    {t("settings.noNumbers")}
                  </Typography>
                )}
              </Stack>

              {testResult && (
                <Alert
                  severity={testResult.includes("✓") || testResult.startsWith("ارسال") ? "success" : "warning"}
                  sx={{ mt: 2 }}
                  onClose={() => setTestResult(null)}
                >
                  {testResult}
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Provider panel */}
        <Grid item xs={12} md={5}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 0.5 }}>
                {t("settings.provider")}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {t("settings.providerHint")}
              </Typography>

              <Stack spacing={2}>
                <TextField
                  select
                  label={t("settings.provider")}
                  value={form.provider}
                  onChange={(e) => set("provider", e.target.value)}
                  fullWidth
                >
                  {PROVIDERS.map((p) => (
                    <MenuItem key={p} value={p}>
                      {t(`settings.providers.${p}`)}
                    </MenuItem>
                  ))}
                </TextField>

                {form.provider === "console" && (
                  <Alert severity="info">{t("settings.consoleNote")}</Alert>
                )}

                {form.provider === "kavenegar" && (
                  <>
                    <TextField
                      label={t("settings.apiKey")}
                      value={form.kavenegar_api_key}
                      dir="ltr"
                      onChange={(e) => set("kavenegar_api_key", e.target.value)}
                      fullWidth
                    />
                    <TextField
                      label={t("settings.smsSender")}
                      value={form.sms_sender}
                      dir="ltr"
                      placeholder="10004346"
                      onChange={(e) => set("sms_sender", e.target.value)}
                      fullWidth
                    />
                  </>
                )}

                {form.provider === "twilio" && (
                  <>
                    <TextField label="Account SID" value={form.twilio_sid} dir="ltr" onChange={(e) => set("twilio_sid", e.target.value)} fullWidth />
                    <TextField label="Auth Token" value={form.twilio_token} dir="ltr" type="password" onChange={(e) => set("twilio_token", e.target.value)} fullWidth />
                    <TextField label="From number" value={form.twilio_from} dir="ltr" placeholder="+1..." onChange={(e) => set("twilio_from", e.target.value)} fullWidth />
                  </>
                )}
              </Stack>
            </CardContent>
          </Card>

          <Card sx={{ mt: 2 }}>
            <CardContent>
              <Typography variant="subtitle1" sx={{ mb: 1 }}>
                {t("settings.alarmRules")}
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                <Chip color="error" size="small" label={t("eventTypes.fire")} />
                <Chip color="error" size="small" label={t("eventTypes.smoke")} />
                <Chip color="error" size="small" label={t("eventTypes.tripwire")} />
              </Stack>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
                {t("settings.alarmRulesHint")}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Stack direction="row" sx={{ mt: 2 }} alignItems="center" spacing={2}>
        <Button variant="contained" size="large" startIcon={<SaveIcon />} onClick={save} disabled={saving}>
          {t("common.save")}
        </Button>
        {saved && <Chip color="success" label={t("settings.saved")} />}
      </Stack>
    </Box>
  );
}
