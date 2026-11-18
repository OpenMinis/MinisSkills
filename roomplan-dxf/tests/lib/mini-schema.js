'use strict';
/**
 * Dependency-free JSON Schema validator (draft 2020-12 subset) used by
 * tests/test_schema.js.
 *
 * Supported keywords: $ref (internal, "#/$defs/..."), type (string or array of
 * strings, "null" included), const, enum, required, properties,
 * additionalProperties (boolean or schema), items, minItems, maxItems,
 * minimum, maximum, minLength, maxLength, pattern (ECMAScript RegExp),
 * oneOf, anyOf, allOf, not.
 *
 * Deliberately NOT supported (and rejected by checkSchemaDocument so a schema
 * can never silently rely on them): external $ref, $dynamicRef, unevaluated*,
 * if/then/else, dependentSchemas, patternProperties, propertyNames.
 *
 * The output of validate() is an array of {path, message}; an empty array
 * means the instance conforms.
 */
const pathStr = (p) => (p.length ? p.map((s) => (typeof s === 'number' ? `[${s}]` : `.${s}`)).join('').replace(/^\./, '') : '<root>');

function resolveRef(root, ref) {
  if (typeof ref !== 'string' || ref[0] !== '#') throw new Error(`Unsupported $ref (external or relative): ${ref}`);
  if (ref === '#') return root;
  if (!ref.startsWith('#/')) throw new Error(`Unsupported $ref form: ${ref}`);
  let node = root;
  for (const raw of ref.slice(2).split('/')) {
    const key = raw.replace(/~1/g, '/').replace(/~0/g, '~');
    if (node == null || typeof node !== 'object' || !(key in node)) throw new Error(`Unresolved $ref: ${ref}`);
    node = node[key];
  }
  return node;
}

function typeOf(v) {
  if (v === null) return 'null';
  if (Array.isArray(v)) return 'array';
  if (typeof v === 'number') return Number.isInteger(v) ? 'integer' : 'number';
  return typeof v;
}

function typeMatches(v, t) {
  const actual = typeOf(v);
  if (t === 'number') return actual === 'number' || actual === 'integer';
  if (t === 'integer') return actual === 'integer';
  return actual === t;
}

const KEYWORDS = new Set([
  '$schema', '$id', '$comment', 'title', 'description', 'default', 'examples', 'deprecated',
  '$defs', '$ref', 'type', 'const', 'enum', 'required', 'properties', 'additionalProperties',
  'items', 'minItems', 'maxItems', 'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum',
  'minLength', 'maxLength', 'pattern', 'oneOf', 'anyOf', 'allOf', 'not', 'format',
]);

function validate(schema, instance, root, path = []) {
  if (root === undefined) root = schema;
  const errors = [];
  const push = (at, message) => errors.push({ path: at, message: `${pathStr(at)}: ${message}` });
  if (schema === true || schema == null) return errors;
  if (schema === false) { push(path, 'schema is false (nothing allowed)'); return errors; }
  if (typeof schema !== 'object' || Array.isArray(schema)) { push(path, 'schema is not an object'); return errors; }

  if (schema.$ref !== undefined) {
    const target = resolveRef(root, schema.$ref);
    errors.push(...validate(target, instance, root, path));
    // draft 2020-12: siblings of $ref are applied too
  }
  if (schema.type !== undefined) {
    const types = Array.isArray(schema.type) ? schema.type : [schema.type];
    if (!types.some((t) => typeMatches(instance, t))) push(path, `expected type ${types.join('|')}, got ${typeOf(instance)}`);
  }
  if (schema.const !== undefined && JSON.stringify(instance) !== JSON.stringify(schema.const)) {
    push(path, `expected const ${JSON.stringify(schema.const)}, got ${JSON.stringify(instance)}`);
  }
  if (schema.enum !== undefined) {
    const ok = schema.enum.some((e) => JSON.stringify(e) === JSON.stringify(instance));
    if (!ok) push(path, `${JSON.stringify(instance)} is not one of ${JSON.stringify(schema.enum)}`);
  }
  if (schema.minLength !== undefined && typeof instance === 'string' && instance.length < schema.minLength) push(path, `shorter than minLength ${schema.minLength}`);
  if (schema.maxLength !== undefined && typeof instance === 'string' && instance.length > schema.maxLength) push(path, `longer than maxLength ${schema.maxLength}`);
  if (schema.pattern !== undefined && typeof instance === 'string') {
    if (!new RegExp(schema.pattern, 'u').test(instance)) push(path, `${JSON.stringify(instance)} does not match ${schema.pattern}`);
  }
  if (typeof instance === 'number') {
    if (schema.minimum !== undefined && instance < schema.minimum) push(path, `${instance} < minimum ${schema.minimum}`);
    if (schema.maximum !== undefined && instance > schema.maximum) push(path, `${instance} > maximum ${schema.maximum}`);
    if (schema.exclusiveMinimum !== undefined && instance <= schema.exclusiveMinimum) push(path, `${instance} <= exclusiveMinimum ${schema.exclusiveMinimum}`);
    if (schema.exclusiveMaximum !== undefined && instance >= schema.exclusiveMaximum) push(path, `${instance} >= exclusiveMaximum ${schema.exclusiveMaximum}`);
  }
  if (Array.isArray(instance)) {
    if (schema.minItems !== undefined && instance.length < schema.minItems) push(path, `${instance.length} items < minItems ${schema.minItems}`);
    if (schema.maxItems !== undefined && instance.length > schema.maxItems) push(path, `${instance.length} items > maxItems ${schema.maxItems}`);
    if (schema.items !== undefined) instance.forEach((item, i) => errors.push(...validate(schema.items, item, root, [...path, i])));
  }
  if (instance !== null && typeof instance === 'object' && !Array.isArray(instance)) {
    if (Array.isArray(schema.required)) {
      for (const key of schema.required) if (!(key in instance)) push(path, `missing required property "${key}"`);
    }
    const props = schema.properties || {};
    for (const [key, value] of Object.entries(instance)) {
      if (key in props) errors.push(...validate(props[key], value, root, [...path, key]));
      else if (schema.additionalProperties === false) push(path, `unexpected property "${key}"`);
      else if (schema.additionalProperties && typeof schema.additionalProperties === 'object') {
        errors.push(...validate(schema.additionalProperties, value, root, [...path, key]));
      }
    }
  }
  if (Array.isArray(schema.allOf)) for (const s of schema.allOf) errors.push(...validate(s, instance, root, path));
  if (Array.isArray(schema.anyOf)) {
    const results = schema.anyOf.map((s) => validate(s, instance, root, path));
    if (!results.some((r) => r.length === 0)) push(path, `matches no anyOf branch (first: ${results[0][0] ? results[0][0].message : 'n/a'})`);
  }
  if (Array.isArray(schema.oneOf)) {
    const results = schema.oneOf.map((s) => validate(s, instance, root, path));
    const passing = results.filter((r) => r.length === 0).length;
    if (passing !== 1) push(path, `must match exactly one oneOf branch, matched ${passing}`);
  }
  if (schema.not !== undefined) {
    if (validate(schema.not, instance, root, path).length === 0) push(path, 'must not match the "not" schema');
  }
  return errors;
}

