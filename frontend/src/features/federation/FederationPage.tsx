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
  List,
  ListItem,
  ListItemText,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import SyncIcon from "@mui/icons-material/Sync";
import DeleteIcon from "@mui/icons-material/Delete";
import HubIcon from "@mui/icons-material/Hub";
import { useTranslation } from "react-i18next";

import {
  useCreateFederatedServerMutation,
  useDeleteFederatedServerMutation,
  useFederatedServersQuery,
  useSyncFederatedServerMutation,
} from "../../api/endpointsPhase2";
import { formatDateTime, toFa } from "../../utils/format";

const statusColor: Record<string, "success" | "error" | "warning"> = {
  online: "success",
  offline: "error",
  unknown: "warning",
};

export default function FederationPage() {
  const { t } = useTranslation();
  const { data: servers } = useFederatedServersQuery();
  const [createServer] = useCreateFederatedServerMutation();
  const [deleteServer] = useDeleteFederatedServerMutation();
  const [sync] = useSyncFederatedServerMutation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<any>({ name: "", base_url: "", username: "", password: "", enabled: true });

  return (
    <Box>
      <Stack direction="row" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h4">{t("federation.title")}</Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)}>
          {t("federation.addServer")}
        </Button>
      </Stack>

      <Grid container spacing={2}>
        {(servers || []).map((s) => (
          <Grid item xs={12} md={6} key={s.id}>
            <Card sx={{ border: "1px solid #2b3a4f" }}>
              <CardContent>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <HubIcon color="disabled" />
                  <Typography variant="h6" sx={{ flexGrow: 1 }}>
                    {s.name}
                  </Typography>
                  <Chip size="small" color={statusColor[s.status]} label={t(`status.${s.status}`)} />
                  <IconButton size="small" onClick={() => sync(s.id)}>
                    <SyncIcon fontSize="small" />
                  </IconButton>
                  <IconButton size="small" color="error" onClick={() => deleteServer(s.id)}>
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Stack>
                <Typography variant="caption" color="text.secondary" dir="ltr">
                  {s.base_url}
                </Typography>
                <Typography variant="body2" sx={{ mt: 1 }}>
                  {t("federation.cameras")}: {toFa(s.camera_count)} — {t("federation.lastSync")}:{" "}
                  {s.last_sync ? formatDateTime(s.last_sync) : "—"}
                </Typography>
                {s.remote_cameras?.length > 0 && (
                  <List dense sx={{ mt: 1, maxHeight: 160, overflow: "auto" }}>
                    {s.remote_cameras.map((rc) => (
                      <ListItem key={rc.id} sx={{ px: 0 }}>
                        <ListItemText primary={rc.name} secondary={rc.status} />
                      </ListItem>
                    ))}
                  </List>
                )}
              </CardContent>
            </Card>
          </Grid>
        ))}
        {!servers?.length && (
          <Grid item xs={12}>
            <Typography color="text.secondary">{t("federation.empty")}</Typography>
          </Grid>
        )}
      </Grid>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{t("federation.addServer")}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label={t("cameras.name")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <TextField label={t("federation.baseUrl")} placeholder="http://site-b:8080" dir="ltr" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} />
            <TextField label={t("auth.username")} dir="ltr" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            <TextField label={t("auth.password")} type="password" dir="ltr" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
          <Button variant="contained" onClick={async () => { await createServer(form); setOpen(false); }} disabled={!form.name || !form.base_url}>
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
