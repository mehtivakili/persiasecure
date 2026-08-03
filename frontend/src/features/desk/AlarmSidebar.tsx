import {
  Box,
  Button,
  Chip,
  FormControlLabel,
  IconButton,
  Stack,
  Switch,
  Tooltip,
  Typography,
} from "@mui/material";
import DoneIcon from "@mui/icons-material/Done";
import ClearIcon from "@mui/icons-material/Clear";
import DoneAllIcon from "@mui/icons-material/DoneAll";
import NotificationsActiveIcon from "@mui/icons-material/NotificationsActive";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import { useTranslation } from "react-i18next";

import {
  useAcknowledgeAllMutation,
  useAcknowledgeEventMutation,
  useClearEventMutation,
} from "../../api/endpoints";
import type { VmsEvent } from "../../api/types";
import { formatTime } from "../../utils/format";
import SeverityChip from "../events/SeverityChip";

interface Props {
  events: VmsEvent[];
  autoDisplay: boolean;
  onAutoDisplayChange: (v: boolean) => void;
  /** Load the alarming camera into a tile. */
  onShow: (cameraId: number) => void;
}

/** Genetec-style alarm monitoring pane: live feed, ack/clear, push-to-tile. */
export default function AlarmSidebar({ events, autoDisplay, onAutoDisplayChange, onShow }: Props) {
  const { t } = useTranslation();
  const [ack] = useAcknowledgeEventMutation();
  const [clear] = useClearEventMutation();
  const [ackAll] = useAcknowledgeAllMutation();

  const active = events.filter((e) => !e.cleared);

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
        <NotificationsActiveIcon color={active.length ? "error" : "disabled"} fontSize="small" />
        <Typography variant="subtitle2" sx={{ flexGrow: 1, color: "text.primary" }}>
          {t("desk.alarms")}
        </Typography>
        <Chip size="small" color={active.length ? "error" : "default"} label={active.length} />
      </Stack>

      <FormControlLabel
        control={
          <Switch
            size="small"
            checked={autoDisplay}
            onChange={(e) => onAutoDisplayChange(e.target.checked)}
          />
        }
        label={<Typography variant="caption">{t("desk.autoDisplay")}</Typography>}
        sx={{ mb: 0.5 }}
      />

      <Button size="small" startIcon={<DoneAllIcon />} onClick={() => ackAll()} sx={{ mb: 1 }}>
        {t("events.acknowledgeAll")}
      </Button>

      <Box sx={{ overflow: "auto", flexGrow: 1 }}>
        <Stack spacing={0.75}>
          {active.map((e) => (
            <Box
              key={e.id}
              sx={{
                p: 1,
                borderRadius: 2,
                border: "1px solid #243044",
                bgcolor: e.acknowledged ? "transparent" : "rgba(255,90,95,.08)",
              }}
            >
              <Stack direction="row" alignItems="center" spacing={0.5}>
                <SeverityChip severity={e.severity} />
                <Typography variant="caption" sx={{ flexGrow: 1 }} noWrap>
                  {t(`eventTypes.${e.type}`)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {formatTime(e.ts)}
                </Typography>
              </Stack>
              <Typography variant="caption" color="text.secondary" display="block" noWrap>
                {e.camera_name || "—"}
              </Typography>
              {e.snapshot && (
                <img
                  src={e.snapshot}
                  alt=""
                  style={{ width: "100%", height: 64, objectFit: "cover", borderRadius: 6, marginTop: 4 }}
                />
              )}
              <Stack direction="row" spacing={0.25} sx={{ mt: 0.5 }}>
                {e.camera && (
                  <Tooltip title={t("desk.showInTile")}>
                    <IconButton size="small" onClick={() => onShow(e.camera!)}>
                      <OpenInNewIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
                <Box sx={{ flexGrow: 1 }} />
                <Tooltip title={t("events.acknowledge")}>
                  <span>
                    <IconButton size="small" disabled={e.acknowledged} onClick={() => ack(e.id)}>
                      <DoneIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
                <Tooltip title={t("events.clear")}>
                  <IconButton size="small" color="success" onClick={() => clear(e.id)}>
                    <ClearIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Stack>
            </Box>
          ))}
          {!active.length && (
            <Typography variant="caption" color="text.secondary">
              {t("desk.noAlarms")}
            </Typography>
          )}
        </Stack>
      </Box>
    </Box>
  );
}
