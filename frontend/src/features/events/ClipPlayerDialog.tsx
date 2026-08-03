import { useEffect, useState } from "react";
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";

import { useAppSelector } from "../../app/hooks";

/** Fetches an event clip with the auth token and plays it inline. */
export default function ClipPlayerDialog({ url, onClose }: { url: string; onClose: () => void }) {
  const { t } = useTranslation();
  const token = useAppSelector((s) => s.auth.access);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
        if (!res.ok) throw new Error("clip fetch failed");
        const blob = await res.blob();
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      } catch {
        if (!cancelled) setError(true);
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url, token]);

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{t("events.playClip")}</DialogTitle>
      <DialogContent>
        <Box sx={{ aspectRatio: "16/9", bgcolor: "#000", display: "flex", alignItems: "center", justifyContent: "center" }}>
          {error ? (
            <Typography color="error">{t("events.clipFailed")}</Typography>
          ) : blobUrl ? (
            <video src={blobUrl} controls autoPlay style={{ width: "100%", height: "100%", objectFit: "contain" }} />
          ) : (
            <CircularProgress />
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t("common.close")}</Button>
      </DialogActions>
    </Dialog>
  );
}
