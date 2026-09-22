import Link from "next/link";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8 text-center">
      <div className="max-w-3xl space-y-6">
        <div className="inline-flex items-center rounded-full border border-teal-500/30 bg-teal-500/10 px-4 py-1 text-sm font-medium text-teal-400">
          AutoSage Platform
        </div>
        <h1 className="text-5xl font-extrabold tracking-tight sm:text-6xl bg-gradient-to-r from-teal-400 via-cyan-400 to-blue-500 bg-clip-text text-transparent">
          Verified Multi-Agent AutoML
        </h1>
        <p className="text-lg text-slate-400">
          Convert natural-language ML requirements into empirically verified, leak-free, reproducible pipelines with complete evidence trails and sandboxed execution.
        </p>
        <div className="flex justify-center gap-4 pt-4">
          <Link
            href="/dashboard"
            className="rounded-lg bg-teal-500 px-6 py-3 font-semibold text-slate-950 hover:bg-teal-400 transition"
          >
            Launch Cockpit
          </Link>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="rounded-lg border border-slate-700 bg-slate-900 px-6 py-3 font-semibold text-slate-200 hover:bg-slate-800 transition"
          >
            Backend API Docs
          </a>
        </div>
      </div>
    </main>
  );
}
