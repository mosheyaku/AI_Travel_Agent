
import type { VercelRequest, VercelResponse } from "@vercel/node";

export default async function handler(
  request: VercelRequest,
  response: VercelResponse,
): Promise<void> {
  if (request.method !== "POST") {
    response.setHeader("Allow", "POST");
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

  try {
    const upstream = await fetch(
      `${backendUrl.replace(/\/+$/, "")}/trips/generate`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request.body),
        signal: AbortSignal.timeout(240_000),
      },
    );

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
