// @ts-check
import nextConfig from "eslint-config-next";

/** @type {import("eslint").Linter.Config[]} */
const eslintConfig = [
  // ── Next.js 16 native flat config ─────────────────────────────────────────
  // Includes: @next/eslint-plugin-next, eslint-plugin-react,
  //           eslint-plugin-react-hooks, typescript-eslint,
  //           eslint-plugin-import, eslint-plugin-jsx-a11y.
  ...nextConfig,

  // ── ESLint 10 + eslint-plugin-react compatibility fix ─────────────────────
  // eslint-plugin-react ≤7.37.5 calls context.getFilename() which was removed
  // in ESLint 10. Providing an explicit version skips auto-detection and the
  // broken code path.
  {
    settings: {
      react: {
        version: "19.2.3",
      },
    },
  },

  // ── Project-level overrides ───────────────────────────────────────────────
  {
    rules: {
      // Allow `any` but warn — gradual adoption path.
      "@typescript-eslint/no-explicit-any": "warn",

      // Unused vars: error; ignore vars/args prefixed with _.
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],

      // React 19 — JSX transform, no need to import React.
      "react/react-in-jsx-scope": "off",

      // Prevent console.log left in production code.
      "no-console": ["warn", { allow: ["warn", "error"] }],

      // Enforce `import type` for type-only imports.
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { prefer: "type-imports", fixStyle: "inline-type-imports" },
      ],
    },
  },

  // ── Additional ignores ────────────────────────────────────────────────────
  {
    ignores: [
      // shadcn/ui generated components — managed by CLI, not hand-edited.
      "src/components/ui/**",
      // Test coverage output.
      "coverage/**",
    ],
  },
];

export default eslintConfig;
