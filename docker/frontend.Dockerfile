# Frontend image: Vite dev server for the React SOC dashboard.
# For a production build serve the `dist/` output behind any static server;
# for the hackathon demo the dev server is simplest.
FROM node:20-alpine

WORKDIR /app

COPY package.json ./
# package-lock.json may not exist on a fresh checkout; install either way.
COPY package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

# --host so a browser on the Windows host can reach the container/VM.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
