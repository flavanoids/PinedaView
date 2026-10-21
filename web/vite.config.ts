// SPDX-License-Identifier: Apache-2.0
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { svelteTesting } from "@testing-library/svelte/vite";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

const API = process.env.VITE_API_URL ?? "http://localhost:8090";

export default defineConfig({
  build: { target: "es2020" },
  plugins: [
    svelte(),
    // Resolves Svelte to its client build under vitest so components can mount.
    svelteTesting(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.ico", "favicon.svg", "apple-touch-icon.png"],
      manifest: {
        name: "PinedaDisplay",
        short_name: "Pineda",
        display: "fullscreen",
        orientation: "any",
        background_color: "#000000",
        theme_color: "#000000",
        icons: [
          { src: "pwa-192.png", sizes: "192x192", type: "image/png" },
          { src: "pwa-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "pwa-maskable-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        navigateFallback: "index.html",
        // Pages the server renders itself, and the API: never the SPA shell.
        navigateFallbackDenylist: [/^\/(menu|upload|connect|api)(\/|$|\?)/],
        globPatterns: ["**/*.{js,css,html,otf,woff2,png,svg,ico}"],
        // Optional clock-face fonts: only the face a screen is set to should
        // pull its font. Keep them out of the precache; cache on first use.
        globIgnores: ["**/assets/{Anton,DSEG7Classic}-*"],
        runtimeCaching: [
          {
            urlPattern: /\/assets\/(Anton|DSEG7Classic)-[^/]+\.woff2$/,
            handler: "CacheFirst",
            options: {
              cacheName: "clock-face-fonts",
              expiration: { maxEntries: 4 },
            },
          },
        ],
      },
    }),
  ],
  server: {
    host: true,
    proxy: {
      "/api": { target: API, changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.{test,spec}.{ts,js}"],
  },
});
