import { Box, Button, IconButton, Stack, TextField, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { useTranslation } from "react-i18next";

import type { TimeWindow, WeeklyWindows } from "../../api/types";

interface Props {
  value: WeeklyWindows;
  onChange: (v: WeeklyWindows) => void;
}

// Persian week order: 0 = Saturday … 6 = Friday (matches the backend evaluator).
const DAYS = [0, 1, 2, 3, 4, 5, 6];

/**
 * Editor for scheduled-recording weekly windows. Each day holds zero or more
 * {from,to} time ranges; a range where `from` > `to` wraps past midnight.
 */
export default function WeeklyScheduleEditor({ value, onChange }: Props) {
  const { t } = useTranslation();

  const windowsFor = (day: number): TimeWindow[] => value?.[String(day)] || [];

  const update = (day: number, windows: TimeWindow[]) => {
    const next: WeeklyWindows = { ...value };
    if (windows.length) next[String(day)] = windows;
    else delete next[String(day)];
    onChange(next);
  };

  const addWindow = (day: number) =>
    update(day, [...windowsFor(day), { from: "08:00", to: "18:00" }]);

  const setField = (day: number, idx: number, field: "from" | "to", v: string) => {
    const windows = windowsFor(day).map((w, i) => (i === idx ? { ...w, [field]: v } : w));
    update(day, windows);
  };

  const removeWindow = (day: number, idx: number) =>
    update(day, windowsFor(day).filter((_, i) => i !== idx));

  return (
    <Box>
      <Typography variant="caption" color="text.secondary">
        {t("cameras.weeklyHint")}
      </Typography>
      <Stack spacing={1} sx={{ mt: 1 }}>
        {DAYS.map((day) => {
          const windows = windowsFor(day);
          return (
            <Stack
              key={day}
              direction="row"
              spacing={1}
              alignItems="flex-start"
              sx={{ borderBottom: "1px solid rgba(255,255,255,0.06)", pb: 1 }}
            >
              <Typography variant="body2" sx={{ minWidth: 72, pt: 1, fontWeight: 600 }}>
                {t(`weekdays.${day}`)}
              </Typography>
              <Stack spacing={0.75} sx={{ flexGrow: 1 }}>
                {windows.length === 0 && (
                  <Typography variant="caption" color="text.disabled" sx={{ pt: 1 }}>
                    {t("cameras.noWindow")}
                  </Typography>
                )}
                {windows.map((w, idx) => (
                  <Stack key={idx} direction="row" spacing={1} alignItems="center">
                    <TextField
                      type="time"
                      size="small"
                      value={w.from}
                      onChange={(e) => setField(day, idx, "from", e.target.value)}
                      sx={{ width: 120 }}
                    />
                    <Typography variant="body2">—</Typography>
                    <TextField
                      type="time"
                      size="small"
                      value={w.to}
                      onChange={(e) => setField(day, idx, "to", e.target.value)}
                      sx={{ width: 120 }}
                    />
                    <IconButton size="small" onClick={() => removeWindow(day, idx)}>
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </Stack>
                ))}
              </Stack>
              <Button size="small" startIcon={<AddIcon />} onClick={() => addWindow(day)}>
                {t("cameras.addWindow")}
              </Button>
            </Stack>
          );
        })}
      </Stack>
    </Box>
  );
}
