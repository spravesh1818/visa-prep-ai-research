/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111111",
        canvas: "#ffffff",
        "soft-cloud": "#f5f5f5",
        charcoal: "#39393b",
        ash: "#4b4b4d",
        mute: "#707072",
        stone: "#9e9ea0",
        hairline: "#cacacb",
        "hairline-soft": "#e5e5e5",
        sale: "#d30005",
        "sale-deep": "#780700",
        success: "#007d48",
        "success-bright": "#1eaa52",
        info: "#1151ff",
        "info-deep": "#0034e3",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      spacing: {
        section: "48px",
      },
      borderRadius: {
        pill: "30px",
        search: "24px",
      },
    },
  },
  plugins: [],
};
