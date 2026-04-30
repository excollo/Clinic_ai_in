import React from "react";
import ReactDOM from "react-dom/client";
import { Toaster } from "sonner";
import { BrowserRouter } from "react-router-dom";
import App from "./app/App";
import "./i18n";
import "./styles/globals.css";
import { AppErrorBoundary } from "./components/AppErrorBoundary";
import { initSentry } from "./lib/sentry";

void initSentry();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
      <Toaster position="top-right" richColors closeButton visibleToasts={3} />
    </AppErrorBoundary>
  </React.StrictMode>,
);
