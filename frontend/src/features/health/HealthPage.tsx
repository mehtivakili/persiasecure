import {
  Box,
  Card,
  CardContent,
  Chip,
  Grid,
  LinearProgress,
  Stack,
  Typography,
} from "@mui/material";
import StorageIcon from "@mui/icons-material/Storage";
import DnsIcon from "@mui/icons-material/Dns";
import MemoryIcon from "@mui/icons-material/Memory";
import OndemandVideoIcon from "@mui/icons-material/OndemandVideo";
import TaskAltIcon from "@mui/icons-material/TaskAlt";
import { useTranslation } from "react-i18next";

import { useSystemHealthQuery } from "../../api/endpointsOps";
import { formatBytes, toFa } from "../../utils/format";
import CameraStatusDot from "../cameras/CameraStatusDot";

const SERVICE_ICONS: Record<string, JSX.Element> = {
  database: <DnsIcon />,
  redis: <MemoryIcon />,
  mediamtx: <OndemandVideoIcon />,
  celery: <TaskAltIcon />,
};

export default function HealthPage() {
  const { t } = useTranslation();
  const { data } = useSystemHealthQuery(undefined, { pollingInterval: 15000 });

  const diskPct = data && data.disk.total > 0 ? (data.disk.used / data.disk.total) * 100 : 0;

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        {t("health.title")}
      </Typography>

      <Grid container spacing={2}>
        {Object.entries(data?.services || {}).map(([name, ok]) => (
          <Grid item xs={6} md={3} key={name}>
            <Card>
              <CardContent>
                <Stack direction="row" alignItems="center" spacing={1.5}>
                  <Box sx={{ color: ok ? "success.main" : "error.main" }}>
                    {SERVICE_ICONS[name]}
                  </Box>
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography variant="subtitle1">{t(`health.services.${name}`)}</Typography>
                    <Chip
                      size="small"
                      color={ok ? "success" : "error"}
                      label={ok ? t("health.ok") : t("health.down")}
                    />
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        ))}

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
                <StorageIcon color="primary" />
                <Typography variant="h6">{t("health.storage")}</Typography>
              </Stack>
              <LinearProgress
                variant="determinate"
                value={Math.min(diskPct, 100)}
                color={diskPct > 90 ? "error" : diskPct > 75 ? "warning" : "primary"}
                sx={{ height: 10, borderRadius: 5, mb: 1 }}
              />
              <Typography variant="body2" color="text.secondary">
                {t("health.used")}: {formatBytes(data?.disk.used || 0)} /{" "}
                {formatBytes(data?.disk.total || 0)} — {t("health.free")}:{" "}
                {formatBytes(data?.disk.free || 0)}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {t("health.recordings")}: {toFa(data?.recordings.count || 0)} (
                {formatBytes(data?.recordings.bytes || 0)})
              </Typography>
              <Stack direction="row" spacing={1} sx={{ mt: 1.5 }} flexWrap="wrap" useFlexGap>
                <Chip
                  size="small"
                  color={data?.projected_days != null && data.projected_days < 7 ? "warning" : "default"}
                  label={`${t("health.projectedDays")}: ${data?.projected_days != null ? toFa(data.projected_days) : "—"}`}
                />
                <Chip
                  size="small"
                  color={data?.recording_delay_seconds != null && data.recording_delay_seconds > 300 ? "error" : "default"}
                  label={`${t("health.recordingDelay")}: ${
                    data?.recording_delay_seconds != null ? `${toFa(data.recording_delay_seconds)}s` : "—"
                  }`}
                />
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        {!!data?.storage_by_camera?.length && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 1 }}>{t("health.storageByCamera")}</Typography>
                <Stack spacing={1}>
                  {data.storage_by_camera.slice(0, 12).map((c) => {
                    const max = data.storage_by_camera[0]?.bytes || 1;
                    return (
                      <Box key={c.camera}>
                        <Stack direction="row" alignItems="center" spacing={1}>
                          <Typography variant="body2" sx={{ minWidth: 140 }}>{c.name}</Typography>
                          <LinearProgress
                            variant="determinate"
                            value={Math.min((c.bytes / max) * 100, 100)}
                            sx={{ flexGrow: 1, height: 8, borderRadius: 4 }}
                          />
                          <Typography variant="caption" color="text.secondary" sx={{ minWidth: 80, textAlign: "end" }}>
                            {formatBytes(c.bytes)}
                          </Typography>
                        </Stack>
                      </Box>
                    );
                  })}
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        )}

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 1 }}>
                {t("dashboard.cameraStatus")}
              </Typography>
              <Stack spacing={1}>
                {Object.entries(data?.cameras || {}).map(([status, count]) => (
                  <Stack key={status} direction="row" alignItems="center">
                    <CameraStatusDot status={status} />
                    <Typography sx={{ flexGrow: 1 }}>{t(`status.${status}`)}</Typography>
                    <Chip size="small" label={toFa(count)} />
                  </Stack>
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
