import React, { useRef, useState } from "react";
import { FileJson, Upload, Sparkles, X, AlertCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface HeroUploadProps {
  selectedFile: File | null;
  state: "idle" | "loading" | "success" | "error";
  error: string | null;
  onFileSelect: (file: File | null) => void;
  onUpload: () => void;
  onReset: () => void;
}

function formatBytes(bytes: number, decimals = 2) {
  if (!+bytes) return "0 Bytes";
  const k = 1024;
  const dm = Math.max(0, decimals);
  const sizes = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

export function HeroUpload({
  selectedFile,
  state,
  error,
  onFileSelect,
  onUpload,
  onReset,
}: HeroUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (file.name.endsWith(".json")) {
        onFileSelect(file);
      }
      e.dataTransfer.clearData();
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFileSelect(e.target.files[0]);
    }
  };

  const triggerFileInput = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  return (
    <div className="flex flex-col items-center justify-center w-full py-12 px-4 space-y-12">
      {/* Hero Text */}
      <div className="text-center space-y-4">
        <h1 className="text-3xl md:text-5xl font-bold text-zinc-100 tracking-tight">
          Convert n8n workflows <span className="text-gradient">to Python</span>
        </h1>
        <p className="text-zinc-400 text-lg md:text-xl max-w-2xl mx-auto">
          Upload your workflow JSON and get a clean, runnable Python project
        </p>
      </div>

      {/* Upload Zone */}
      <div className="w-full max-w-2xl animate-fade-in-up">
        {state === "error" && error ? (
          <Card className="border-red-500/50 bg-red-950/20 mb-6">
            <CardContent className="p-6 flex flex-col items-center justify-center space-y-4 text-center">
              <AlertCircle className="w-12 h-12 text-red-500 mb-2" />
              <div className="space-y-1">
                <h3 className="text-lg font-medium text-red-200">Upload Failed</h3>
                <p className="text-red-400/80">{error}</p>
              </div>
              <Button variant="outline" className="mt-4 border-red-500/30 text-red-300 hover:bg-red-500/10 hover:text-red-200" onClick={onReset}>
                Try again
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Card
            className={cn(
              "border-2 border-dashed transition-all duration-200 ease-in-out",
              isDragging
                ? "border-indigo-500 bg-indigo-500/5"
                : "border-zinc-700 hover:border-indigo-500 hover:bg-zinc-900/50"
            )}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <CardContent className="p-10 flex flex-col items-center justify-center min-h-[250px] text-center">
              {!selectedFile ? (
                <>
                  <div
                    className={cn(
                      "p-4 rounded-full mb-6 transition-colors duration-200",
                      isDragging ? "bg-indigo-500/20" : "bg-zinc-800"
                    )}
                  >
                    <FileJson
                      className={cn(
                        "w-10 h-10 transition-colors duration-200",
                        isDragging ? "text-indigo-400" : "text-zinc-500"
                      )}
                    />
                  </div>
                  <h3 className="text-lg font-medium text-zinc-300 mb-2">
                    Drag & drop your n8n workflow
                  </h3>
                  <div className="flex items-center w-full max-w-xs my-4 opacity-50">
                    <div className="flex-1 h-px bg-zinc-600"></div>
                    <span className="px-4 text-sm text-zinc-400">or</span>
                    <div className="flex-1 h-px bg-zinc-600"></div>
                  </div>
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileInput}
                    accept=".json"
                    className="hidden"
                  />
                  <Button
                    variant="secondary"
                    onClick={triggerFileInput}
                    className="mt-2"
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Browse files
                  </Button>
                  <p className="mt-4 text-xs text-zinc-500">Accepted: .json files only</p>
                </>
              ) : (
                <div className="w-full flex flex-col items-center animate-fade-in-up">
                  <div className="flex items-center justify-between w-full max-w-md p-4 bg-zinc-800/50 rounded-lg border border-zinc-700/50 mb-8">
                    <div className="flex items-center space-x-4 overflow-hidden">
                      <div className="p-2 bg-indigo-500/20 rounded-md">
                        <FileJson className="w-6 h-6 text-indigo-400" />
                      </div>
                      <div className="flex flex-col items-start truncate text-left">
                        <span className="text-sm font-medium text-zinc-200 truncate w-48 sm:w-64">
                          {selectedFile.name}
                        </span>
                        <span className="text-xs text-zinc-500">
                          {formatBytes(selectedFile.size)}
                        </span>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => onFileSelect(null)}
                      className="text-zinc-400 hover:text-red-400 hover:bg-red-400/10"
                      disabled={state === "loading"}
                    >
                      <X className="w-5 h-5" />
                    </Button>
                  </div>

                  <Button
                    size="lg"
                    className="w-full max-w-md text-base"
                    onClick={onUpload}
                    disabled={state === "loading"}
                  >
                    {state === "loading" ? (
                      <>
                        <Loader2 className="w-5 h-5 mr-3 animate-spin" />
                        Transpiling...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-5 h-5 mr-3" />
                        Generate Python Code
                      </>
                    )}
                  </Button>
                  <p className="mt-6 text-xs text-zinc-500">
                    Your workflow stays local — no data is stored
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}