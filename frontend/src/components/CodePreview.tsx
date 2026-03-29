import { useState, useCallback } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Check, FileCode } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

interface CodePreviewProps {
  code: string;
}

export function CodePreview({ code }: CodePreviewProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  return (
    <Card className="animate-fade-in-up">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
        <CardTitle className="flex items-center gap-2 text-base">
          <FileCode className="w-4 h-4 text-indigo-400" />
          Generated Python Code
        </CardTitle>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleCopy}
          className="gap-1.5 text-xs"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              Copy Code
            </>
          )}
        </Button>
      </CardHeader>
      <CardContent>
        <ScrollArea className="max-h-[600px] rounded-lg border border-zinc-800/50 bg-zinc-950/50">
          <SyntaxHighlighter
            language="python"
            style={oneDark}
            showLineNumbers
            customStyle={{
              background: "transparent",
              margin: 0,
              padding: "1rem",
              fontSize: "0.8125rem",
            }}
          >
            {code}
          </SyntaxHighlighter>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
