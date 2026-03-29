export function Footer() {
  return (
    <footer className="border-t border-zinc-800/50 py-6 mt-auto">
      <div className="max-w-7xl mx-auto px-4 md:px-8 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-zinc-600">
        <span>Built with nCode — n8n to Python Transpiler</span>
        <span>© {new Date().getFullYear()} nCode</span>
      </div>
    </footer>
  );
}
