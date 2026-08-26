#!/usr/bin/env node
import { cp, mkdir, rename, rm, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const prototypeRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(prototypeRoot, "../..");
const source = path.join(prototypeRoot, "dist", "client");
const destination = path.join(repoRoot, "studio", "client");
const staged = path.join(repoRoot, "studio", ".client-next");

const sourceIndex = path.join(source, "index.html");
if (!(await stat(sourceIndex).catch(() => null))?.isFile()) {
  throw new Error(`Missing local Studio build: ${sourceIndex}`);
}

await rm(staged, { recursive: true, force: true });
await mkdir(staged, { recursive: true });
await cp(source, staged, { recursive: true });
await rm(destination, { recursive: true, force: true });
await rename(staged, destination);

console.log(`Promoted Future Studio client to ${path.relative(repoRoot, destination)}`);
