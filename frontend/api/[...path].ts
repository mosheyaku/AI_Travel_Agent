
import type { VercelRequest, VercelResponse } from "@vercel/node";

const ALLOWED_ROUTES: Record<string, string> = {
  "health": "GET",
  "trips/generate": "POST",
  "places/accommodations": "GET",
};

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

  const requestUrl = new URL(
    request.url ?? "/",
    "https://localhost",
  );

  const path = requestUrl.pathname.replace(/^\/api\//, "");
  const allowedMethod = ALLOWED_ROUTES[path];

  if (!allowedMethod) {
    response.status(404).json({
      detail: "API route not found.",
    });
    return;
  }

  if (request.method !== allowedMethod) {
    response.setHeader("Allow", allowedMethod);
    response.status(405).json({
      detail: "Method not allowed.",
    });
    return;
  }

  const targetUrl = new URL(
    `${backendUrl.replace(/\/+$/, "")}/${path}`,
  );

  targetUrl.search = requestUrl.search;

  try {
    const upstream = await fetch(targetUrl, {
      method: allowedMethod,
      headers:
        allowedMethod === "POST"
          ? { "Content-Type": "application/json" }
          : {},
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

    response
      .status(upstream.status)
      .send(Buffer.from(await upstream.arrayBuffer()));
  } catch {
    response.status(502).json({
      detail: "Unable to reach the backend service.",
    });
  }
}
