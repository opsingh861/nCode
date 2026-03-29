import { useState, useCallback } from "react";
import type { UploadResponse } from "@/types/api";
import { uploadWorkflow, ApiClientError } from "@/api/client";

type WorkflowState = "idle" | "loading" | "success" | "error";

interface UseWorkflowReturn {
  state: WorkflowState;
  selectedFile: File | null;
  response: UploadResponse | null;
  error: string | null;
  setSelectedFile: (file: File | null) => void;
  upload: () => Promise<void>;
  reset: () => void;
}

export function useWorkflow(): UseWorkflowReturn {
  const [state, setState] = useState<WorkflowState>("idle");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [response, setResponse] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const upload = useCallback(async () => {
    if (!selectedFile) return;

    setState("loading");
    setError(null);

    try {
      const result = await uploadWorkflow(selectedFile);
      setResponse(result);
      setState("success");
    } catch (err) {
      const message =
        err instanceof ApiClientError
          ? err.message
          : err instanceof TypeError
            ? "Backend unavailable. Please check that the server is running."
            : "An unexpected error occurred.";
      setError(message);
      setState("error");
    }
  }, [selectedFile]);

  const reset = useCallback(() => {
    setState("idle");
    setSelectedFile(null);
    setResponse(null);
    setError(null);
  }, []);

  return { state, selectedFile, response, error, setSelectedFile, upload, reset };
}
