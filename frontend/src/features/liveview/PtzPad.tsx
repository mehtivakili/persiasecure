import {
  Box,
  Card,
  CardContent,
  IconButton,
  Stack,
  Typography,
} from "@mui/material";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";
import ArrowDownwardIcon from "@mui/icons-material/ArrowDownward";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import AddIcon from "@mui/icons-material/Add";
import RemoveIcon from "@mui/icons-material/Remove";
import MyLocationIcon from "@mui/icons-material/MyLocation";
import { useTranslation } from "react-i18next";

import { usePtzMutation } from "../../api/endpoints";

export default function PtzPad({ cameraId }: { cameraId: number }) {
  const { t } = useTranslation();
  const [ptz] = usePtzMutation();

  const move = (pan: number, tilt: number, zoom = 0) =>
    ptz({ id: cameraId, action: "move", pan, tilt, zoom });
  const stop = () => ptz({ id: cameraId, action: "stop" });

  const dirBtn = (icon: React.ReactNode, pan: number, tilt: number) => (
    <IconButton
      onMouseDown={() => move(pan, tilt)}
      onMouseUp={stop}
      onMouseLeave={stop}
      sx={{ bgcolor: "#0f1216", border: "1px solid #2b3a4f" }}
    >
      {icon}
    </IconButton>
  );

  return (
    <Card sx={{ border: "1px solid #2b3a4f" }}>
      <CardContent>
        <Typography variant="subtitle1" sx={{ mb: 2 }}>
          {t("liveview.ptz")}
        </Typography>
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 44px)",
            gap: 1,
            justifyContent: "center",
          }}
        >
          <Box />
          {dirBtn(<ArrowUpwardIcon />, 0, 0.5)}
          <Box />
          {dirBtn(<ArrowBackIcon />, -0.5, 0)}
          <IconButton
            onClick={() => ptz({ id: cameraId, action: "stop" })}
            sx={{ bgcolor: "#0f1216", border: "1px solid #2b3a4f" }}
          >
            <MyLocationIcon fontSize="small" />
          </IconButton>
          {dirBtn(<ArrowForwardIcon />, 0.5, 0)}
          <Box />
          {dirBtn(<ArrowDownwardIcon />, 0, -0.5)}
          <Box />
        </Box>
        <Stack direction="row" spacing={1} justifyContent="center" sx={{ mt: 2 }}>
          <IconButton
            onMouseDown={() => move(0, 0, 0.5)}
            onMouseUp={stop}
            onMouseLeave={stop}
            sx={{ bgcolor: "#0f1216", border: "1px solid #2b3a4f" }}
          >
            <AddIcon />
          </IconButton>
          <IconButton
            onMouseDown={() => move(0, 0, -0.5)}
            onMouseUp={stop}
            onMouseLeave={stop}
            sx={{ bgcolor: "#0f1216", border: "1px solid #2b3a4f" }}
          >
            <RemoveIcon />
          </IconButton>
        </Stack>
      </CardContent>
    </Card>
  );
}
