import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import * as ts from "typescript";

const root = path.resolve("src");
const failures = [];
const forbiddenDirectives = ["@ts-ignore", "@ts-nocheck", "eslint-disable"];

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

function visit(node, sourceFile) {
  if (
    ts.isCallExpression(node) &&
    ts.isIdentifier(node.expression) &&
    node.expression.text === "eval"
  ) {
    const { line, character } = sourceFile.getLineAndCharacterOfPosition(
      node.getStart(sourceFile),
    );
    failures.push(
      `${sourceFile.fileName}:${line + 1}:${character + 1}: eval() is forbidden`,
    );
  }

  if (
    ts.isJsxAttribute(node) &&
    ts.isIdentifier(node.name) &&
    node.name.text === "dangerouslySetInnerHTML"
  ) {
    const { line, character } = sourceFile.getLineAndCharacterOfPosition(
      node.getStart(sourceFile),
    );
    failures.push(
      `${sourceFile.fileName}:${line + 1}:${character + 1}: dangerouslySetInnerHTML is forbidden in the baseline fixture`,
    );
  }

  ts.forEachChild(node, (child) => visit(child, sourceFile));
}

for (const filename of walk(root)) {
  const source = fs.readFileSync(filename, "utf8");
  for (const directive of forbiddenDirectives) {
    if (source.includes(directive)) {
      failures.push(`${filename}: forbidden suppression directive ${directive}`);
    }
  }

  const kind = filename.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sourceFile = ts.createSourceFile(
    filename,
    source,
    ts.ScriptTarget.Latest,
    true,
    kind,
  );
  for (const diagnostic of sourceFile.parseDiagnostics) {
    const start = diagnostic.start ?? 0;
    const { line, character } = sourceFile.getLineAndCharacterOfPosition(start);
    failures.push(
      `${filename}:${line + 1}:${character + 1}: ${ts.flattenDiagnosticMessageText(diagnostic.messageText, " ")}`,
    );
  }
  visit(sourceFile, sourceFile);
}

if (failures.length > 0) {
  console.error("Frontend lint contract failed:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log("Frontend lint contract passed.");
