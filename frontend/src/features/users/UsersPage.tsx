import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Card,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { DataGrid, GridColDef } from "@mui/x-data-grid";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import { useTranslation } from "react-i18next";

import {
  useCreateUserMutation,
  useDeleteUserMutation,
  useRolesQuery,
  useUpdateUserMutation,
  useUsersQuery,
} from "../../api/endpoints";
import type { AppUser } from "../../api/types";

const empty = { username: "", email: "", display_name: "", role: null, is_active: true, password: "" };

export default function UsersPage() {
  const { t } = useTranslation();
  const { data: users, isLoading } = useUsersQuery();
  const { data: roles } = useRolesQuery();
  const [createUser] = useCreateUserMutation();
  const [updateUser] = useUpdateUserMutation();
  const [deleteUser] = useDeleteUserMutation();

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<AppUser | null>(null);
  const [form, setForm] = useState<any>(empty);

  useEffect(() => {
    setForm(editing ? { ...editing, password: "" } : empty);
  }, [editing, open]);

  const set = (k: string, v: any) => setForm((f: any) => ({ ...f, [k]: v }));

  const save = async () => {
    const body: any = { ...form };
    if (!body.password) delete body.password;
    if (editing) await updateUser({ id: editing.id, body });
    else await createUser(body);
    setOpen(false);
  };

  const columns: GridColDef<AppUser>[] = [
    { field: "username", headerName: t("users.username"), flex: 1, minWidth: 120 },
    { field: "display_name", headerName: t("users.displayName"), flex: 1, minWidth: 120 },
    { field: "email", headerName: t("users.email"), flex: 1, minWidth: 150 },
    { field: "role_name", headerName: t("users.role"), width: 140 },
    {
      field: "is_active",
      headerName: t("users.active"),
      width: 100,
      renderCell: (p) =>
        p.value ? (
          <Chip size="small" color="success" label={t("common.yes")} />
        ) : (
          <Chip size="small" variant="outlined" label={t("common.no")} />
        ),
    },
    {
      field: "actions",
      headerName: t("common.actions"),
      width: 110,
      sortable: false,
      renderCell: (p) => (
        <>
          <Tooltip title={t("common.edit")}>
            <IconButton
              size="small"
              onClick={() => {
                setEditing(p.row);
                setOpen(true);
              }}
            >
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={t("common.delete")}>
            <IconButton
              size="small"
              color="error"
              onClick={() => deleteUser(p.row.id)}
              disabled={p.row.is_superuser}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </>
      ),
    },
  ];

  return (
    <Box>
      <Stack direction="row" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h4">{t("users.title")}</Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => {
            setEditing(null);
            setOpen(true);
          }}
        >
          {t("users.add")}
        </Button>
      </Stack>

      <Card sx={{ border: "1px solid #2b3a4f" }}>
        <DataGrid
          autoHeight
          rows={users || []}
          columns={columns}
          loading={isLoading}
          disableRowSelectionOnClick
          sx={{ border: 0, "& .MuiDataGrid-cell": { borderColor: "#2b3a4f" } }}
        />
      </Card>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? t("common.edit") : t("users.add")}</DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <TextField
                label={t("users.username")}
                value={form.username}
                onChange={(e) => set("username", e.target.value)}
                fullWidth
                dir="ltr"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label={t("users.displayName")}
                value={form.display_name}
                onChange={(e) => set("display_name", e.target.value)}
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label={t("users.email")}
                value={form.email}
                onChange={(e) => set("email", e.target.value)}
                fullWidth
                dir="ltr"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                select
                label={t("users.role")}
                value={form.role ?? ""}
                onChange={(e) => set("role", Number(e.target.value))}
                fullWidth
              >
                {(roles || []).map((r) => (
                  <MenuItem key={r.id} value={r.id}>
                    {r.name}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12}>
              <TextField
                label={t("users.password")}
                type="password"
                value={form.password}
                onChange={(e) => set("password", e.target.value)}
                placeholder={editing ? "بدون تغییر" : ""}
                fullWidth
                dir="ltr"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
          <Button variant="contained" onClick={save}>
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
