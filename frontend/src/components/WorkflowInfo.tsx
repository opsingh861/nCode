import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Workflow, Blocks, CheckCircle2, AlertTriangle } from 'lucide-react';
import { NodePreview } from '@/types/api';

interface WorkflowInfoProps {
  workflowName: string;
  nodes: NodePreview[];
}

export function WorkflowInfo({ workflowName, nodes }: WorkflowInfoProps) {
  const totalNodes = nodes.length;
  const supportedNodes = nodes.filter(n => n.handled).length;
  const unsupportedNodes = totalNodes - supportedNodes;

  return (
    <Card className="animate-fade-in-up">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xl">
          <Workflow className="w-6 h-6 text-indigo-400" />
          {workflowName || 'Uploaded Workflow'}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-6">
          <div className="flex items-center gap-2">
            <Blocks className="w-5 h-5 text-zinc-300" />
            <span className="text-2xl font-bold text-zinc-100">{totalNodes}</span>
            <span className="text-sm text-zinc-400">Total Nodes</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            <span className="text-2xl font-bold text-emerald-400">{supportedNodes}</span>
            <span className="text-sm text-emerald-400/80">Supported</span>
          </div>
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            <span className="text-2xl font-bold text-amber-400">{unsupportedNodes}</span>
            <span className="text-sm text-amber-400/80">Unsupported</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}