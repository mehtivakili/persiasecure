import {
  Box,
  Card,
  CardContent,
  Chip,
  Grid,
  List,
  ListItem,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import VideocamIcon from "@mui/icons-material/Videocam";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CancelIcon from "@mui/icons-material/Cancel";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";
import NotificationsActiveIcon from "@mui/icons-material/NotificationsActive";
import StorageIcon from "@mui/icons-material/Storage";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTranslation } from "react-i18next";

import {
  useCamerasQuery,
  useDashboardSummaryQuery,
  useEventsQuery,
  useEventsTimeseriesQuery,
} from "../../api/endpoints";
import StatCard from "../../components/StatCard";
import SeverityChip from "../events/SeverityChip";
import { formatBytes, formatTime, toFa } from "../../utils/format";
import CameraStatusDot from "../cameras/CameraStatusDot";

export default function DashboardPage() {
  const { t } = useTranslation();
  const { data: summary } = useDashboardSummaryQuery();
  const { data: series } = useEventsTimeseriesQuery();
  const { data: cameras } = useCamerasQuery();
  const { data: events } = useEventsQuery();

  const chartData =
    series?.map((p) => ({
      hour: new Intl.DateTimeFormat("fa-IR", { hour: "2-digit" }).format(
        new Date(p.hour)
      ),
      count: p.count,
    })) || [];

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3 }}>
        {t("dashboard.title")}
      </Typography>

      <Grid container spacing={2} sx={{ mb: 1 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            label={t("dashboard.totalCameras")}
            value={toFa(summary?.cameras.total ?? 0)}
            icon={<VideocamIcon />}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            label={t("dashboard.online")}
            value={toFa(summary?.cameras.online ?? 0)}
            icon={<CheckCircleIcon />}
            color="#3ddc84"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            label={t("dashboard.offline")}
            value={toFa(summary?.cameras.offline ?? 0)}
            icon={<CancelIcon />}
            color="#ff5252"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            label={t("dashboard.recording")}
            value={toFa(summary?.cameras.recording ?? 0)}
            icon={<FiberManualRecordIcon />}
            color="#ffb020"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            label={t("dashboard.events24h")}
            value={toFa(summary?.events_24h ?? 0)}
            icon={<NotificationsActiveIcon />}
            color="#17c3b2"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            label={t("dashboard.unacknowledged")}
            value={toFa(summary?.unacknowledged ?? 0)}
            icon={<NotificationsActiveIcon />}
            color="#ff5252"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            label={t("dashboard.storage")}
            value={formatBytes(summary?.storage_bytes ?? 0)}
            icon={<StorageIcon />}
            color="#9aa7b4"
          />
        </Grid>
      </Grid>

      <Grid container spacing={2} sx={{ mt: 0.5 }}>
        <Grid item xs={12} md={8}>
          <Card sx={{ border: "1px solid #2b3a4f", height: 340 }}>
            <CardContent sx={{ height: "100%" }}>
              <Typography variant="h6" sx={{ mb: 2 }}>
                {t("dashboard.eventsChart")}
              </Typography>
              <ResponsiveContainer width="100%" height="82%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="ev" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2e9bff" stopOpacity={0.6} />
                      <stop offset="100%" stopColor="#2e9bff" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2b3a4f" />
                  <XAxis dataKey="hour" stroke="#9aa7b4" reversed />
                  <YAxis stroke="#9aa7b4" allowDecimals={false} />
                  <RTooltip
                    contentStyle={{
                      background: "#161b22",
                      border: "1px solid #2b3a4f",
                      borderRadius: 8,
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke="#2e9bff"
                    fill="url(#ev)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card sx={{ border: "1px solid #2b3a4f", height: 340, overflow: "auto" }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 1 }}>
                {t("dashboard.cameraStatus")}
              </Typography>
              <List dense>
                {(cameras || []).slice(0, 8).map((c) => (
                  <ListItem key={c.id} sx={{ px: 0 }}>
                    <CameraStatusDot status={c.status} />
                    <ListItemText primary={c.name} secondary={c.location || "—"} />
                    {c.is_recording && (
                      <Chip size="small" color="warning" label={t("dashboard.recording")} />
                    )}
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card sx={{ border: "1px solid #2b3a4f" }}>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 1 }}>
                {t("dashboard.recentAlarms")}
              </Typography>
              <List dense>
                {(events || []).slice(0, 8).map((e) => (
                  <ListItem key={e.id} sx={{ px: 0 }}>
                    <Stack direction="row" spacing={1.5} alignItems="center" sx={{ flex: 1 }}>
                      <SeverityChip severity={e.severity} />
                      <ListItemText
                        primary={`${t(`eventTypes.${e.type}`)} — ${e.camera_name || "—"}`}
                        secondary={formatTime(e.ts)}
                      />
                      {!e.acknowledged && (
                        <Chip size="small" color="error" label={t("events.unacknowledged")} />
                      )}
                    </Stack>
                  </ListItem>
                ))}
                {!events?.length && (
                  <Typography variant="body2" color="text.secondary">
                    {t("common.none")}
                  </Typography>
                )}
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
