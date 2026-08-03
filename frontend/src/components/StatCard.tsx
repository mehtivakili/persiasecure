import { ReactNode } from "react";
import { alpha, Box, Card, CardContent, Typography } from "@mui/material";

interface Props {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  color?: string;
}

export default function StatCard({ label, value, icon, color = "#3da5ff" }: Props) {
  return (
    <Card
      sx={{
        height: "100%",
        position: "relative",
        overflow: "hidden",
        "&:hover": {
          transform: "translateY(-3px)",
          borderColor: alpha(color, 0.55),
          boxShadow: `0 14px 34px -18px ${alpha(color, 0.6)}`,
        },
        // Soft color wash in the corner
        "&::after": {
          content: '""',
          position: "absolute",
          width: 140,
          height: 140,
          borderRadius: "50%",
          background: alpha(color, 0.10),
          filter: "blur(30px)",
          top: -50,
          insetInlineStart: -30,
          pointerEvents: "none",
        },
      }}
    >
      <CardContent sx={{ display: "flex", alignItems: "center", gap: 2 }}>
        <Box
          sx={{
            width: 52,
            height: 52,
            borderRadius: 2.5,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            color: "#fff",
            background: `linear-gradient(135deg, ${alpha(color, 0.95)}, ${alpha(color, 0.55)})`,
            boxShadow: `0 10px 24px -10px ${alpha(color, 0.8)}`,
          }}
        >
          {icon}
        </Box>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h5" sx={{ fontWeight: 900, lineHeight: 1.2 }}>
            {value}
          </Typography>
          <Typography variant="body2" color="text.secondary" noWrap>
            {label}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
}
