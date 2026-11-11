
import type { VercelRequest, VercelResponse } from "@vercel/node";

const ROUTES: Record<string, string> = {
  health: "GET",
  "trips/generate": "POST",
  "places/accommodations": "GET",
};

export default async function handler(
  request: VercelRequest,
  response: VercelResponse,
): Promise<void> {
  const route = request.query.route;

  if (typeof route !== "string" || !ROUTES[route]) {
    response.status(404).json({
      detail: "API route not found.",
    });
    return;
  }

  const method = ROUTES[route];

  if (request.method !== method) {
    response.setHeader("Allow", method);
    response.status(405).json({
      detail: "Method not allowed.",
    });
    return;
  }

  const backendUrl = process.env.BACKEND_URL;

  if (!backendUrl) {
    response.status(500).json({
      detail: "Backend URL is not configured.",
    });
    return;
  }

  const target = new URL(
    `${backendUrl.replace(/\/+$/, "")}/${route}`,
  );

  const incomingUrl = new URL(
    request.url ?? "/",
    "https://localhost",
  );

  for (const [key, value] of incomingUrl.searchParams) {
    if (key !== "route") {
      target.searchParams.append(key, value);
    }
  }

  try {
    const upstream = await fetch(target, {
      method,
      headers:
        method === "POST"
          ? { "Content-Type": "application/json" }
          : {},
      body:
        method === "POST"
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
