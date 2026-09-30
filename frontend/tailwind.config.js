/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        soc: {
          bg: "#080B10",
          panel: "#11161D",
          panel2: "#151C25",
          border: "#1E2833",
          muted: "#6B7A8D",
          text: "#D7E0EA",
          cyan: "#22D3EE",
          blue: "#3B82F6",
          amber: "#F59E0B",
          red: "#EF4444",
          green: "#22C55E",
        },
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
