import { alpha, createTheme } from "@mui/material/styles";

/**
 * PersianSecure design system — "Security Operations" dark theme.
 *
 * Inspired by Genetec Security Desk: near-black canvas, layered graphite
 * surfaces, one strong azure accent, glowing state colors, generous radii,
 * and quiet borders that still read as panels. RTL, Vazirmatn.
 */

// ---- Design tokens -------------------------------------------------------
export const tokens = {
  bg: "#090c11", // page canvas
  surface: "#10151d", // cards / drawer / appbar
  surface2: "#161d28", // nested panels, dialogs
  surface3: "#1d2634", // hover / selected fills
  border: "#243044",
  borderStrong: "#33415a",
  primary: "#3da5ff",
  primaryDark: "#1f7fe0",
  teal: "#1cc8b5",
  success: "#3ddc84",
  warning: "#ffb020",
  error: "#ff5a5f",
  textPrimary: "#eaf1f8",
  textSecondary: "#8fa1b8",
  textDisabled: "#5a6b82",
};

const t = tokens;

export const theme = createTheme({
  direction: "rtl",
  palette: {
    mode: "dark",
    primary: { main: t.primary, dark: t.primaryDark },
    secondary: { main: t.teal },
    success: { main: t.success },
    warning: { main: t.warning },
    error: { main: t.error },
    info: { main: t.primary },
    divider: t.border,
    background: { default: t.bg, paper: t.surface },
    text: { primary: t.textPrimary, secondary: t.textSecondary, disabled: t.textDisabled },
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily: "Vazirmatn, Tahoma, sans-serif",
    h4: { fontWeight: 800, letterSpacing: "-0.02em", fontSize: "1.7rem" },
    h5: { fontWeight: 800, letterSpacing: "-0.01em" },
    h6: { fontWeight: 700, fontSize: "1.05rem" },
    subtitle1: { fontWeight: 700 },
    subtitle2: { fontWeight: 700, color: t.textSecondary },
    button: { fontWeight: 700, textTransform: "none" },
    caption: { letterSpacing: 0 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        html: { colorScheme: "dark" },
        body: {
          backgroundImage: [
            `radial-gradient(1000px 460px at 88% -8%, ${alpha(t.primary, 0.13)}, transparent 62%)`,
            `radial-gradient(800px 420px at -10% 108%, ${alpha(t.teal, 0.07)}, transparent 55%)`,
          ].join(","),
          backgroundAttachment: "fixed",
        },
        "::selection": { background: alpha(t.primary, 0.35) },
        "::-webkit-scrollbar": { width: 9, height: 9 },
        "::-webkit-scrollbar-thumb": {
          background: t.borderStrong,
          borderRadius: 9,
          border: `2px solid ${t.bg}`,
        },
        "::-webkit-scrollbar-track": { background: "transparent" },
        "@keyframes psPulse": {
          "0%": { boxShadow: `0 0 0 0 ${alpha(t.error, 0.5)}` },
          "70%": { boxShadow: `0 0 0 8px ${alpha(t.error, 0)}` },
          "100%": { boxShadow: `0 0 0 0 ${alpha(t.error, 0)}` },
        },
        "@keyframes psFadeUp": {
          from: { opacity: 0, transform: "translateY(6px)" },
          to: { opacity: 1, transform: "translateY(0)" },
        },

        // --- Jalali date picker (react-multi-date-picker) ---
        // Rendered through a portal into <body>; must sit above AppBar (1100)
        // and Dialog (1300), otherwise the calendar is invisible.
        ".rmdp-wrapper, .rmdp-container": { zIndex: 1500 },
        ".rmdp-wrapper.ps-calendar, .ps-calendar .rmdp-wrapper": {
          border: `1px solid ${t.borderStrong}`,
          borderRadius: 12,
          boxShadow: "0 24px 60px -20px rgba(0,0,0,.95)",
        },
        ".rmdp-day.rmdp-today span": { backgroundColor: `${t.teal} !important` },
        ".rmdp-day.rmdp-selected span:not(.highlight)": {
          backgroundColor: `${t.primary} !important`,
          boxShadow: "none",
        },
        ".rmdp-day:not(.rmdp-disabled):not(.rmdp-day-hidden) span:hover": {
          backgroundColor: `${t.surface3} !important`,
        },
        ".rmdp-arrow": { borderColor: t.textSecondary },
        ".rmdp-arrow-container:hover": { backgroundColor: t.surface3 },
      },
    },

    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: alpha(t.surface, 0.82),
          backdropFilter: "blur(14px)",
          borderBottom: `1px solid ${t.border}`,
          backgroundImage: "none",
        },
      },
    },

    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: t.surface,
          backgroundImage: "none",
          borderInlineStart: `1px solid ${t.border}`,
        },
      },
    },

    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: "none" },
        outlined: { borderColor: t.border },
      },
    },

    MuiCard: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          backgroundColor: t.surface,
          border: `1px solid ${t.border}`,
          borderRadius: 16,
          boxShadow: "0 1px 2px rgba(0,0,0,.45), 0 12px 32px -24px rgba(0,0,0,.9)",
          transition: "border-color .2s ease, transform .2s ease, box-shadow .2s ease",
          animation: "psFadeUp .35s ease both",
        },
      },
    },

    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: 10, paddingInline: 16 },
        containedPrimary: {
          background: `linear-gradient(135deg, ${t.primary} 0%, ${t.primaryDark} 100%)`,
          boxShadow: `0 6px 18px -8px ${alpha(t.primary, 0.7)}`,
          "&:hover": {
            background: `linear-gradient(135deg, ${alpha(t.primary, 0.9)} 0%, ${t.primaryDark} 100%)`,
            boxShadow: `0 8px 22px -8px ${alpha(t.primary, 0.85)}`,
          },
        },
        outlined: { borderColor: t.borderStrong, "&:hover": { borderColor: t.primary, background: alpha(t.primary, 0.06) } },
      },
    },

    MuiIconButton: {
      styleOverrides: {
        root: { transition: "background .15s ease, color .15s ease" },
      },
    },

    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: alpha("#ffffff", 0.025),
          borderRadius: 10,
          "& .MuiOutlinedInput-notchedOutline": { borderColor: t.border },
          "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: t.borderStrong },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
            borderColor: t.primary,
            boxShadow: `0 0 0 3px ${alpha(t.primary, 0.18)}`,
          },
        },
      },
    },

    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 700, borderRadius: 8 },
        outlined: { borderColor: t.borderStrong },
      },
    },

    MuiTabs: {
      styleOverrides: {
        root: {
          minHeight: 44,
          backgroundColor: t.surface,
          border: `1px solid ${t.border}`,
          borderRadius: 12,
          padding: 4,
          display: "inline-flex",
        },
        indicator: { display: "none" },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          minHeight: 36,
          borderRadius: 9,
          fontWeight: 700,
          color: t.textSecondary,
          "&.Mui-selected": {
            color: "#fff",
            backgroundColor: t.surface3,
            boxShadow: `inset 0 0 0 1px ${t.borderStrong}`,
          },
        },
      },
    },

    MuiListSubheader: {
      styleOverrides: {
        root: {
          background: "transparent",
          color: t.textDisabled,
          fontWeight: 800,
          fontSize: 11,
          letterSpacing: ".06em",
          lineHeight: 2.6,
        },
      },
    },

    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          transition: "background .15s ease",
          "&:hover": { backgroundColor: t.surface3 },
        },
      },
    },

    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundColor: t.surface2,
          border: `1px solid ${t.borderStrong}`,
          borderRadius: 18,
          backgroundImage: "none",
        },
      },
    },
    MuiDialogTitle: { styleOverrides: { root: { fontWeight: 800 } } },

    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          backgroundColor: t.surface3,
          border: `1px solid ${t.borderStrong}`,
          fontSize: 12,
          fontWeight: 600,
        },
      },
    },

    MuiMenu: {
      styleOverrides: {
        paper: { backgroundColor: t.surface2, border: `1px solid ${t.border}` },
      },
    },

    MuiLinearProgress: {
      styleOverrides: {
        root: { borderRadius: 6, backgroundColor: t.surface3 },
      },
    },

    MuiTableCell: { styleOverrides: { root: { borderColor: t.border } } },

    MuiDataGrid: {
      styleOverrides: {
        root: {
          border: "none",
          "--DataGrid-rowBorderColor": t.border,
          fontSize: 13.5,
          "& .MuiDataGrid-columnHeaders": {
            backgroundColor: alpha("#ffffff", 0.03),
            borderBottom: `1px solid ${t.borderStrong}`,
          },
          "& .MuiDataGrid-columnHeaderTitle": { fontWeight: 800, color: t.textSecondary },
          "& .MuiDataGrid-cell": { borderColor: t.border },
          "& .MuiDataGrid-footerContainer": { borderColor: t.borderStrong },
          "& .MuiDataGrid-row:hover": { backgroundColor: alpha(t.primary, 0.06) },
          "& .MuiDataGrid-row.Mui-selected": { backgroundColor: alpha(t.primary, 0.12) },
        },
      },
    },
  } as any,
});
