import { useState, useCallback } from "react";
import { Download, Copy, Check, RotateCcw, Package } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getDownloadUrl } from "@/api/client";

interface DownloadBarProps {
  downloadId: string;
  code: string;
  workflowName: string;
  onReset: () => void;
}

export function DownloadBar({ downloadId, code, workflowName, onReset }: DownloadBarProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  const handleDownload = useCallback(() => {
    const link = document.createElement("a");
    link.href = getDownloadUrl(downloadId);
    link.download = `${workflowName}_python.zip`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [downloadId, workflowName]);

  return (
    <div className="sticky bottom-0 z-40 bg-zinc-950/90 backdrop-blur-xl border-t border-zinc-800/50 py-4 mt-6">
      <div className="max-w-7xl mx-auto px-4 md:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-emerald-600/20 border border-emerald-500/30">
            <Package className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-zinc-100">{workflowName}</p>
            <p className="text-xs text-zinc-500">Ready to download</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onReset}>
            <RotateCcw className="w-4 h-4" />
            New Upload
          </Button>
          <Button variant="secondary" size="sm" onClick={handleCopy}>
            {copied ? (
              <Check className="w-4 h-4 text-emerald-400" />
            ) : (
              <Copy className="w-4 h-4" />
            )}
            {copied ? "Copied!" : "Copy Code"}
          </Button>
          <Button size="lg" onClick={handleDownload}>
            <Download className="w-4 h-4" />
            Download ZIP
          </Button>
        </div>
      </div>
    </div>
  );
}
