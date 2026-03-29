export function Header() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-zinc-950/80 backdrop-blur-xl border-b border-zinc-800/50">
      <div className="max-w-7xl mx-auto px-4 md:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <img
            src="/ncode-logo.png"
            alt="nCode"
            className="h-9"
          />
          <div>
            <h1 className="text-lg font-bold text-gradient">nCode</h1>
            <p className="text-xs text-zinc-500 -mt-0.5">n8n → Python Transpiler</p>
          </div>
        </div>
        <span className="text-xs text-zinc-600 font-mono">v1.0</span>
      </div>
    </header>
  );
}
