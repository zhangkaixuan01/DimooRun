FROM node:22-alpine

WORKDIR /app/apps/console

COPY apps/console/package*.json ./
RUN npm ci

COPY apps/console ./
RUN npm run build

EXPOSE 5173

CMD ["node", "scripts/serve-dist.mjs", "--host", "0.0.0.0", "--port", "5173"]
