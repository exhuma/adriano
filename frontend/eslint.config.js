import js from "@eslint/js";
import { withVueTs, vueTsConfigs } from "@vue/eslint-config-typescript";
import pluginVue from "eslint-plugin-vue";
import globals from "globals";

export default withVueTs(
  {
    name: "adriano/files-to-lint",
    files: ["**/*.{ts,vue}"],
  },
  {
    name: "adriano/ignores",
    ignores: ["**/dist/**", "**/node_modules/**", "**/coverage/**"],
  },
  js.configs.recommended,
  pluginVue.configs["flat/recommended"],
  vueTsConfigs.recommended,
  {
    name: "adriano/language-options",
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
  },
  {
    name: "adriano/rules",
    rules: {
      "vue/multi-word-component-names": "off",
      "vue/max-attributes-per-line": "off",
      "vue/singleline-html-element-content-newline": "off",
    },
  },
);
