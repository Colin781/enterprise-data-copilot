import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { extname, join } from "node:path";
import test from "node:test";

async function sourceFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return [".ts", ".tsx"].includes(extname(path)) ? [path] : [];
  }));
  return nested.flat();
}

test("frontend contains no dynamic code execution or raw HTML rendering path", async () => {
  const files = await sourceFiles(new URL("../src", import.meta.url).pathname);
  const forbidden = ["eval(", "new Function(", "dangerouslySetInnerHTML", "document.write("];
  for (const file of files) {
    const source = await readFile(file, "utf8");
    for (const token of forbidden) assert.equal(source.includes(token), false, `${file} contains ${token}`);
  }
});
