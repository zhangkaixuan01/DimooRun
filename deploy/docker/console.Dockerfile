FROM node:22-alpine

WORKDIR /app/apps/console

COPY apps/console/package*.json ./
RUN npm ci

COPY apps/console ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
