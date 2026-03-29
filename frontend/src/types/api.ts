export interface NodePreview {
  name: string;
  type: string;
  handled: boolean;
}

export interface UploadResponse {
  workflow_name: string;
  nodes_preview: NodePreview[];
  generated_code: string;
  download_id: string;
}

export interface SupportedNodesResponse {
  supported_types: string[];
  count: number;
}

export interface ApiError {
  detail: string | Record<string, unknown>[];
}
