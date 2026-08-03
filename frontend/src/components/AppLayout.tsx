import { useEffect, useMemo, useState } from "react";
import {
  AppBar,
  Avatar,
  Badge,
  Box,
  Button,
  Chip,
  Divider,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  ListSubheader,
  Menu,
  MenuItem,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";
import DashboardIcon from "@mui/icons-material/SpaceDashboard";
import LiveTvIcon from "@mui/icons-material/LiveTv";
import HistoryIcon from "@mui/icons-material/History";
import FileDownloadIcon from "@mui/icons-material/FileDownload";
import VideocamIcon from "@mui/icons-material/Videocam";
import NotificationsIcon from "@mui/icons-material/Notifications";
import NotificationsActiveIcon from "@mui/icons-material/NotificationsActive";
import PeopleIcon from "@mui/icons-material/People";
import SecurityIcon from "@mui/icons-material/AdminPanelSettings";
import LogoutIcon from "@mui/icons-material/Logout";
import ShieldIcon from "@mui/icons-material/GppGood";
import GppMaybeIcon from "@mui/icons-material/GppMaybe";
import InsightsIcon from "@mui/icons-material/Insights";
import MeetingRoomIcon from "@mui/icons-material/MeetingRoom";
import MapIcon from "@mui/icons-material/Map";
import HubIcon from "@mui/icons-material/Hub";
import GavelIcon from "@mui/icons-material/Gavel";
import AssessmentIcon from "@mui/icons-material/Assessment";
import BoltIcon from "@mui/icons-material/Bolt";
import MonitorHeartIcon from "@mui/icons-material/MonitorHeart";
import SettingsIcon from "@mui/icons-material/Settings";
import ViewQuiltIcon from "@mui/icons-material/ViewQuilt";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAppDispatch, useAppSelector } from "../app/hooks";
import { hasPerm, logout, setUser } from "../features/auth/authSlice";
import { useDashboardSummaryQuery, useEventsQuery, useMeQuery } from "../api/endpoints";
import { useSetThreatLevelMutation } from "../api/endpointsOps";
import { useLiveEvents } from "../features/events/useLiveEvents";
import { featureEnabled } from "../config/features";

const drawerWidth = 252;

const THREAT_COLORS: Record<string, string> = {
  green: "#3ddc84",
  yellow: "#ffb020",
  red: "#ff5a5a",
};

