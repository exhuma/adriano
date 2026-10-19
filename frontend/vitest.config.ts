import { fileURLToPath, URL } from "node:url";

import { mergeConfig, defineConfig, configDefaults } from "vitest/config";

import viteConfig from "./vite.config.ts";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      exclude: [...configDefaults.exclude, "e2e/**"],
      root: fileURLToPath(new URL("./", import.meta.url)),
      include: ["tests/**/*.test.ts"],
      setupFiles: ["tests/setup.ts"],
      // Vuetify's `vite-plugin-vuetify` auto-import injects
      // per-component CSS side-effect imports (e.g. `VIcon.css`);
      // without this, Vitest's SSR module runner tries to load them
      // as plain files and fails with "Unknown file extension .css".
      css: true,
      server: {
        // By default Vitest's SSR module runner externalizes
        // node_modules packages (plain Node `import`, bypassing
        // Vite's CSS transform). `vuetify` ships per-component `.css`
        // side-effect imports that only resolve through Vite, so it
        // must be inlined (transformed) instead of externalized.
        deps: { inline: ["vuetify"] },
      },
    },
  }),
);
