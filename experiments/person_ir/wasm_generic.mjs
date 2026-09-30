// One core-WASM host ABI for two conventional component programs. It is not
// a Component Model binary or WIT binding. Values live in the trusted host.
import { pathToFileURL } from "node:url";
import { readFileSync } from "node:fs";
import { section, str, uleb, vector } from "./wasm_baseline.mjs";

const local = index => [0x20, ...uleb(index)];
const set = index => [0x21, ...uleb(index)];
const constant = value => [0x41, ...uleb(value)];
const call = index => [0x10, ...uleb(index)];

export function genericModuleBytes(program, { forgeHandle = false,
                                               skipEquality = false,
                                               sourceIndex = null } = {}) {
  if (!["academic", "email"].includes(program)) throw new Error("unknown component program");
  // read, destination: i32 -> i32; field, pair, equal: (i32,i32)->i32;
  // propose: (i32,i32)->(); effect: (i32,i32,i32)->(); run: ()->().
  const types = section(1, vector(
    [0x60, ...vector([0x7f]), ...vector([0x7f])],
    [0x60, ...vector([0x7f], [0x7f]), ...vector([0x7f])],
    [0x60, ...vector([0x7f], [0x7f]), 0],
    [0x60, ...vector([0x7f], [0x7f], [0x7f]), 0],
    [0x60, 0, 0],
  ));
  const imports = section(2, vector(...[
    ["read", 0], ["field", 1], ["pair", 1], ["equal", 1],
    ["destination", 0], ["propose", 2], ["effect", 3],
  ].map(([name, type]) => [...str("host"), ...str(name), 0, type])));
  const functions = section(3, vector([4]));
  const exports = section(7, vector([...str("run"), 0, 7]));
  let instructions;
  if (program === "academic") {
    instructions = [
      ...constant(sourceIndex ?? 0), ...call(0), ...set(0),
      ...local(0), ...constant(0), ...call(1), ...set(2),
      ...constant(1), ...call(0), ...set(1),
      ...local(1), ...constant(1), ...call(1), ...set(3),
      ...local(2), ...local(3), ...call(2), ...set(4),
      ...constant(0), ...local(4), ...call(5),
    ];
  } else {
    instructions = [
      ...constant(0), ...call(0), ...set(0),
      ...constant(1), ...call(0), ...set(1),
      ...constant(sourceIndex ?? 2), ...call(0), ...set(2),
      ...constant(0), ...call(4), ...set(3),
      ...(skipEquality ? [] : [
        ...local(2), ...local(3), ...call(3), 0x45,
        0x04, 0x40, 0x00, 0x0b, // trap if recipient differs
      ]),
      ...(forgeHandle ? constant(999) : local(0)), ...local(1), ...call(2), ...set(4),
      ...local(4), ...local(2), ...call(2), ...set(5),
      ...constant(0), ...local(3), ...local(5), ...call(6),
    ];
  }
  const body = [1, 6, 0x7f, ...instructions, 0x0b];
  const code = section(10, vector([...uleb(body.length), ...body]));
  return new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0,
                         ...types, ...imports, ...functions, ...exports, ...code]);
}

