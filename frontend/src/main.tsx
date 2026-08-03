import React from "react";
import ReactDOM from "react-dom/client";
import { CacheProvider } from "@emotion/react";
import { CssBaseline, ThemeProvider } from "@mui/material";
import { Provider } from "react-redux";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { store } from "./app/store";
import ConfirmProvider from "./components/ConfirmProvider";
import "./i18n";
import { rtlCache } from "./theme/rtlCache";
import { theme } from "./theme/theme";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Provider store={store}>
      <CacheProvider value={rtlCache}>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <BrowserRouter>
            <ConfirmProvider>
              <App />
            </ConfirmProvider>
          </BrowserRouter>
        </ThemeProvider>
      </CacheProvider>
    </Provider>
  </React.StrictMode>
);
