/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Archivo", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        /* Grid Control type scale (rem, fixed) */
        index: ["10px", { lineHeight: "1.4", letterSpacing: "0.1em", fontWeight: "500" }],
        label: ["10px", { lineHeight: "1.4", letterSpacing: "0.08em", fontWeight: "500" }],
        meta: ["12px", { lineHeight: "1.5", letterSpacing: "0.005em" }],
        body: ["13px", { lineHeight: "1.5", letterSpacing: "-0.005em" }],
        emphasis: ["14px", { lineHeight: "1.45", letterSpacing: "-0.01em", fontWeight: "500" }],
        section: ["16px", { lineHeight: "1.35", letterSpacing: "-0.01em", fontWeight: "600" }],
        page: ["20px", { lineHeight: "1.25", letterSpacing: "-0.02em", fontWeight: "650" }],
        surface: ["28px", { lineHeight: "1.1", letterSpacing: "-0.03em", fontWeight: "650" }],
      },
      borderRadius: {
        lg: "var(--radius)",          /* 8px — overlays, dialogs */
        md: "calc(var(--radius) - 2px)", /* 6px — panels */
        sm: "calc(var(--radius) - 4px)", /* 4px — controls */
      },
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        surface: {
          DEFAULT: "hsl(var(--surface))",
          raised: "hsl(var(--surface-raised))",
        },
        faint: "hsl(var(--faint-foreground))",
        card: {
          DEFAULT: "hsl(var(--surface))",
          foreground: "hsl(var(--foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--surface-raised))",
          foreground: "hsl(var(--foreground))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        border: "hsl(var(--border))",
        borderStrong: "hsl(var(--border-strong))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        console: {
          DEFAULT: "hsl(var(--terminal-bg))",
          foreground: "hsl(var(--terminal-fg))",
        },
        /* Semantic state hues — hue confirms; symbol/line/label lead (§4) */
        healthy: "hsl(var(--state-healthy))",
        running: "hsl(var(--state-running))",
        degraded: "hsl(var(--state-degraded))",
        blocked: "hsl(var(--state-blocked))",
        pending: "hsl(var(--state-pending))",
        manual: "hsl(var(--state-manual))",
        failed: "hsl(var(--state-failed))",
        terminal: "hsl(var(--state-terminal))",
        chart: {
          '1': "hsl(var(--chart-1))",
          '2': "hsl(var(--chart-2))",
          '3': "hsl(var(--chart-3))",
          '4': "hsl(var(--chart-4))",
          '5': "hsl(var(--chart-5))",
        },
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