/**
 * Structural self-check of a schema document, independent of any instance:
 * valid JSON object, declared draft, no external $ref, every internal $ref
 * resolves, only supported keywords, keyword values of the right type.
 */
function checkSchemaDocument(schema) {
  const problems = [];
  const walk = (node, at) => {
    if (node === true || node === false) return;
    if (node === null || typeof node !== 'object') { problems.push(`${at}: schema node is not an object/boolean`); return; }
    if (Array.isArray(node)) { problems.push(`${at}: unexpected array where a schema was expected`); return; }
    for (const key of Object.keys(node)) {
      if (!KEYWORDS.has(key)) problems.push(`${at}: unsupported keyword "${key}"`);
    }
    if (typeof node.type === 'string' && !['object', 'array', 'string', 'number', 'integer', 'boolean', 'null'].includes(node.type)) problems.push(`${at}.type: unknown type "${node.type}"`);
    if (Array.isArray(node.type) && node.type.some((t) => !['object', 'array', 'string', 'number', 'integer', 'boolean', 'null'].includes(t))) problems.push(`${at}.type: unknown type in array`);
    if (node.required !== undefined && (!Array.isArray(node.required) || node.required.some((r) => typeof r !== 'string'))) problems.push(`${at}.required: expected array of strings`);
    if (node.enum !== undefined && !Array.isArray(node.enum)) problems.push(`${at}.enum: expected array`);
    if (node.pattern !== undefined) { try { new RegExp(node.pattern); } catch (e) { problems.push(`${at}.pattern: ${e.message}`); } }
    if (node.$ref !== undefined) {
      try { resolveRef(schema, node.$ref); } catch (e) { problems.push(`${at}.$ref: ${e.message}`); }
    }
    for (const [k, v] of Object.entries(node.properties || {})) walk(v, `${at}.properties.${k}`);
    for (const [k, v] of Object.entries(node.$defs || {})) walk(v, `${at}.$defs.${k}`);
    if (node.additionalProperties && typeof node.additionalProperties === 'object') walk(node.additionalProperties, `${at}.additionalProperties`);
    if (node.items && typeof node.items === 'object') walk(node.items, `${at}.items`);
    for (const k of ['oneOf', 'anyOf', 'allOf']) if (Array.isArray(node[k])) node[k].forEach((s, i) => walk(s, `${at}.${k}[${i}]`));
    if (node.not && typeof node.not === 'object') walk(node.not, `${at}.not`);
  };
  if (schema && schema.$schema !== 'https://json-schema.org/draft/2020-12/schema') problems.push(`$schema: expected draft 2020-12, got ${JSON.stringify(schema && schema.$schema)}`);
  if (!schema || typeof schema.$id !== 'string') problems.push('$id: missing');
  if (!schema || schema.type !== 'object') problems.push('root type should be "object"');
  walk(schema, '$');
  return problems;
}

module.exports = { validate, checkSchemaDocument, resolveRef, typeOf };
