import { Chip } from "@mui/material";
import { useTranslation } from "react-i18next";

const colorMap: Record<string, "info" | "warning" | "error"> = {
  info: "info",
  warning: "warning",
  critical: "error",
};

export default function SeverityChip({ severity }: { severity: string }) {
  const { t } = useTranslation();
  return (
    <Chip
      size="small"
      color={colorMap[severity] || "default"}
      label={t(`severity.${severity}`)}
    />
  );
}
