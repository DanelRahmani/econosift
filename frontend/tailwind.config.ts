import type { Config } from "tailwindcss";

// Colors are driven by CSS variables (RGB triplets) defined in globals.css,
// so every token switches with the .dark class. The <alpha-value> placeholder
// lets Tailwind opacity modifiers (e.g. bg-surface/80) keep working.
const c = (v: string) => `rgb(var(${v}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: c("--background"),
        surface: c("--surface"),
        "surface-alt": c("--surface-alt"),
        border: c("--border"),
        accent: c("--primary"),
        "accent-light": c("--primary-light"),
        "text-primary": c("--foreground"),
        "text-secondary": c("--text-secondary"),
        "text-muted": c("--text-muted"),
        success: c("--success"),
        warning: c("--warning"),
        danger: c("--danger"),
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Outfit", "Inter", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        sm: "0.25rem",
        md: "0.375rem",
        lg: "0.5rem",
        xl: "0.75rem",
      },
    },
  },
  plugins: [],
};

export default config;
