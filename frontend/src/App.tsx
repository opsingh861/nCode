import { Toaster, toast } from "sonner";
import { useWorkflow } from "@/hooks/useWorkflow";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { HeroUpload } from "@/components/HeroUpload";
import { ResultsPanel } from "@/components/ResultsPanel";
import { useEffect } from "react";

export default function App() {
  const { state, selectedFile, response, error, setSelectedFile, upload, reset } =
    useWorkflow();

  // Show error toast when error state changes
  useEffect(() => {
    if (error) {
      toast.error(error);
    }
  }, [error]);

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 pt-16">
        {state === "success" && response ? (
          <ResultsPanel response={response} onReset={reset} />
        ) : (
          <HeroUpload
            selectedFile={selectedFile}
            state={state}
            error={error}
            onFileSelect={setSelectedFile}
            onUpload={upload}
            onReset={reset}
          />
        )}
      </main>
      <Footer />
      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          style: {
            background: "rgba(24, 24, 27, 0.9)",
            border: "1px solid rgba(63, 63, 70, 0.5)",
            color: "#e4e4e7",
            backdropFilter: "blur(12px)",
          },
        }}
      />
    </div>
  );
}
