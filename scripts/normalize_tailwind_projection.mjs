/** Canonicalize platform-sensitive color rounding in a generated Tailwind bundle. */

import { readFileSync, writeFileSync } from "node:fs";

const projectionPath = process.argv[2];

if (!projectionPath || process.argv.length !== 3) {
  throw new Error("usage: node normalize_tailwind_projection.mjs <projection.css>");
}

function compactDecimal(value) {
  const rounded = Number(value).toFixed(5).replace(/0+$/, "").replace(/\.$/, "");
  if (rounded === "-0") {
    return "0";
  }
  return rounded.replace(/^(-?)0\./, "$1.");
}

function canonicalizeOklab(body) {
  return body.replace(/-?(?:\d+\.\d*|\.\d+)/g, (value, offset) => {
    if (body[offset + value.length] === "%") {
      return value;
    }
    return compactDecimal(value);
  });
}

const source = readFileSync(projectionPath, "utf8");
const canonical = source
  .replace(/\r\n?/g, "\n")
  .replace(/oklab\(([^)]*)\)/g, (_match, body) => `oklab(${canonicalizeOklab(body)})`);

writeFileSync(projectionPath, canonical, "utf8");
