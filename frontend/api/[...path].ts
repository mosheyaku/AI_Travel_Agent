
import type { VercelRequest, VercelResponse } from "@vercel/node";

const ALLOWED_ROUTES = new Set([
  "health",
  "trips/generate",
  "places/accommodations",
]);

export default async function handler(
  request: VercelRequest,
  response: VercelResponse,
): Promise<void> {
  const backendUrl = process.env.BACKEND_URL;

  if (!backendUrl) {
    response.status(500).json({
      detail: "Backend URL is not configured.",
    });
    return;
  }

  const rawPath = request.query.path;
  const segments = Array.isArray(rawPath)
    ? rawPath
    : rawPath
      ? [rawPath]
      : [];

  const path = segments.join("/");

  if (!ALLOWED_ROUTES.has(path)) {
    response.status(404).json({
      detail: "API route not found.",
    });
    return;
  }

  const allowedMethod =
    path === "health" || path === "places/accommodations"
      ? "GET"
      : "POST";

  if (request.method !== allowedMethod) {
    response.setHeader("Allow", allowedMethod);
    response.status(405).json({
      detail: "Method not allowed.",
    });
    return;
  }

  const target = new URL(
    `${backendUrl.replace(/\/+$/, "")}/${path}`,
  );

  for (const [key, value] of Object.entries(request.query)) {
    if (key === "path") continue;

    if (Array.isArray(value)) {
      for (const item of value) {
        target.searchParams.append(key, item);
      }
    } else if (value !== undefined) {
      target.searchParams.append(key, value);
    }
  }

  try {
    const upstream = await fetch(target, {
      method: allowedMethod,
      headers: {
        ...(allowedMethod === "POST"
          ? { "Content-Type": "application/json" }
          : {}),
      },
      body:
        allowedMethod === "POST"
          ? JSON.stringify(request.body)
          : undefined,
      signal: AbortSignal.timeout(240_000),
    });

    const contentType = upstream.headers.get("content-type");

    if (contentType) {
      response.setHeader("Content-Type", contentType);
    }

    const body = Buffer.from(await upstream.arrayBuffer());

    response.status(upstream.status).send(body);
  } catch {
    response.status(502).json({
      detail: "Unable to reach the backend service.",
    });
  }
}
