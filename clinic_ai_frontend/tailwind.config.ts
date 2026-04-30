import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        clinic: {
          sidebar: "#0f1b3d",
          sidebarMuted: "#142551",
          sidebarText: "#c2cce7",
          primary: "#5b5de6",
          primaryDark: "#4f51cf",
          surface: "#f2f4f8",
          card: "#ffffff",
          border: "#e6eaf2",
          ink: "#111827",
          muted: "#6b7280",
          success: "#0f9d69",
          warning: "#f59e0b",
          danger: "#dc2626",
          info: "#2563eb",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      fontSize: {
        h1: ["1.875rem", { lineHeight: "2.25rem", fontWeight: "700" }],
        h2: ["1.5rem", { lineHeight: "2rem", fontWeight: "700" }],
        h3: ["1.125rem", { lineHeight: "1.625rem", fontWeight: "600" }],
        body: ["0.9375rem", { lineHeight: "1.5rem", fontWeight: "400" }],
        caption: ["0.8125rem", { lineHeight: "1.25rem", fontWeight: "500" }],
      },
      borderRadius: {
        "2xl": "1rem",
      },
      transitionDuration: {
        200: "200ms",
      },
    },
  },
  plugins: [],
};

export default config;
