/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Build-time fallback API base URL, used when no runtime config
   *  global is injected (local dev only). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
