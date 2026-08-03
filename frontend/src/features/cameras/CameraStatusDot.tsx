import { Box, Tooltip } from "@mui/material";
import { useTranslation } from "react-i18next";

const colors: Record<string, string> = {
  online: "#3ddc84",
  offline: "#ff5252",
  disabled: "#6b7480",
  unknown: "#ffb020",
};

export default function CameraStatusDot({ status }: { status: string }) {
  const { t } = useTranslation();
  return (
    <Tooltip title={t(`status.${status}`)}>
      <Box
        sx={{
          width: 12,
          height: 12,
          borderRadius: "50%",
          bgcolor: colors[status] || "#6b7480",
          boxShadow: `0 0 8px ${colors[status] || "#6b7480"}`,
          mx: 1,
          flexShrink: 0,
        }}
      />
    </Tooltip>
  );
}
