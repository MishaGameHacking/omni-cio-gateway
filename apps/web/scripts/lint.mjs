import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const roots = ["src", "tests", "e2e"];
const failures = [];
const forbiddenPatterns = [
  [/@ts-ignore|@ts-nocheck|eslint-disable/, "compiler/lint suppression directive"],
  [/\beval\s*\(/, "eval()"],
  [/dangerouslySetInnerHTML/, "dangerouslySetInnerHTML"],
  [/\.innerHTML\s*=/, "direct innerHTML assignment"],
  [/localStorage|sessionStorage/, "browser Web Storage"],
  [/omni_cio\/real_trading|real_trading/, "direct Real authority reference"],
];

function walk(directory) {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) return walk(target);
    return /\.(ts|tsx)$/.test(entry.name) ? [target] : [];
  });
}

for (const root of roots) {
  for (const filename of walk(path.resolve(root))) {
    const source = fs.readFileSync(filename, "utf8");
    for (const [index, line] of source.split(/\r?\n/).entries()) {
      for (const [pattern, label] of forbiddenPatterns) {
        if (pattern.test(line)) failures.push(`${filename}:${index + 1}: forbidden ${label}`);
      }
    }
  }
}

if (failures.length) {
  console.error("Omni-CIO Web lint contract failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}
console.log("Omni-CIO Web lint contract passed.");