export async function runGeneric(program, config, mutation = {}) {
  const values = new Map();
  let next = 1;
  const intern = (value, sources = [], protectedValue = false) => {
    const handle = next++;
    values.set(handle, { value, sources: [...sources], protectedValue });
    return handle;
  };
  const get = handle => {
    if (!values.has(handle)) throw new Error("unknown value handle");
    return values.get(handle);
  };
  const combine = (left, right, value) => intern(value,
    [...new Set([...left.sources, ...right.sources])],
    left.protectedValue || right.protectedValue);
  const at = (value, path) => {
    for (const key of path) {
      if (value === null || typeof value !== "object" || !Object.hasOwn(value, key))
        throw new Error("destination policy path missing");
      value = value[key];
    }
    return value;
  };
  let request = null;
  const imports = { host: {
    read(index) {
      const name = config.sourceNames[index];
      if (!config.manifest.sources.includes(name)) throw new Error("source not declared: " + name);
      const observation = config.observations[name];
      if (!observation || !["public", "protected"].includes(observation.label) ||
          typeof observation.source !== "string" || !observation.source)
        throw new Error("invalid host observation");
      return intern(observation.value, [observation.source], observation.label === "protected");
    },
    field(handle, index) {
      const object = get(handle);
      const key = config.fieldNames[index];
      if (!object.value || typeof object.value !== "object" ||
          Array.isArray(object.value) || !Object.hasOwn(object.value, key))
        throw new Error("unknown object field");
      return intern(object.value[key], object.sources, object.protectedValue);
    },
    pair(a, b) {
      const left = get(a), right = get(b);
      return combine(left, right, [left.value, right.value]);
    },
    equal(a, b) { return Number(JSON.stringify(get(a).value) === JSON.stringify(get(b).value)); },
    destination(index) {
      if (index !== 0) throw new Error("destination index not declared");
      return intern(config.destination);
    },
    propose(index, handle) {
      const target = config.targetNames[index];
      if (!config.manifest.commit_targets.includes(target))
        throw new Error("commit target not declared");
      const item = get(handle);
      request = { target, value: item.value, sources: item.sources,
                  label: item.protectedValue ? "protected" : "public" };
    },
    effect(index, destinationHandle, payloadHandle) {
      const kind = config.effectNames[index];
      const destination = get(destinationHandle).value;
      if (!config.manifest.effect_scopes.some(([k, d]) => k === kind && d === destination))
        throw new Error("effect scope not declared");
      const item = get(payloadHandle);
      const purpose = item.protectedValue ? config.disclosurePurpose : null;
      if (item.protectedValue && !config.manifest.disclosures.some(([d, p]) =>
        d === destination && p === purpose)) throw new Error("disclosure not declared");
      if (config.destinationPath && at(item.value, config.destinationPath) !== destination)
        throw new Error("payload destination mismatch");
      request = { kind, destination, payload: item.value,
                  label: item.protectedValue ? "protected" : "public",
                  disclosure_purpose: purpose, sources: item.sources };
    },
  }};
  const module = await WebAssembly.compile(genericModuleBytes(program, mutation));
  const instance = await WebAssembly.instantiate(module, imports);
  instance.exports.run();
  return request;
}

export function fixture(program) {
  if (program === "academic") return {
    sourceNames: ["deadline", "availability", "secret"],
    fieldNames: ["course", "free_slot"], targetNames: ["study_blocks"],
    effectNames: [], destination: "", disclosurePurpose: null,
    manifest: { sources: ["deadline", "availability"],
                commit_targets: ["study_blocks"], effect_scopes: [], disclosures: [] },
    observations: {
      deadline: { value: { course: "CSI 2110" }, source: "course:1", label: "protected" },
      availability: { value: { free_slot: "Thursday" }, source: "calendar:1", label: "protected" },
      secret: { value: "private", source: "secret:1", label: "protected" },
    },
  };
  if (program === "email") {
    const destination = "alice@example.com";
    return {
      sourceNames: ["context", "draft", "recipient", "secret"], fieldNames: [],
      targetNames: [], effectNames: ["email"], destination,
      destinationPath: [1], disclosurePurpose: "send requested email",
      manifest: { sources: ["context", "draft", "recipient"], commit_targets: [],
                  effect_scopes: [["email", destination]],
                  disclosures: [[destination, "send requested email"]] },
      observations: {
        context: { value: "meeting", source: "context:1", label: "protected" },
        draft: { value: "hello", source: "draft:1", label: "protected" },
        recipient: { value: destination, source: "recipient:1", label: "public" },
        secret: { value: "private", source: "secret:1", label: "protected" },
      },
    };
  }
  throw new Error("unknown program");
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const program = process.argv[2] || "academic";
  const scenario = process.argv[3] || "normal";
  try {
    if (program === "--json") {
      const input = JSON.parse(readFileSync(0, "utf8"));
      process.stdout.write(JSON.stringify({ ok: true, request: await runGeneric(
        input.program, input.config, input.mutation ?? {}) }) + "\n");
      process.exit(0);
    }
    const config = fixture(program);
    let mutation = {};
    if (scenario === "undeclared") mutation.sourceIndex = program === "academic" ? 2 : 3;
    if (scenario === "no_commit") config.manifest.commit_targets = [];
    if (scenario === "no_effect") config.manifest.effect_scopes = [];
    if (scenario === "no_disclosure") config.manifest.disclosures = [];
    if (scenario === "mismatch") config.observations.recipient.value = "bob@example.com";
    if (scenario === "forge") mutation.forgeHandle = true;
    if (scenario === "skip_equality") {
      config.observations.recipient.value = "bob@example.com";
      mutation.skipEquality = true;
    }
    process.stdout.write(JSON.stringify({ ok: true, request: await runGeneric(program, config, mutation) }) + "\n");
  } catch (error) {
    process.stdout.write(JSON.stringify({ ok: false, error: error.message }) + "\n");
  }
}
