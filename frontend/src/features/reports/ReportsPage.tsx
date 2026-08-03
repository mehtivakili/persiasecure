import { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Grid,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import AssessmentIcon from "@mui/icons-material/Assessment";
import { useTranslation } from "react-i18next";

import { useCamerasQuery } from "../../api/endpoints";
import { useAppSelector } from "../../app/hooks";
import JalaliDatePicker from "../../components/JalaliDatePicker";
import { authedDownload } from "../../utils/download";

const KINDS = ["events", "access", "plates"] as const;

export default function ReportsPage() {
  const { t } = useTranslation();
  const { data: cameras } = useCamerasQuery();
  const token = useAppSelector((s) => s.auth.access);
  const today = new Date().toISOString().slice(0, 10);
  const weekAgo = new Date(Date.now() - 7 * 86400e3).toISOString().slice(0, 10);
  const [kind, setKind] = useState<(typeof KINDS)[number]>("events");
  const [from, setFrom] = useState(weekAgo);
  const [to, setTo] = useState(today);
  const [camera, setCamera] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const download = async () => {
    setBusy(true);
    setError("");
    try {
      const params = new URLSearchParams({
        after: new Date(from + "T00:00:00").toISOString(),
        before: new Date(to + "T23:59:59").toISOString(),
      });
      if (camera) params.set("camera", camera);
      await authedDownload(`/api/reports/${kind}?${params}`, `${kind}.csv`, token);
    } catch {
      setError(t("reports.failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        {t("reports.title")}
      </Typography>

      <Grid container spacing={2}>
        {KINDS.map((k) => (
          <Grid item xs={12} sm={4} key={k}>
            <Card
              onClick={() => setKind(k)}
              sx={{
                cursor: "pointer",
                border: kind === k ? "2px solid #3aa0ff" : undefined,
              }}
            >
              <CardContent sx={{ textAlign: "center" }}>
                <AssessmentIcon color={kind === k ? "primary" : "disabled"} sx={{ fontSize: 40 }} />
                <Typography variant="h6">{t(`reports.kinds.${k}`)}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {t(`reports.desc.${k}`)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Card sx={{ mt: 2 }}>
        <CardContent>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
            <JalaliDatePicker label={t("reports.from")} value={from} onChange={(d) => d && setFrom(d)} />
            <JalaliDatePicker label={t("reports.to")} value={to} onChange={(d) => d && setTo(d)} />
            <TextField
              select
              size="small"
              label={t("playback.camera")}
              value={camera}
              onChange={(e) => setCamera(e.target.value)}
              sx={{ minWidth: 200 }}
            >
              <MenuItem value="">{t("automation.anyCamera")}</MenuItem>
              {(cameras || []).map((c) => (
                <MenuItem key={c.id} value={String(c.id)}>
                  {c.name}
                </MenuItem>
              ))}
            </TextField>
            <Box sx={{ flexGrow: 1 }} />
            <Button
              variant="contained"
              size="large"
              startIcon={<DownloadIcon />}
              onClick={download}
              disabled={busy}
            >
              {t("reports.download")}
            </Button>
          </Stack>
          {error && (
            <Typography color="error" variant="body2" sx={{ mt: 1 }}>
              {error}
            </Typography>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
