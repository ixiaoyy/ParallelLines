import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "../../..");
const defaultSchemaPath = resolve(repoRoot, "apps/api/openapi/openapi.json");
const defaultOutputPath = resolve(repoRoot, "apps/web/src/shared/api/generated.ts");
const args = new Set(process.argv.slice(2));
const check = args.has("--check");

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function schemaNameFromRef(ref) {
  return ref.replace("#/components/schemas/", "");
}

function quoteKey(key) {
  return /^[A-Za-z_$][A-Za-z0-9_$]*$/.test(key) ? key : JSON.stringify(key);
}

function literal(value) {
  return JSON.stringify(value);
}

function typeForSchema(schema, components) {
  if (!schema || typeof schema !== "object") {
    return "unknown";
  }
  if (schema.$ref) {
    return `components["schemas"]["${schemaNameFromRef(schema.$ref)}"]`;
  }
  if (Array.isArray(schema.anyOf)) {
    return schema.anyOf.map((item) => typeForSchema(item, components)).join(" | ");
  }
  if (Array.isArray(schema.oneOf)) {
    return schema.oneOf.map((item) => typeForSchema(item, components)).join(" | ");
  }
  if (Array.isArray(schema.allOf)) {
    return schema.allOf.map((item) => typeForSchema(item, components)).join(" & ");
  }
  if (Array.isArray(schema.enum)) {
    return schema.enum.map(literal).join(" | ") || "unknown";
  }
  if (Object.hasOwn(schema, "const")) {
    return literal(schema.const);
  }
  if (schema.type === "null") {
    return "null";
  }
  if (schema.type === "string") {
    return "string";
  }
  if (schema.type === "integer" || schema.type === "number") {
    return "number";
  }
  if (schema.type === "boolean") {
    return "boolean";
  }
  if (schema.type === "array") {
    return `Array<${typeForSchema(schema.items, components)}>`;
  }
  if (schema.type === "object" || schema.properties || schema.additionalProperties) {
    const props = schema.properties ?? {};
    const required = new Set(schema.required ?? []);
    const lines = Object.entries(props).map(([key, value]) => {
      const optional = required.has(key) ? "" : "?";
      return `      ${quoteKey(key)}${optional}: ${typeForSchema(value, components)};`;
    });
    if (schema.additionalProperties) {
      const additional =
        schema.additionalProperties === true
          ? "unknown"
          : typeForSchema(schema.additionalProperties, components);
      lines.push(`      [key: string]: ${additional};`);
    }
    if (lines.length === 0) {
      return "Record<string, unknown>";
    }
    return `{
${lines.join("\n")}
    }`;
  }
  return "unknown";
}

function operationType(operation, components) {
  const responses = operation.responses ?? {};
  const success = responses["200"] ?? responses["201"] ?? responses["204"] ?? responses.default;
  const content = success?.content?.["application/json"]?.schema;
  return content ? typeForSchema(content, components) : "unknown";
}

function build(schema) {
  const schemas = schema.components?.schemas ?? {};
  const schemaEntries = Object.keys(schemas)
    .sort((a, b) => a.localeCompare(b))
    .map((name) => `    ${quoteKey(name)}: ${typeForSchema(schemas[name], schemas)};`);

  const pathEntries = Object.entries(schema.paths ?? {})
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([path, methods]) => {
      const methodEntries = Object.entries(methods)
        .filter(([method]) => ["get", "post", "put", "patch", "delete"].includes(method))
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([method, operation]) => {
          const responseType = operationType(operation, schemas);
          return `      ${quoteKey(method)}: { response: ${responseType}; operationId: ${literal(
            operation.operationId ?? "",
          )} };`;
        });
      return `    ${quoteKey(path)}: {
${methodEntries.join("\n")}
    };`;
    });

  return `// Generated from apps/api/openapi/openapi.json by apps/web/scripts/generate-openapi-types.mjs.
// Do not edit by hand. Run: pnpm --dir apps/web openapi:types

export interface components {
  schemas: {
${schemaEntries.join("\n")}
  };
}

export interface paths {
${pathEntries.join("\n")}
}

export type ApiSchema<Name extends keyof components["schemas"]> = components["schemas"][Name];
export type ApiPath<Name extends keyof paths> = paths[Name];
`;
}

const schema = readJson(defaultSchemaPath);
const content = build(schema);

if (check) {
  if (!existsSync(defaultOutputPath)) {
    console.error(`Generated OpenAPI types missing: ${defaultOutputPath}`);
    process.exit(1);
  }
  const current = readFileSync(defaultOutputPath, "utf8");
  if (current !== content) {
    console.error("Generated OpenAPI types are stale. Run: pnpm --dir apps/web openapi:types");
    process.exit(1);
  }
  process.exit(0);
}

writeFileSync(defaultOutputPath, content, "utf8");
console.log(`Wrote ${defaultOutputPath}`);
