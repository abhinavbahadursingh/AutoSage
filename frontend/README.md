# AutoSage Frontend

Vite 8 + React 19 + TypeScript SPA. Full project documentation lives in the
[repository README](../README.md) (product surface, API, environment variables,
core flows).

## Stack

- **Vite 8** + **React 19** + **TypeScript**, **React Router 7**
- **Tailwind CSS 4**, **framer-motion**, **@xyflow/react** (graphs)
- **Monaco** (`@monaco-editor/react` bound to the locally bundled
  `monaco-editor` — no CDN, workers via `?worker` imports)
- **oxlint** for linting, `playwright-core` for headless verification probes

## Setup

```bash
npm install
cp .env.example .env.local        # defaults are correct for local dev
npm run dev                       # http://localhost:5173
```

The dev server proxies `/api` and `/health` to `VITE_BACKEND_ORIGIN`
(default `http://127.0.0.1:8000`) — requests are same-origin, so no CORS setup
is needed in development. SSE responses on `/stream` are exempted from proxy
buffering so verification frames arrive in real time.

## Commands

```bash
npm run dev      # Vite dev server (port 5173)
npx tsc -b       # type checking (also runs inside build)
npm run lint      # oxlint
npm run build     # tsc -b && vite build
npm run preview   # serve the production build
```

## Layout

```
src/
├── App.tsx              # routes, protected layout, page transitions
├── pages/               # one file per route (Objectives, Pipeline, Sandbox, Evidence, ...)
├── components/
│   ├── layout/          # Sidebar, PageHeader
│   ├── workspace/       # SandboxIDE, MonacoCodeEditor, FileTabs, Terminal
│   ├── verification/    # ObjectiveViews (objectives, checks, report, decisions)
│   ├── pipeline/ graph/ # plan analysis panel, pipeline graphs
│   └── ui/ anim/        # theme, toasts, transitions, motion primitives
├── lib/
│   ├── api.ts           # fetch client: base resolution, Bearer/dev-token auth, SSE
│   ├── objectiveRun.ts  # current run pointer (sessionStorage)
│   ├── pipelinePlanStore.ts
│   └── monacoSetup.ts   # loader.config({ monaco }) — local bundle
└── store/               # StoreProvider/useStore (auth, experiment stream + polling)
```

## Notes

- The production API base is `VITE_API_BASE_URL` (or `VITE_BACKEND_ORIGIN` + `/api/v1`).
- The local dev-token minter (`POST /auth/dev-token`) is only ever called from
  localhost or with `VITE_ALLOW_DEV_TOKEN=true`; production backends answer 404 there.
- Monaco is bundled locally, so the main JS chunk is ~5 MB (~1.3 MB gzip).
