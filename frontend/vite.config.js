import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dashboard talks to the FastAPI backend over REST + WebSocket.
// In dev, VITE_BACKEND_URL / VITE_WS_URL can point at the Ubuntu backend
// (e.g. http://<UBUNTU_IP>:8000). Defaults assume same-host dev.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // listen on 0.0.0.0 so a Windows browser can reach the VM
    port: 5173,
  },
  preview: {
    host: true,
    port: 5173,
  },
});
