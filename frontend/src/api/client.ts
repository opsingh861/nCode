import type { UploadResponse, SupportedNodesResponse } from "@/types/api";

const API_BASE = "/api";

class ApiClientError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: unknown
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    const message =
      typeof detail === "object" && detail !== null && "detail" in detail
        ? String((detail as Record<string, unknown>).detail)
        : `Request failed with status ${response.status}`;
    throw new ApiClientError(message, response.status, detail);
  }
  return response.json() as Promise<T>;
}

export async function uploadWorkflow(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData,
  });

  return handleResponse<UploadResponse>(response);
}

export function getDownloadUrl(downloadId: string): string {
  return `${API_BASE}/download/${encodeURIComponent(downloadId)}`;
}

export async function getSupportedNodes(): Promise<SupportedNodesResponse> {
  const response = await fetch(`${API_BASE}/supported-nodes`);
  return handleResponse<SupportedNodesResponse>(response);
}

export { ApiClientError };
