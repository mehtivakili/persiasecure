import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  FormGroup,
  Grid,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import { useTranslation } from "react-i18next";

import {
  useCreateRoleMutation,
  useDeleteRoleMutation,
  usePermissionCatalogQuery,
  useRolesQuery,
  useUpdateRoleMutation,
} from "../../api/endpoints";
import type { Role } from "../../api/types";

export default function RolesPage() {
  const { t } = useTranslation();
  const { data: roles } = useRolesQuery();
  const { data: catalog } = usePermissionCatalogQuery();
  const [createRole] = useCreateRoleMutation();
  const [updateRole] = useUpdateRoleMutation();
  const [deleteRole] = useDeleteRoleMutation();

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Role | null>(null);
  const [name, setName] = useState("");
  const [perms, setPerms] = useState<string[]>([]);

  useEffect(() => {
    setName(editing?.name || "");
    setPerms(editing?.permissions || []);
  }, [editing, open]);

  const toggle = (code: string) =>
    setPerms((p) => (p.includes(code) ? p.filter((x) => x !== code) : [...p, code]));

  const save = async () => {
    const body = { name, permissions: perms };
    if (editing) await updateRole({ id: editing.id, body });
    else await createRole(body);
    setOpen(false);
  };

  return (
    <Box>
      <Stack direction="row" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h4">{t("roles.title")}</Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => {
            setEditing(null);
            setOpen(true);
          }}
        >
          {t("roles.add")}
        </Button>
      </Stack>

      <Grid container spacing={2}>
        {(roles || []).map((role) => (
          <Grid item xs={12} md={6} lg={4} key={role.id}>
            <Card sx={{ border: "1px solid #2b3a4f", height: "100%" }}>
              <CardContent>
                <Stack direction="row" alignItems="center" sx={{ mb: 1 }}>
                  <Typography variant="h6">{role.name}</Typography>
                  {role.is_system && (
                    <Chip size="small" label="سیستمی" sx={{ mx: 1 }} />
                  )}
                  <Box sx={{ flexGrow: 1 }} />
                  <Tooltip title={t("common.edit")}>
                    <IconButton
                      size="small"
                      onClick={() => {
                        setEditing(role);
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
                      disabled={role.is_system}
                      onClick={() => deleteRole(role.id)}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Stack>
                <Typography variant="caption" color="text.secondary">
                  {t("roles.users")}: {role.user_count} — {t("roles.permissions")}:{" "}
                  {role.permissions.length}
                </Typography>
                <Box sx={{ mt: 1, display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                  {role.permissions.slice(0, 6).map((p) => (
                    <Chip
                      key={p}
                      size="small"
                      variant="outlined"
                      label={catalog?.find((c) => c.code === p)?.label || p}
                    />
                  ))}
                  {role.permissions.length > 6 && (
                    <Chip size="small" label={`+${role.permissions.length - 6}`} />
                  )}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? t("common.edit") : t("roles.add")}</DialogTitle>
        <DialogContent dividers>
          <TextField
            label={t("roles.name")}
            value={name}
            onChange={(e) => setName(e.target.value)}
            fullWidth
            sx={{ mb: 2 }}
          />
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            {t("roles.permissions")}
          </Typography>
          <FormGroup>
            {(catalog || []).map((c) => (
              <FormControlLabel
                key={c.code}
                control={
                  <Checkbox
                    checked={perms.includes(c.code)}
                    onChange={() => toggle(c.code)}
                  />
                }
                label={c.label}
              />
            ))}
          </FormGroup>
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
