import { rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const artifactRoot = path.join(projectDir, ".artifacts");
const outputRoot = path.join(artifactRoot, "e2e-outputs");

if (!outputRoot.startsWith(`${artifactRoot}${path.sep}`)) {
  throw new Error("refusing to clean an E2E output path outside .artifacts");
}

await rm(outputRoot, { recursive: true, force: true });
