/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#15233d",
        navy: "#173b73",
        canvas: "#f6f8fc",
        muted: "#72809a",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 8px 32px rgba(24, 45, 80, 0.06)",
      },
    },
  },
  plugins: [],
};
