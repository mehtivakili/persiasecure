// Persian-friendly formatting helpers.

export function formatBytes(bytes: number): string {
  if (!bytes) return "۰";
  const units = ["بایت", "کیلوبایت", "مگابایت", "گیگابایت", "ترابایت"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const val = bytes / Math.pow(1024, i);
  return `${toFa(val.toFixed(i === 0 ? 0 : 1))} ${units[i]}`;
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("fa-IR", {
      dateStyle: "short",
      timeStyle: "medium",
      calendar: "persian",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function formatTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("fa-IR", { timeStyle: "medium" }).format(
      new Date(iso)
    );
  } catch {
    return iso;
  }
}

export function toFa(input: string | number): string {
  const map = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];
  return String(input).replace(/[0-9]/g, (d) => map[+d]);
}
