import type { UploadResponse } from "@/types/api";
import { WorkflowInfo } from "./WorkflowInfo";
import { NodeList } from "./NodeList";
import { CodePreview } from "./CodePreview";
import { DownloadBar } from "./DownloadBar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";

interface ResultsPanelProps {
  response: UploadResponse;
  onReset: () => void;
}

export function ResultsPanel({ response, onReset }: ResultsPanelProps) {
  return (
    <section className="max-w-7xl mx-auto px-4 md:px-8 py-8 animate-fade-in-up space-y-6">
      <WorkflowInfo 
        workflowName={response.workflow_name} 
        nodes={response.nodes_preview} 
      />

      {/* Desktop View */}
      <div className="hidden md:grid md:grid-cols-5 gap-6">
        <div className="col-span-2">
          <NodeList nodes={response.nodes_preview} />
        </div>
        <div className="col-span-3">
          <CodePreview code={response.generated_code} />
        </div>
      </div>

      {/* Mobile View */}
      <div className="md:hidden">
        <Tabs defaultValue="nodes">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="nodes">Nodes</TabsTrigger>
            <TabsTrigger value="code">Code</TabsTrigger>
          </TabsList>
          <TabsContent value="nodes" className="mt-4">
            <NodeList nodes={response.nodes_preview} />
          </TabsContent>
          <TabsContent value="code" className="mt-4">
            <CodePreview code={response.generated_code} />
          </TabsContent>
        </Tabs>
      </div>

      <DownloadBar 
        downloadId={response.download_id} 
        code={response.generated_code} 
        workflowName={response.workflow_name} 
        onReset={onReset} 
      />
    </section>
  );
}
