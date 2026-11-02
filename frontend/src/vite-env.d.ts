/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Build-time fallback API base URL, used when no runtime config
   *  global is injected (local dev only). */
  readonly VITE_API_BASE_URL?: string;
  /**
   * Dev-login opt-in. Deliberately **not** part of the runtime
   * config global (`RuntimeConfig` in `config.ts`): the dev-auth gate
   * must be a build-time literal so a production build's dead-code
   * elimination can remove the dev-login UI entirely (see
   * `module-dev-auth-bypass`). Combined with `import.meta.env.DEV`,
   * which Vite replaces with the literal `false` outside the dev
   * server, so this flag alone can never enable dev login in a
   * production build regardless of how it is set.
   */
  readonly VITE_DEV_AUTH?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