export default function AppLayout() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const user = useAppSelector((s) => s.auth.user);
  const { data: currentUser } = useMeQuery();
  useEffect(() => {
    if (currentUser) dispatch(setUser(currentUser));
  }, [currentUser, dispatch]);
  useLiveEvents(); // app-wide WS subscription
  const { data: events } = useEventsQuery({ acknowledged: false });
  const { data: summary } = useDashboardSummaryQuery(undefined, { pollingInterval: 30000 });
  const [setThreatLevel] = useSetThreatLevelMutation();
  const unacked = events?.length ?? 0;
  const threat = summary?.threat_level || "green";
  const [threatAnchor, setThreatAnchor] = useState<null | HTMLElement>(null);
  const canThreat = hasPerm(user, "threat.manage");

  const groups = useMemo(
    () => [
      {
        header: null,
        items: [{ to: "/", icon: <DashboardIcon />, label: t("nav.dashboard"), perm: null }],
      },
      {
        header: t("navGroups.video"),
        items: [
          { to: "/desk", icon: <ViewQuiltIcon />, label: t("nav.desk"), perm: "liveview.view" },
          { to: "/live", icon: <LiveTvIcon />, label: t("nav.liveview"), perm: "liveview.view" },
          { to: "/playback", icon: <HistoryIcon />, label: t("nav.playback"), perm: "playback.view" },
          { to: "/exports", icon: <FileDownloadIcon />, label: t("nav.exports"), perm: "playback.export" },
          { to: "/cameras", icon: <VideocamIcon />, label: t("nav.cameras"), perm: "camera.view" },
          {
            to: "/events",
            icon: (
              <Badge color="error" badgeContent={unacked} max={99}>
                <NotificationsIcon />
              </Badge>
            ),
            label: t("nav.events"),
            perm: "event.view",
          },
        ],
      },
      {
        header: t("navGroups.intelligence"),
        items: [
          ...(featureEnabled(user, "analytics")
            ? [{ to: "/analytics", icon: <InsightsIcon />, label: t("nav.analytics"), perm: "analytics.view" }]
            : []),
          { to: "/reports", icon: <AssessmentIcon />, label: t("nav.reports"), perm: "report.view" },
        ],
      },
      {
        header: t("navGroups.access"),
        items: [
          ...(featureEnabled(user, "access_control")
            ? [{ to: "/access", icon: <MeetingRoomIcon />, label: t("nav.access"), perm: "access.view" }]
            : []),
        ],
      },
      {
        header: t("navGroups.system"),
        items: [
          ...(featureEnabled(user, "maps")
            ? [{ to: "/maps", icon: <MapIcon />, label: t("nav.maps"), perm: "map.view" }]
            : []),
          { to: "/automation", icon: <BoltIcon />, label: t("nav.automation"), perm: "automation.manage" },
          ...(featureEnabled(user, "federation")
            ? [{ to: "/federation", icon: <HubIcon />, label: t("nav.federation"), perm: "federation.manage" }]
            : []),
          ...(featureEnabled(user, "evidence")
            ? [{ to: "/evidence", icon: <GavelIcon />, label: t("nav.evidence"), perm: "evidence.view" }]
            : []),
          { to: "/health", icon: <MonitorHeartIcon />, label: t("nav.health"), perm: "system.view" },
          { to: "/users", icon: <PeopleIcon />, label: t("nav.users"), perm: "user.manage" },
          { to: "/roles", icon: <SecurityIcon />, label: t("nav.roles"), perm: "user.manage" },
          { to: "/settings", icon: <SettingsIcon />, label: t("nav.settings"), perm: "settings.manage" },
        ],
      },
    ],
    [t, unacked, user]
  );

  const doLogout = () => {
    dispatch(logout());
    navigate("/login");
  };

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <AppBar
        position="fixed"
        elevation={0}
        sx={{ zIndex: (th) => th.zIndex.drawer + 1 }}
      >
        <Toolbar sx={{ gap: 1.5 }}>
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: 2,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "linear-gradient(135deg,#3da5ff,#1f7fe0)",
              boxShadow: "0 8px 20px -8px rgba(61,165,255,.8)",
            }}
          >
            <ShieldIcon sx={{ color: "#fff", fontSize: 22 }} />
          </Box>
          <Box sx={{ lineHeight: 1 }}>
            <Typography variant="h6" sx={{ fontWeight: 900, lineHeight: 1.1 }}>
              {t("app.name")}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: { xs: "none", md: "block" } }}>
              {t("app.tagline")}
            </Typography>
          </Box>
          <Box sx={{ flexGrow: 1 }} />

          {/* Genetec-style threat level */}
          <Tooltip title={t("threat.title")}>
            <Chip
              size="small"
              icon={<GppMaybeIcon sx={{ "&&": { color: "#0b0e14" } }} />}
              label={t(`threat.${threat}`)}
              onClick={canThreat ? (e) => setThreatAnchor(e.currentTarget) : undefined}
              sx={{
                bgcolor: THREAT_COLORS[threat],
                color: "#0b0e14",
                fontWeight: 800,
                cursor: canThreat ? "pointer" : "default",
              }}
            />
          </Tooltip>
          <Menu anchorEl={threatAnchor} open={!!threatAnchor} onClose={() => setThreatAnchor(null)}>
            {(["green", "yellow", "red"] as const).map((l) => (
              <MenuItem
                key={l}
                selected={threat === l}
                onClick={() => {
                  setThreatLevel(l);
                  setThreatAnchor(null);
                }}
              >
                <Box
                  sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: THREAT_COLORS[l], ml: 1 }}
                />
                {t(`threat.${l}`)}
              </MenuItem>
            ))}
          </Menu>

          <Chip
            size="small"
            variant="outlined"
            label={user?.organization?.name || "—"}
            sx={{ display: { xs: "none", sm: "flex" } }}
          />
          <Avatar sx={{ width: 32, height: 32, bgcolor: "primary.main" }}>
            {(user?.display_name || user?.username || "?").slice(0, 1)}
          </Avatar>
          <Box sx={{ mx: 1, display: { xs: "none", sm: "block" } }}>
            <Typography variant="body2" sx={{ lineHeight: 1 }}>
              {user?.display_name || user?.username}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {user?.role_name || (user?.is_superuser ? "مدیر کل" : "")}
            </Typography>
          </Box>
          <Tooltip title={t("nav.logout")}>
            <IconButton onClick={doLogout} color="inherit">
              <LogoutIcon />
            </IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>

      {/*
        Sidebar as a plain fixed nav with LOGICAL positioning. MUI's Drawer
        anchor gets double-flipped in RTL (MUI mirrors it for theme.direction
        AND stylis-plugin-rtl mirrors the CSS again), which left the panel
        overlapping the content. inset-inline/border-inline are resolved by
        the browser from dir="rtl" and are untouched by the RTL plugin.
      */}
      <Box
        component="nav"
        sx={{
          position: "fixed",
          top: 64,
          bottom: 0,
          insetInlineStart: 0,
          width: drawerWidth,
          zIndex: (th) => th.zIndex.appBar - 1,
          bgcolor: "background.paper",
          borderInlineEnd: "1px solid #243044",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <Box sx={{ overflow: "auto", px: 1, py: 1, flexGrow: 1 }}>
          {groups.map((group, gi) => {
            const visible = group.items.filter((i) => !i.perm || hasPerm(user, i.perm));
            if (!visible.length) return null;
            return (
              <List
                key={gi}
                dense
                subheader={
                  group.header ? (
                    <ListSubheader
                      disableSticky
                      sx={{ bgcolor: "transparent", color: "#5d708a", fontWeight: 800, lineHeight: 2.4 }}
                    >
                      {group.header}
                    </ListSubheader>
                  ) : undefined
                }
              >
                {visible.map((item) => (
                  <ListItemButton
                    key={item.to}
                    component={NavLink}
                    to={item.to}
                    end={item.to === "/"}
                    sx={{
                      borderRadius: 2.5,
                      mb: 0.25,
                      "&.active": {
                        background: "linear-gradient(135deg,#3da5ff,#1f7fe0)",
                        color: "#fff",
                        boxShadow: "0 8px 22px -10px rgba(61,165,255,.9)",
                      },
                      "&.active .MuiListItemIcon-root": { color: "#fff" },
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: 38, color: "text.secondary" }}>
                      {item.icon}
                    </ListItemIcon>
                    <ListItemText primaryTypographyProps={{ fontWeight: 700 }} primary={item.label} />
                  </ListItemButton>
                ))}
              </List>
            );
          })}
        </Box>
        <Divider sx={{ borderColor: "#243044" }} />
        <Box sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">
            © پرشین‌سکیور — نسخه ۰٫۲
          </Typography>
        </Box>
      </Box>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          mt: 8,
          minWidth: 0,
          marginInlineStart: `${drawerWidth}px`,
        }}
      >
        {/* Live alarm banner (Genetec-style alarm bar) */}
        {unacked > 0 && (
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1.5,
              px: 2,
              py: 1,
              mb: 2,
              borderRadius: 2,
              border: "1px solid #ff5a5a",
              bgcolor: "rgba(255,90,90,0.12)",
            }}
          >
            <NotificationsActiveIcon color="error" />
            <Typography sx={{ flexGrow: 1, fontWeight: 700 }}>
              {t("banner.unacked", { count: unacked })}
            </Typography>
            <Button size="small" color="error" variant="contained" onClick={() => navigate("/events")}>
              {t("banner.view")}
            </Button>
          </Box>
        )}
        <Outlet />
      </Box>
    </Box>
  );
}
