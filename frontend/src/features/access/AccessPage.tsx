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
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import { DataGrid, GridColDef } from "@mui/x-data-grid";
import LockOpenIcon from "@mui/icons-material/LockOpen";
import LockIcon from "@mui/icons-material/Lock";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import MeetingRoomIcon from "@mui/icons-material/MeetingRoom";
import { useTranslation } from "react-i18next";

import {
  useAccessEventsQuery,
  useCardholdersQuery,
  useCreateDoorMutation,
  useDeleteDoorMutation,
  useDoorsQuery,
  useLockDoorMutation,
  useUnlockDoorMutation,
} from "../../api/endpointsPhase2";
import { formatDateTime } from "../../utils/format";

const stateColor: Record<string, "success" | "error" | "warning" | "default"> = {
  unlocked: "success",
  locked: "default",
  held: "warning",
  offline: "error",
};

export default function AccessPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState(0);
  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 2 }}>
        {t("access.title")}
      </Typography>
      <Tabs value={tab} onChange={(_e, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label={t("access.doors")} />
        <Tab label={t("access.cardholders")} />
        <Tab label={t("access.events")} />
      </Tabs>
      {tab === 0 && <DoorsTab />}
      {tab === 1 && <CardholdersTab />}
      {tab === 2 && <AccessEventsTab />}
    </Box>
  );
}

function DoorsTab() {
  const { t } = useTranslation();
  const { data: doors } = useDoorsQuery();
  const [unlock] = useUnlockDoorMutation();
  const [lock] = useLockDoorMutation();
  const [createDoor] = useCreateDoorMutation();
  const [deleteDoor] = useDeleteDoorMutation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<any>({ name: "", location: "", controller_url: "", relay: 1, unlock_seconds: 5 });

  return (
    <Box>
      <Stack direction="row" sx={{ mb: 1 }}>
        <Box sx={{ flexGrow: 1 }} />
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)}>
          {t("access.addDoor")}
        </Button>
      </Stack>
      <Grid container spacing={2}>
        {(doors || []).map((d) => (
          <Grid item xs={12} sm={6} md={4} key={d.id}>
            <Card sx={{ border: "1px solid #2b3a4f" }}>
              <CardContent>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <MeetingRoomIcon color="disabled" />
                  <Typography variant="h6" sx={{ flexGrow: 1 }}>
                    {d.name}
                  </Typography>
                  <Chip size="small" color={stateColor[d.state]} label={t(`access.state.${d.state}`)} />
                </Stack>
                <Typography variant="caption" color="text.secondary">
                  {d.location || "—"}
                </Typography>
                <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                  <Button
                    size="small"
                    variant="contained"
                    color="success"
                    startIcon={<LockOpenIcon />}
                    onClick={() => unlock(d.id)}
                  >
                    {t("access.unlock")}
                  </Button>
                  <Button size="small" variant="outlined" startIcon={<LockIcon />} onClick={() => lock(d.id)}>
                    {t("access.lock")}
                  </Button>
                  <Box sx={{ flexGrow: 1 }} />
                  <IconButton size="small" color="error" onClick={() => deleteDoor(d.id)}>
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{t("access.addDoor")}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label={t("cameras.name")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <TextField label={t("cameras.location")} value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
            <TextField label={t("access.controllerUrl")} value={form.controller_url} dir="ltr" onChange={(e) => setForm({ ...form, controller_url: e.target.value })} />
            <Stack direction="row" spacing={2}>
              <TextField type="number" label={t("access.relay")} value={form.relay} onChange={(e) => setForm({ ...form, relay: Number(e.target.value) })} />
              <TextField type="number" label={t("access.unlockSeconds")} value={form.unlock_seconds} onChange={(e) => setForm({ ...form, unlock_seconds: Number(e.target.value) })} />
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
          <Button variant="contained" onClick={async () => { await createDoor(form); setOpen(false); }} disabled={!form.name}>
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

function CardholdersTab() {
  const { t } = useTranslation();
  const { data } = useCardholdersQuery();
  const kindColor: Record<string, "info" | "warning" | "default"> = {
    employee: "info",
    visitor: "warning",
    contractor: "default",
  };
  const columns: GridColDef[] = [
    { field: "first_name", headerName: t("access.firstName"), flex: 1 },
    { field: "last_name", headerName: t("access.lastName"), flex: 1 },
    {
      field: "kind",
      headerName: t("access.kind"),
      width: 110,
      renderCell: (p) => (
        <Chip size="small" color={kindColor[p.value] || "default"} label={t(`access.kinds.${p.value}`)} />
      ),
    },
    { field: "employee_id", headerName: t("access.employeeId"), width: 140 },
    {
      field: "credentials",
      headerName: t("access.credentials"),
      width: 140,
      valueGetter: (_v, row) => row.credentials?.length ?? 0,
    },
    {
      field: "active",
      headerName: t("users.active"),
      width: 100,
      renderCell: (p) =>
        p.value ? <Chip size="small" color="success" label={t("common.yes")} /> : <Chip size="small" label={t("common.no")} />,
    },
  ];
  return (
    <Card sx={{ border: "1px solid #2b3a4f" }}>
      <DataGrid autoHeight rows={data || []} columns={columns} sx={{ border: 0 }} />
    </Card>
  );
}

function AccessEventsTab() {
  const { t } = useTranslation();
  const { data } = useAccessEventsQuery();
  const columns: GridColDef[] = [
    {
      field: "decision",
      headerName: t("access.decision"),
      width: 120,
      renderCell: (p) => (
        <Chip size="small" color={p.value === "granted" ? "success" : "error"} label={t(`access.${p.value}`)} />
      ),
    },
    { field: "door_name", headerName: t("access.door"), flex: 1 },
    { field: "cardholder_name", headerName: t("access.cardholder"), flex: 1 },
    { field: "reason", headerName: t("access.reason"), flex: 1 },
    { field: "ts", headerName: t("events.time"), width: 180, valueFormatter: (v: string) => formatDateTime(v) },
  ];
  return (
    <Card sx={{ border: "1px solid #2b3a4f" }}>
      <DataGrid autoHeight rows={data || []} columns={columns} sx={{ border: 0 }} />
    </Card>
  );
}
