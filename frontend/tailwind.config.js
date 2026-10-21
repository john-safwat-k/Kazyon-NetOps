import kazyonNetopsPreset from "./tailwind/kazyon-netops.preset.js";

/** @type {import('tailwindcss').Config} */
export default {
  presets: [kazyonNetopsPreset],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {},
  },
  plugins: [],
};
