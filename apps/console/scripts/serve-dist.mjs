import http from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const args = new Map();
for (let index = 2; index < process.argv.length; index += 2) {
  const key = process.argv[index];
  const value = process.argv[index + 1];
  if (key?.startsWith("--") && value) {
    args.set(key.slice(2), value);
  }
}

const host = args.get("host") || "127.0.0.1";
const port = Number(args.get("port") || "4173");
const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const distDir = path.join(rootDir, "dist");
const indexPath = path.join(distDir, "index.html");

if (!existsSync(indexPath)) {
  console.error("Missing dist/index.html. Run `npm run build:e2e` first.");
  process.exit(1);
}

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

const server = http.createServer((request, response) => {
  const url = new URL(request.url || "/", `http://${host}:${port}`);
  let filePath = path.join(distDir, url.pathname === "/" ? "index.html" : decodeURIComponent(url.pathname.slice(1)));
  if (!filePath.startsWith(distDir)) {
    response.writeHead(403);
    response.end("Forbidden");
    return;
  }
  if (!existsSync(filePath) || statSafe(filePath)?.isDirectory()) {
    filePath = indexPath;
  }
  const ext = path.extname(filePath);
  const body = readFileSync(filePath);
  response.writeHead(200, {
    "Content-Type": contentTypes[ext] || "application/octet-stream",
    "Cache-Control": "no-cache",
  });
  response.end(body);
});

server.listen(port, host, () => {
  console.log(`Console dist server ready on http://${host}:${port}`);
});

function statSafe(filePath) {
  try {
    return statSync(filePath);
  } catch {
    return null;
  }
}
