import {
  Box,
  Card,
  Chip,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import { DataGrid, GridColDef } from "@mui/x-data-grid";
import DownloadIcon from "@mui/icons-material/Download";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useTranslation } from "react-i18next";

import { useExportJobsQuery } from "../../api/endpoints";
import { useAppSelector } from "../../app/hooks";
import type { ExportJob } from "../../api/types";
import { authedDownload } from "../../utils/download";
import { formatBytes, formatDateTime } from "../../utils/format";

const STATUS_COLOR: Record<string, "default" | "info" | "success" | "error" | "warning"> = {
  pending: "default",
  running: "info",
  done: "success",
  failed: "error",
};

export default function ExportsPage() {
  const { t } = useTranslation();
  const token = useAppSelector((s) => s.auth.access);
  // Poll so queued → running → done transitions show without a manual refresh.
  const { data: jobs, isLoading, refetch, isFetching } = useExportJobsQuery(undefined, {
    pollingInterval: 5000,
  });

  const download = (job: ExportJob) => {
    if (!job.download_url) return;
    authedDownload(job.download_url, `export_${job.id}.mp4`, token).catch(() => {});
  };

  const columns: GridColDef<ExportJob>[] = [
    { field: "camera_name", headerName: t("events.camera"), flex: 1, minWidth: 130 },
    { field: "start", headerName: t("exports.from"), width: 170, valueFormatter: (v) => formatDateTime(v as string) },
    { field: "end", headerName: t("exports.to"), width: 170, valueFormatter: (v) => formatDateTime(v as string) },
    {
      field: "status",
      headerName: t("events.status"),
      width: 120,
      renderCell: (p) => <Chip size="small" color={STATUS_COLOR[p.value] || "default"} label={t(`exports.status.${p.value}`)} />,
    },
    {
      field: "size",
      headerName: t("exports.size"),
      width: 110,
      valueFormatter: (v) => ((v as number) ? formatBytes(v as number) : "—"),
    },
    {
      field: "sha256",
      headerName: "SHA‑256",
      width: 130,
      renderCell: (p) =>
        p.value ? (
          <Tooltip title={p.value}>
            <Typography variant="caption" dir="ltr" sx={{ fontFamily: "monospace" }}>
              {String(p.value).slice(0, 10)}…
            </Typography>
          </Tooltip>
        ) : (
          <span>—</span>
        ),
    },
    {
      field: "download",
      headerName: "",
      width: 70,
      sortable: false,
      renderCell: (p) => (
        <Tooltip title={t("exports.download")}>
          <span>
            <IconButton size="small" color="primary" onClick={() => download(p.row)} disabled={p.row.status !== "done"}>
              <DownloadIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
      ),
    },
  ];

  return (
    <Box>
      <Stack direction="row" alignItems="center" sx={{ mb: 2 }} spacing={1}>
        <Typography variant="h4" sx={{ flexGrow: 1 }}>{t("exports.title")}</Typography>
        <Tooltip title={t("common.refresh")}>
          <span><IconButton onClick={() => refetch()} disabled={isFetching}><RefreshIcon /></IconButton></span>
        </Tooltip>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{t("exports.hint")}</Typography>
      <Card sx={{ border: "1px solid #2b3a4f" }}>
        <DataGrid
          autoHeight
          rows={jobs || []}
          columns={columns}
          loading={isLoading}
          disableRowSelectionOnClick
          pageSizeOptions={[10, 25, 50]}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          sx={{ border: 0, "& .MuiDataGrid-cell": { borderColor: "#2b3a4f" } }}
        />
      </Card>
    </Box>
  );
}
