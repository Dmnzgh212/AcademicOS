// Minimal core-WASM component experiment. The module has no ambient imports.
// Its entire host ABI is read(index) -> i32 and propose(course, slot) -> void.
import { pathToFileURL } from "node:url";

export const uleb = (value) => {
  const bytes = [];
  do {
    let byte = value & 127;
    value >>>= 7;
    if (value) byte |= 128;
    bytes.push(byte);
  } while (value);
  return bytes;
};
export const str = (value) => {
  const bytes = [...new TextEncoder().encode(value)];
  return [...uleb(bytes.length), ...bytes];
};
export const section = (id, bytes) => [id, ...uleb(bytes.length), ...bytes];
export const vector = (...entries) => [...uleb(entries.length), ...entries.flat()];

export function moduleBytes(readIndices = [0, 1]) {
  // read: (i32) -> i32; propose: (i32, i32) -> (); run: () -> ()
  const types = section(1, vector(
    [0x60, ...vector([0x7f]), ...vector([0x7f])],
    [0x60, ...vector([0x7f], [0x7f]), 0],
    [0x60, 0, 0],
  ));
  const imports = section(2, vector(
    [...str("host"), ...str("read"), 0, 0],
    [...str("host"), ...str("propose"), 0, 1],
  ));
  const functions = section(3, vector([2]));
  const exports = section(7, vector([...str("run"), 0, 2]));
  const body = [0, ...readIndices.flatMap(index => [0x41, ...uleb(index), 0x10, 0]),
                0x10, 1, 0x0b];
  const code = section(10, vector([...uleb(body.length), ...body]));
  return new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0,
                         ...types, ...imports, ...functions, ...exports, ...code]);
}

export async function runComponent({ manifest, observations, readIndices = [0, 1] }) {
  const reads = [];
  const allowed = new Set(manifest.sources);
  let proposal = null;
  const imports = { host: {
    read(index) {
      const source = ["course", "free_slot", "secret"][index];
      if (!allowed.has(source)) throw new Error("source not declared: " + source);
      reads.push(source);
      const value = observations[source];
      if (!Number.isInteger(value)) throw new TypeError("integer ABI input required");
      return value;
    },
    propose(course, slot) {
      if (!manifest.commit_targets.includes("study_blocks"))
        throw new Error("commit target not declared");
      if (reads.join(",") !== "course,free_slot")
        throw new Error("required observations were not read");
      proposal = { target: "study_blocks", value: [course, slot], sources: [...reads] };
    },
  }};
  const module = await WebAssembly.compile(moduleBytes(readIndices));
  const instance = await WebAssembly.instantiate(module, imports);
  instance.exports.run();
  return proposal;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const scenario = process.argv[2] || "academic";
  const config = {
    manifest: { sources: ["course", "free_slot"], commit_targets: ["study_blocks"] },
    observations: { course: 2110, free_slot: 4, secret: 99 },
    readIndices: scenario === "undeclared" ? [2, 1] : [0, 1],
  };
  if (scenario === "no_commit") config.manifest.commit_targets = [];
  try {
    process.stdout.write(JSON.stringify({ ok: true, proposal: await runComponent(config) }) + "\n");
  } catch (error) {
    process.stdout.write(JSON.stringify({ ok: false, error: error.message }) + "\n");
  }
}
