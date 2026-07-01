/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111111",
        surface: "#FFFFFF",
        background: "#F8F9FA",
        primary: "#111111",
        accent: "#5B5BEF",
        success: "#22C55E",
        line: "#E7EAEE"
      },
      fontFamily: {
        display: ["'Inter'", "sans-serif"],
        body: ["'Inter'", "sans-serif"]
      },
      boxShadow: {
        glow: "0 24px 80px rgba(17, 17, 17, 0.12)"
      },
      animation: {
        "fade-up": "fadeUp 0.8s ease-out forwards"
      },
      keyframes: {
        fadeUp: {
          from: { opacity: "0", transform: "translateY(18px)" },
          to: { opacity: "1", transform: "translateY(0)" }
        }
      }
    }
  },
  plugins: []
};
