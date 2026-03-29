import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { NodePreview } from '@/types/api';
import { Box } from 'lucide-react';

interface NodeListProps {
  nodes: NodePreview[];
}

export function NodeList({ nodes }: NodeListProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Box className="w-5 h-5 text-zinc-300" />
          Workflow Nodes
          <Badge variant="secondary" className="ml-2">
            {nodes.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="max-h-[500px] pr-4">
          {nodes.length === 0 ? (
            <div className="text-center py-8 text-zinc-500">
              No nodes found
            </div>
          ) : (
            <div className="flex flex-col">
              {nodes.map((node, index) => (
                <div
                  key={`${node.name}-${index}`}
                  className="flex items-center justify-between py-3 border-b border-zinc-800/50 last:border-0 animate-slide-in opacity-0"
                  style={{ 
                    animationDelay: `${index * 50}ms`, 
                    animationFillMode: 'forwards' 
                  }}
                >
                  <div className="flex flex-col gap-1">
                    <span className="text-sm font-medium text-zinc-100">
                      {node.name}
                    </span>
                    <span className="text-xs font-mono text-zinc-500">
                      {node.type}
                    </span>
                  </div>
                  <Badge variant={node.handled ? "success" : "destructive"}>
                    {node.handled ? "Supported" : "Unsupported"}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}