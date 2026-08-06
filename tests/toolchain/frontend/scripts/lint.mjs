import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = path.resolve("src");
const failures = [];
const forbiddenPatterns = [
  [/@ts-ignore|@ts-nocheck|eslint-disable/, "compiler/lint suppression directive"],
  [/\beval\s*\(/, "eval()"],
  [/dangerouslySetInnerHTML/, "dangerouslySetInnerHTML"],
  [/\.innerHTML\s*=/, "direct innerHTML assignment"],
];

function walk(directory) {
  return fs
    .readdirSync(directory, { withFileTypes: true })
    .flatMap((entry) => {
      const target = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        return walk(target);
      }
      return /\.(ts|tsx)$/.test(entry.name) ? [target] : [];
    });
}

for (const filename of walk(root)) {
  const source = fs.readFileSync(filename, "utf8");
  const lines = source.split(/\r?\n/);
  for (const [index, line] of lines.entries()) {
    for (const [pattern, label] of forbiddenPatterns) {
      if (pattern.test(line)) {
        failures.push(`${filename}:${index + 1}: forbidden ${label}`);
      }
    }
  }
}

if (failures.length > 0) {
  console.error("Frontend lint contract failed:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log("Frontend lint contract passed.");
