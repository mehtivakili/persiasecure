import { useState } from "react";
import {
  Box,
  Button,
  Card,
  Chip,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import { DataGrid, GridColDef } from "@mui/x-data-grid";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import RefreshIcon from "@mui/icons-material/Refresh";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";
import StopCircleIcon from "@mui/icons-material/StopCircle";
import { useTranslation } from "react-i18next";

import {
  useCamerasQuery,
  useDeleteCameraMutation,
  useStartRecordingMutation,
  useStopRecordingMutation,
} from "../../api/endpoints";
import { useAppSelector } from "../../app/hooks";
import { hasPerm } from "../auth/authSlice";
import type { Camera } from "../../api/types";
import { formatDateTime } from "../../utils/format";
import { useConfirm } from "../../components/ConfirmProvider";
import CameraStatusDot from "./CameraStatusDot";
import CameraDialog from "./CameraDialog";

export default function CamerasPage() {
  const { t } = useTranslation();
  const { data: cameras, isLoading, refetch, isFetching } = useCamerasQuery();
  const [deleteCamera] = useDeleteCameraMutation();
  const [startRecording, { isLoading: starting }] = useStartRecordingMutation();
  const [stopRecording, { isLoading: stopping }] = useStopRecordingMutation();
  const confirm = useConfirm();
  const user = useAppSelector((s) => s.auth.user);
  const canManage = hasPerm(user, "camera.manage");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Camera | null>(null);

  const openAdd = () => {
    setEditing(null);
    setDialogOpen(true);
  };
  const openEdit = (cam: Camera) => {
    setEditing(cam);
    setDialogOpen(true);
  };
  const remove = async (cam: Camera) => {
    const ok = await confirm({
      title: t("cameras.delete"),
      message: t("cameras.confirmDeleteNamed", { name: cam.name }),
      confirmLabel: t("cameras.delete"),
      destructive: true,
    });
    if (ok) deleteCamera(cam.id);
  };

  const toggleRecord = async (cam: Camera) => {
    // Scheduled recording can't be stopped from here — only manual sessions.
    if (cam.manual_recording) {
      await stopRecording(cam.id);
    } else {
      await startRecording(cam.id);
    }
  };

  const columns: GridColDef<Camera>[] = [
    {
      field: "status",
      headerName: t("cameras.status"),
      width: 120,
      renderCell: (p) => (
        <Stack direction="row" alignItems="center">
          <CameraStatusDot status={p.value} />
          <span>{t(`status.${p.value}`)}</span>
        </Stack>
      ),
    },
    { field: "name", headerName: t("cameras.name"), flex: 1, minWidth: 140 },
    { field: "location", headerName: t("cameras.location"), flex: 1, minWidth: 120 },
    { field: "manufacturer", headerName: "سازنده", width: 120 },
    {
      field: "record_mode",
      headerName: t("cameras.recording"),
      width: 150,
      // Distinct from health/status: this is the recording *state*. A live red
      // dot means it is actually recording now (schedule or manual); the chip
      // shows the policy/mode.
      renderCell: (p) => {
        const active = Boolean(p.row.recording_active);
        const mode = (p.row.manual_recording
          ? "manual"
          : p.row.record_mode || (p.row.is_recording ? "continuous" : "off")) as string;
        return (
          <Stack direction="row" spacing={0.75} alignItems="center">
            {active && (
              <FiberManualRecordIcon
                sx={{ fontSize: 12, color: "#ff5a5f", animation: "psPulse 1.6s infinite" }}
              />
            )}
            {mode === "off" ? (
              <Chip size="small" variant="outlined" label={t("recordModes.off")} />
            ) : (
              <Chip
                size="small"
                color={active ? "error" : "warning"}
                label={mode === "manual" ? t("cameras.manualRec") : t(`recordModes.${mode}`)}
              />
            )}
          </Stack>
        );
      },
    },
    {
      field: "last_seen",
      headerName: "آخرین اتصال",
      width: 170,
      valueFormatter: (v) => formatDateTime(v as string),
    },
    {
      field: "actions",
      headerName: t("common.actions"),
      width: 150,
      sortable: false,
      renderCell: (p) => {
        const manual = Boolean(p.row.manual_recording);
        const scheduled = Boolean(p.row.recording_active) && !manual;
        return (
          <>
            <Tooltip
              title={
                scheduled
                  ? t("cameras.recScheduled")
                  : manual
                    ? t("cameras.stopRec")
                    : t("cameras.startRec")
              }
            >
              <span>
                <IconButton
                  size="small"
                  color={manual ? "error" : "default"}
                  onClick={() => toggleRecord(p.row)}
                  disabled={!canManage || scheduled || starting || stopping}
                >
                  {manual ? (
                    <StopCircleIcon fontSize="small" />
                  ) : (
                    <FiberManualRecordIcon fontSize="small" />
                  )}
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title={t("common.edit")}>
              <IconButton size="small" onClick={() => openEdit(p.row)} disabled={!canManage}>
                <EditIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title={t("common.delete")}>
              <IconButton
                size="small"
                color="error"
                onClick={() => remove(p.row)}
                disabled={!canManage}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </>
        );
      },
    },
  ];

  return (
    <Box>
      <Stack direction="row" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h4">{t("cameras.title")}</Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Tooltip title={t("common.refresh")}>
          <span>
            <IconButton onClick={() => refetch()} disabled={isFetching} sx={{ mr: 1 }}>
              <RefreshIcon />
            </IconButton>
          </span>
        </Tooltip>
        {canManage && (
          <Button variant="contained" startIcon={<AddIcon />} onClick={openAdd}>
            {t("cameras.add")}
          </Button>
        )}
      </Stack>

      <Card sx={{ border: "1px solid #2b3a4f" }}>
        <DataGrid
          autoHeight
          rows={cameras || []}
          columns={columns}
          loading={isLoading}
          disableRowSelectionOnClick
          pageSizeOptions={[10, 25, 50]}
          initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
          sx={{ border: 0, "& .MuiDataGrid-cell": { borderColor: "#2b3a4f" } }}
        />
      </Card>

      <CameraDialog
        open={dialogOpen}
        camera={editing}
        onClose={() => setDialogOpen(false)}
      />
    </Box>
  );
}
