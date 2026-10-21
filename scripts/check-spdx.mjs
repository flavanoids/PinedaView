// SPDX-License-Identifier: Apache-2.0
// Fails if any tracked source file is missing an SPDX license header.
import { execSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";

const EXTS = new Set([".ts", ".mjs", ".js", ".cjs", ".svelte", ".py", ".css"]);
const IGNORE = [
  /(^|\/)node_modules\//,
  /(^|\/)dist\//,
  /\.d\.ts$/,
  /\.gen\.ts$/,
  /generated\//,
];
const TAG = "SPDX-License-Identifier:";

const files = execSync("git ls-files", { encoding: "utf8" })
  .split("\n")
  .filter(Boolean)
  .filter((f) => EXTS.has(f.slice(f.lastIndexOf("."))))
  .filter((f) => !IGNORE.some((re) => re.test(f)));

const missing = files.filter((f) => {
  if (!existsSync(f)) return false; // staged deletion not yet committed
  const head = readFileSync(f, "utf8").split("\n").slice(0, 5).join("\n");
  return !head.includes(TAG);
});

if (missing.length) {
  console.error(`Missing ${TAG} header in ${missing.length} file(s):`);
  for (const f of missing) console.error(`  ${f}`);
  process.exit(1);
}
console.log(`SPDX headers present in all ${files.length} source files.`);
