import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ShieldIcon from "@mui/icons-material/GppGood";
import VideocamIcon from "@mui/icons-material/Videocam";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";

import { useLoginMutation } from "../../api/endpoints";
import { useAppDispatch } from "../../app/hooks";
import { setCredentials } from "./authSlice";

export default function LoginPage() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const location = useLocation() as any;
  const [login, { isLoading }] = useLoginMutation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const res = await login({ username, password }).unwrap();
      dispatch(setCredentials(res as any));
      navigate(location.state?.from?.pathname || "/", { replace: true });
    } catch {
      setError(t("auth.error"));
    }
  };

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        position: "relative",
        overflow: "hidden",
        bgcolor: "#090c11",
        "@keyframes drift1": {
          "0%,100%": { transform: "translate(0,0) scale(1)" },
          "50%": { transform: "translate(-60px,40px) scale(1.15)" },
        },
        "@keyframes drift2": {
          "0%,100%": { transform: "translate(0,0) scale(1)" },
          "50%": { transform: "translate(50px,-30px) scale(1.1)" },
        },
      }}
    >
      {/* Ambient gradient orbs */}
      <Box
        sx={{
          position: "absolute",
          width: 560,
          height: 560,
          borderRadius: "50%",
          filter: "blur(120px)",
          background: "rgba(61,165,255,0.22)",
          top: -160,
          insetInlineEnd: -120,
          animation: "drift1 14s ease-in-out infinite",
        }}
      />
      <Box
        sx={{
          position: "absolute",
          width: 460,
          height: 460,
          borderRadius: "50%",
          filter: "blur(110px)",
          background: "rgba(28,200,181,0.14)",
          bottom: -140,
          insetInlineStart: -100,
          animation: "drift2 18s ease-in-out infinite",
        }}
      />

      {/* Brand side */}
      <Box
        sx={{
          flex: 1,
          display: { xs: "none", md: "flex" },
          flexDirection: "column",
          justifyContent: "center",
          px: 10,
          position: "relative",
          zIndex: 1,
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 3 }}>
          <Box
            sx={{
              width: 56,
              height: 56,
              borderRadius: 3,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "linear-gradient(135deg,#3da5ff,#1f7fe0)",
              boxShadow: "0 12px 34px -10px rgba(61,165,255,.8)",
            }}
          >
            <ShieldIcon sx={{ color: "#fff", fontSize: 34 }} />
          </Box>
          <Box>
            <Typography variant="h4" sx={{ fontWeight: 900 }}>
              {t("app.name")}
            </Typography>
            <Typography color="text.secondary">{t("app.tagline")}</Typography>
          </Box>
        </Stack>

        <Typography variant="h5" sx={{ maxWidth: 520, lineHeight: 1.9, fontWeight: 700 }}>
          {t("auth.hero")}
        </Typography>

        <Stack direction="row" spacing={1} sx={{ mt: 4 }} flexWrap="wrap" useFlexGap>
          <Chip icon={<VideocamIcon />} label={t("auth.feat1")} variant="outlined" />
        </Stack>
      </Box>

      {/* Form side */}
      <Box
        sx={{
          width: { xs: "100%", md: 480 },
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          p: 3,
          zIndex: 1,
        }}
      >
        <Box
          sx={{
            width: 380,
            maxWidth: "94vw",
            p: 4,
            borderRadius: 4,
            border: "1px solid #243044",
            bgcolor: "rgba(16,21,29,0.75)",
            backdropFilter: "blur(18px)",
            boxShadow: "0 30px 80px -30px rgba(0,0,0,.9)",
          }}
        >
          <Stack spacing={1} alignItems="center" sx={{ mb: 3, display: { md: "none" } }}>
            <ShieldIcon color="primary" sx={{ fontSize: 44 }} />
            <Typography variant="h5" sx={{ fontWeight: 900 }}>
              {t("app.name")}
            </Typography>
          </Stack>
          <Typography variant="h6" sx={{ mb: 0.5 }}>
            {t("auth.welcome")}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            {t("auth.sub")}
          </Typography>
          <form onSubmit={submit}>
            <Stack spacing={2}>
              {error && <Alert severity="error">{error}</Alert>}
              <TextField
                label={t("auth.username")}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                fullWidth
              />
              <TextField
                label={t("auth.password")}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                fullWidth
              />
              <Button type="submit" variant="contained" size="large" disabled={isLoading} fullWidth>
                {t("auth.signIn")}
              </Button>
            </Stack>
          </form>
          <Divider sx={{ my: 2.5 }} />
          <Typography variant="caption" color="text.secondary" display="block" textAlign="center">
            © {t("app.name")} — {t("app.tagline")}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
