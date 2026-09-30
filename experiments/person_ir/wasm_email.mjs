// A core-WASM email component with opaque value handles. Host imports are its
// only access to observations and request construction; no email is sent here.
import { pathToFileURL } from "node:url";
import { readFileSync } from "node:fs";
import { section, str, uleb, vector } from "./wasm_baseline.mjs";

export function emailModuleBytes(readIndices = [0, 1, 2], forgeHandle = false) {
  // read(i32)->i32; destination()->i32; equal(i32,i32)->i32;
  // send(i32,i32,i32)->(); run()->(). Values are host-owned handles.
  const types = section(1, vector(
    [0x60, ...vector([0x7f]), ...vector([0x7f])],
    [0x60, 0, ...vector([0x7f])],
    [0x60, ...vector([0x7f], [0x7f]), ...vector([0x7f])],
    [0x60, ...vector([0x7f], [0x7f], [0x7f]), 0],
    [0x60, 0, 0],
  ));
  const imports = section(2, vector(
    [...str("host"), ...str("read"), 0, 0],
    [...str("host"), ...str("destination"), 0, 1],
    [...str("host"), ...str("equal"), 0, 2],
    [...str("host"), ...str("send"), 0, 3],
  ));
  const functions = section(3, vector([4]));
  const exports = section(7, vector([...str("run"), 0, 4]));
  const reads = readIndices.flatMap((index, local) =>
    [0x41, ...uleb(index), 0x10, 0, 0x21, local]);
  const body = [
    1, 3, 0x7f, // three i32 locals
    ...reads,
    0x20, 2, 0x10, 1, 0x10, 2, 0x45, // !equal(recipient, destination)
    0x04, 0x40, 0x00, 0x0b, // trap on mismatch before requesting send
    ...(forgeHandle ? [0x41, ...uleb(99)] : [0x20, 0]),
    0x20, 1, 0x20, 2, 0x10, 3, 0x0b,
  ];
  const code = section(10, vector([...uleb(body.length), ...body]));
  return new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0,
                         ...types, ...imports, ...functions, ...exports, ...code]);
}

export async function runEmail({ manifest, observations, destination,
                                 readIndices = [0, 1, 2], forgeHandle = false }) {
  const names = ["context", "draft", "recipient", "secret"];
  const values = new Map();
  let nextId = 1;
  const intern = value => {
    const id = nextId++;
    values.set(id, value);
    return id;
  };
  const reads = [];
  let request = null;
  const imports = { host: {
    read(index) {
      const name = names[index];
      if (!manifest.sources.includes(name)) throw new Error("source not declared: " + name);
      const observation = observations[name];
      if (!observation || !["public", "protected"].includes(observation.label))
        throw new Error("invalid host observation: " + name);
      const handle = intern(observation.value);
      reads.push({ name, source: observation.source, label: observation.label, handle });
      return handle;
    },
    destination() { return intern(destination); },
    equal(left, right) {
      if (!values.has(left) || !values.has(right)) throw new Error("unknown value handle");
      return Number(JSON.stringify(values.get(left)) === JSON.stringify(values.get(right)));
    },
    send(contextId, draftId, recipientId) {
      if (reads.map(item => item.name).join(",") !== "context,draft,recipient")
        throw new Error("required observations were not read");
      if ([contextId, draftId, recipientId].some((id, index) => id !== reads[index].handle))
        throw new Error("request value does not match observed source");
      if (!manifest.effect_scopes.some(([kind, address]) =>
        kind === "email" && address === destination))
        throw new Error("effect scope not declared");
      if (values.get(recipientId) !== destination)
        throw new Error("recipient and destination differ");
      const protectedRead = reads.some(item => item.label === "protected");
      const purpose = protectedRead ? "send requested email" : null;
      if (protectedRead && !manifest.disclosures.some(([address, why]) =>
        address === destination && why === purpose))
        throw new Error("disclosure not declared");
      request = {
        kind: "email", destination,
        payload: [[values.get(contextId), values.get(draftId)], values.get(recipientId)],
        label: protectedRead ? "protected" : "public",
        disclosure_purpose: purpose,
        sources: reads.map(item => item.source),
      };
    },
  }};
  const module = await WebAssembly.compile(emailModuleBytes(readIndices, forgeHandle));
  const instance = await WebAssembly.instantiate(module, imports);
  instance.exports.run();
  return request;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const scenario = process.argv[2] || "email";
  if (scenario === "--json") {
    try {
      const config = JSON.parse(readFileSync(0, "utf8"));
      process.stdout.write(JSON.stringify({ ok: true, request: await runEmail(config) }) + "\n");
    } catch (error) {
      process.stdout.write(JSON.stringify({ ok: false, error: error.message }) + "\n");
    }
    process.exit(0);
  }
  const destination = "alice@example.com";
  const config = {
    manifest: {
      sources: ["context", "draft", "recipient"],
      effect_scopes: [["email", destination]],
      disclosures: [[destination, "send requested email"]],
    },
    observations: {
      context: { value: "meeting", source: "context:1", label: "protected" },
      draft: { value: "hello", source: "draft:1", label: "protected" },
      recipient: { value: scenario === "mismatch" ? "bob@example.com" : destination,
                   source: "recipient:1", label: "public" },
      secret: { value: "private", source: "secret:1", label: "protected" },
    },
    destination,
    readIndices: scenario === "undeclared" ? [0, 1, 3] : [0, 1, 2],
    forgeHandle: scenario === "forged_handle",
  };
  if (scenario === "no_disclosure") config.manifest.disclosures = [];
  if (scenario === "no_effect") config.manifest.effect_scopes = [];
  try {
    process.stdout.write(JSON.stringify({ ok: true, request: await runEmail(config) }) + "\n");
  } catch (error) {
    process.stdout.write(JSON.stringify({ ok: false, error: error.message }) + "\n");
  }
}
