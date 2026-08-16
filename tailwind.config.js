/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        // "navy" token retained for backwards compatibility across the component
        // classes in input.css — values now carry Trustline's charcoal/black identity.
        navy: {
          900: "#121316",
          800: "#1B1D22",
          700: "#262932",
          600: "#3D4149",
        },
        gold: {
          100: "#FBEECB",
          400: "#E8B23A",
          500: "#D6A119",
        },
        cream: {
          100: "#FAFAF8",
          200: "#F1F0EC",
        },
        ink: {
          900: "#17181B",
          600: "#4A4D53",
          400: "#83868D",
        },
        line: "#E4E2DC",
      },
      fontFamily: {
        display: ["Poppins", "ui-sans-serif", "system-ui", "sans-serif"],
        body: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(18,19,22,0.06)",
        pop: "0 4px 16px -4px rgba(18,19,22,0.28)",
      },
      borderRadius: {
        xl2: "6px",
      },
    },
  },
  plugins: [],
};
