import { TextField } from "@mui/material";
import DatePicker, { DateObject } from "react-multi-date-picker";
import persian from "react-date-object/calendars/persian";
import persian_fa from "react-date-object/locales/persian_fa";
import "react-multi-date-picker/styles/backgrounds/bg-dark.css";

interface Props {
  label?: string;
  value: string; // ISO yyyy-mm-dd (Gregorian) — what the API expects
  onChange: (isoDate: string) => void;
  size?: "small" | "medium";
}

/**
 * Persian (Jalali / شمسی) calendar date picker that renders as an MUI TextField
 * but stores/emits a Gregorian ISO date so the backend stays calendar-agnostic.
 *
 * `portal` renders the calendar into document.body — without it the popup is
 * clipped by the parent Card's overflow and painted under the AppBar.
 * The matching z-index lives in theme.ts (MuiCssBaseline).
 */
export default function JalaliDatePicker({ label, value, onChange, size = "small" }: Props) {
  return (
    <DatePicker
      calendar={persian}
      locale={persian_fa}
      calendarPosition="bottom-right"
      className="bg-dark ps-calendar"
      portal
      value={value ? new Date(value) : ""}
      onChange={(d: DateObject | null) => {
        if (!d) return onChange("");
        const js = d.toDate();
        const iso = `${js.getFullYear()}-${String(js.getMonth() + 1).padStart(2, "0")}-${String(
          js.getDate()
        ).padStart(2, "0")}`;
        onChange(iso);
      }}
      render={(val: string, openCalendar: () => void) => (
        <TextField
          size={size}
          label={label}
          value={val || ""}
          onClick={openCalendar}
          InputProps={{ readOnly: true }}
          sx={{ minWidth: 180, cursor: "pointer" }}
        />
      )}
    />
  );
}
