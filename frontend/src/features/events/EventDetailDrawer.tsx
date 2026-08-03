import { useState } from "react";
import {
  Box,
  Button,
  Chip,
  Divider,
  Drawer,
  FormControl,
  IconButton,
  InputLabel,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import DoneIcon from "@mui/icons-material/Done";
import ClearIcon from "@mui/icons-material/Clear";
import ThumbDownIcon from "@mui/icons-material/ThumbDown";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import ReplayIcon from "@mui/icons-material/Replay";
import LockIcon from "@mui/icons-material/Lock";
import HistoryEduIcon from "@mui/icons-material/HistoryEdu";
import MovieIcon from "@mui/icons-material/Movie";
import VideocamIcon from "@mui/icons-material/Videocam";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import {
  useAcknowledgeEventMutation,
  useAddEventCommentMutation,
  useAssignEventMutation,
  useClearEventMutation,
  useEventAuditQuery,
  useEventCommentsQuery,
  useProtectEventClipMutation,
  useRelatedEventsQuery,
  useReportEventMutation,
  useRetryEventClipMutation,
  useUsersQuery,
} from "../../api/endpoints";
import type { VmsEvent } from "../../api/types";
import { formatDateTime } from "../../utils/format";
import SeverityChip from "./SeverityChip";
import ClipPlayerDialog from "./ClipPlayerDialog";

interface Props {
  event: VmsEvent | null;
  onClose: () => void;
  onOpenEvent: (e: VmsEvent) => void;
}

export default function EventDetailDrawer({ event, onClose, onOpenEvent }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const id = event?.id ?? 0;

  const { data: comments } = useEventCommentsQuery(id, { skip: !event });
  const { data: related } = useRelatedEventsQuery(id, { skip: !event });
  const { data: audit } = useEventAuditQuery(id, { skip: !event });
  const { data: users } = useUsersQuery();
  const [addComment] = useAddEventCommentMutation();
  const [assign] = useAssignEventMutation();
  const [ack] = useAcknowledgeEventMutation();
  const [clear] = useClearEventMutation();
  const [retryClip] = useRetryEventClipMutation();
  const [protectClip] = useProtectEventClipMutation();
  const [reportEvent] = useReportEventMutation();

  const [note, setNote] = useState("");
  const [playUrl, setPlayUrl] = useState<string | null>(null);

  const submitComment = async () => {
    if (!event || !note.trim()) return;
    await addComment({ id: event.id, text: note.trim() });
    setNote("");
  };

  const openInPlayback = () => {
    if (!event?.camera) return;
    const date = new Date(event.ts).toISOString().slice(0, 10);
    navigate(`/playback?camera=${event.camera}&date=${date}&t=${encodeURIComponent(event.ts)}`);
  };
  const openLive = () => {
    if (!event?.camera) return;
    navigate(`/live?camera=${event.camera}`);
  };

  const protect = () => {
    if (!event?.clip) return;
    const until = new Date(Date.now() + 365 * 24 * 3600 * 1000).toISOString();
    protectClip({ id: event.clip.id, protected_until: until });
  };

  const clip = event?.clip;

  return (
    <Drawer anchor="right" open={!!event} onClose={onClose} PaperProps={{ sx: { width: { xs: "100%", sm: 460 } } }}>
      {event && (
        <Box sx={{ p: 2 }}>
          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
            <Typography variant="h6" sx={{ flexGrow: 1 }}>
              {t(`eventTypes.${event.type}` as any)}
            </Typography>
            <SeverityChip severity={event.severity} />
            <IconButton onClick={onClose}><CloseIcon /></IconButton>
          </Stack>
          <Typography variant="body2" color="text.secondary">
            {event.camera_name || "—"} · {formatDateTime(event.ts)}
          </Typography>
          {(event.details as any)?.model_name && (
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
              {t("events.detectedBy", {
                model: (event.details as any).model_name,
                confidence: Math.round(((event.details as any).confidence || 0) * 100),
              })}
            </Typography>
          )}
          {(event.details as any)?.false_positive && (
            <Chip size="small" color="warning" label={t("events.falsePositive")} sx={{ mt: 0.5 }} />
          )}

          {event.snapshot && (
            <Box
              component="img"
              src={event.snapshot}
              alt=""
              sx={{ width: "100%", borderRadius: 1, mt: 1.5, maxHeight: 220, objectFit: "cover" }}
            />
          )}

          {/* Clip */}
          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle2" gutterBottom>{t("events.clip")}</Typography>
          {!clip ? (
            <Typography variant="body2" color="text.disabled">{t("events.noClip")}</Typography>
          ) : clip.status === "ready" && clip.stream_url ? (
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Button size="small" variant="contained" startIcon={<PlayArrowIcon />} onClick={() => setPlayUrl(clip.stream_url)}>
                {t("events.playClip")}
              </Button>
              <Button size="small" startIcon={<LockIcon />} onClick={protect}>{t("events.protect")}</Button>
            </Stack>
          ) : clip.status === "failed" ? (
            <Button size="small" color="warning" startIcon={<ReplayIcon />} onClick={() => retryClip(clip.id)}>
              {t("events.retryClip")}
            </Button>
          ) : (
            <Chip size="small" variant="outlined" icon={<MovieIcon />} label={t("events.clipPending")} />
          )}

          <Stack direction="row" spacing={1} sx={{ mt: 1.5 }} flexWrap="wrap" useFlexGap>
            <Button size="small" variant="outlined" startIcon={<MovieIcon />} onClick={openInPlayback} disabled={!event.camera}>
              {t("events.openPlayback")}
            </Button>
            <Button size="small" variant="outlined" startIcon={<VideocamIcon />} onClick={openLive} disabled={!event.camera}>
              {t("events.openLive")}
            </Button>
          </Stack>

          {/* Lifecycle + assign */}
          <Divider sx={{ my: 2 }} />
          <Stack direction="row" spacing={1} sx={{ mb: 1.5 }}>
            <Button size="small" variant="outlined" startIcon={<DoneIcon />} onClick={() => ack(event.id)} disabled={event.acknowledged}>
              {t("events.acknowledge")}
            </Button>
            <Button size="small" variant="outlined" color="success" startIcon={<ClearIcon />} onClick={() => clear(event.id)} disabled={event.cleared}>
              {t("events.clear")}
            </Button>
            <Button
              size="small"
              variant="outlined"
              color="warning"
              startIcon={<ThumbDownIcon />}
              onClick={() => reportEvent({ id: event.id, false_positive: true })}
            >
              {t("events.reportFP")}
            </Button>
          </Stack>
          <FormControl size="small" fullWidth>
            <InputLabel>{t("events.assignee")}</InputLabel>
            <Select
              label={t("events.assignee")}
              value={event.assigned_to ?? ""}
              onChange={(e) => assign({ id: event.id, user: e.target.value ? Number(e.target.value) : null })}
            >
              <MenuItem value="">{t("events.unassigned")}</MenuItem>
              {(users || []).map((u) => (
                <MenuItem key={u.id} value={u.id}>{u.display_name || u.username}</MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Comments */}
          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle2" gutterBottom>{t("events.comments")}</Typography>
          <Stack spacing={1} sx={{ mb: 1 }}>
            {(comments || []).map((c) => (
              <Box key={c.id} sx={{ bgcolor: "rgba(255,255,255,0.04)", borderRadius: 1, p: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  {c.username || "—"} · {formatDateTime(c.created_at)}
                </Typography>
                <Typography variant="body2">{c.text}</Typography>
              </Box>
            ))}
            {!comments?.length && (
              <Typography variant="body2" color="text.disabled">{t("events.noComments")}</Typography>
            )}
          </Stack>
          <Stack direction="row" spacing={1}>
            <TextField
              size="small"
              fullWidth
              placeholder={t("events.addComment")}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitComment()}
            />
            <Button variant="contained" onClick={submitComment} disabled={!note.trim()}>
              {t("common.save")}
            </Button>
          </Stack>

          {/* Related */}
          {!!related?.length && (
            <>
              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle2" gutterBottom>{t("events.related")}</Typography>
              <List dense>
                {related.map((r) => (
                  <ListItemButton key={r.id} onClick={() => onOpenEvent(r)} sx={{ borderRadius: 1 }}>
                    <ListItemText
                      primary={t(`eventTypes.${r.type}` as any)}
                      secondary={formatDateTime(r.ts)}
                    />
                    <SeverityChip severity={r.severity} />
                  </ListItemButton>
                ))}
              </List>
            </>
          )}

          {/* Audit */}
          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle2" gutterBottom>
            <HistoryEduIcon sx={{ fontSize: 16, verticalAlign: "middle", mr: 0.5 }} />
            {t("events.audit")}
          </Typography>
          <Stack spacing={0.5}>
            {(audit || []).map((a) => (
              <Typography key={a.id} variant="caption" color="text.secondary">
                {a.username || "—"} · {a.action} · {formatDateTime(a.created_at)}
              </Typography>
            ))}
            {!audit?.length && (
              <Typography variant="body2" color="text.disabled">{t("events.noAudit")}</Typography>
            )}
          </Stack>
        </Box>
      )}

      {playUrl && <ClipPlayerDialog url={playUrl} onClose={() => setPlayUrl(null)} />}
    </Drawer>
  );
}
