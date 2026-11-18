'use strict';
/**
 * usda-lint.js — strict, dependency-free USDA (.usda / ASCII USD) linter.
 *
 * Why this exists: a .usdz that parses everywhere else can still be refused by
 * Quick Look. The only trustworthy reference for "what Apple's reader accepts"
 * is Apple's own exporter output, so this validator is tuned to that corpus
 * (105 .usda layers from 4 Apple .usdz captures) and it must never reject a
 * file Apple itself wrote. Anything Apple never writes is reported as a
 * warning (code STYLE_*), never as an error — that is how the reference
 * corpus stays the source of truth instead of our assumptions.
 *
 * Usage (API):
 *   const { lint, parseLayer } = require('./usda-lint');
 *   const r = lint(text, { name: 'room.usda', baseDir: '/path/to/extract' });
 *   r.ok        // true when there are no errors
 *   r.errors    // [{ line, col, code, message }]
 *   r.warnings  // [{ line, col, code, message }]
 *   r.stats     // { prims, meshes, materials, attributes, maxDepth }
 *
 * Usage (CLI):  node usda-lint.js file1.usda [file2.usda ...]   (exit 1 on error)
 *
 * Grammar implemented (the subset Apple emits, plus the legal neighbours a
 * correct writer may need):
 *   layer      := "#usda 1.0" metadata? statement*
 *   statement  := prim | metadata-statement
 *   prim       := ("def"|"over"|"class"|"block") typename? string metadata? "{" body "}"
 *   body       := (prim | property | variantSet | metadata-statement)*
 *   property   := modifiers type name ( "=" value metadata? | metadata "=" value | (".connect"|".timeSamples") "=" value | )
 *                | "rel" name ("=" path | "=" "[" path,* "]")? metadata?
 *   metadata   := "(" metaitem* ")"          metaitem := modifiers type? name "=" value
 *   value      := number | string | bool | "None" | asset | path
 *                | "[" value,* "]" | "(" value,* ")" | "{" dictitem* "}"
 *   dictitem   := type? name "=" value
 *
 * Everything is line-accurate: every token carries its line/column, so each
 * diagnostic points at the offending line of the layer.
 */

/* ------------------------------------------------------------- tokenizer -- */

const ID_START = /[A-Za-z_]/;
const ID_REST = /[A-Za-z0-9_:.]/; // ':' for namespaces, '.' for .connect/.timeSamples

/**
 * Tokenize one USDA layer. Returns { tokens, errors }.
 * Token: { t: 'id'|'str'|'num'|'asset'|'path'|'punct'|'eof', v, line, col }
 */
function tokenize(text) {
  const tokens = [];
  const errors = [];
  let i = 0;
  let line = 1;
  let col = 1;
  const n = text.length;

  const push = (t, v, l, c) => tokens.push({ t, v, line: l, col: c });
  const advance = (count) => {
    for (let k = 0; k < count; k += 1) {
      if (text[i] === '\n') { line += 1; col = 1; } else { col += 1; }
      i += 1;
    }
  };

  // Leading BOM is tolerated by USD; strip it but keep offsets sane.
  if (text.charCodeAt(0) === 0xfeff) advance(1);

  while (i < n) {
    const ch = text[i];
    // whitespace
    if (ch === ' ' || ch === '\t' || ch === '\r' || ch === '\n') { advance(1); continue; }
    // comments (# anywhere except the magic first line, handled by caller)
    if (ch === '#') {
      const startLine = line;
      while (i < n && text[i] !== '\n') advance(1);
      // "#usda" outside the first line is not valid
      if (startLine !== 1) {
        // a comment; nothing to record
      }
      continue;
    }
    if (ch === '"') {
      const l = line; const c = col;
      advance(1);
      let out = '';
      let closed = false;
      while (i < n) {
        const d = text[i];
        if (d === '\\') {
          const e = text[i + 1];
          const map = { n: '\n', t: '\t', r: '\r', '"': '"', '\\': '\\', "'": "'" };
          if (e in map) { out += map[e]; advance(2); continue; }
          if (e === 'u' || e === 'x') {
            const len = e === 'u' ? 4 : 2;
            const hex = text.slice(i + 2, i + 2 + len);
            if (/^[0-9a-fA-F]+$/.test(hex) && hex.length === len) {
              out += String.fromCharCode(parseInt(hex, 16)); advance(2 + len); continue;
            }
          }
          errors.push({ line, col, code: 'LEX_BAD_ESCAPE', message: `unknown string escape "\\${e}"` });
          advance(2);
          continue;
        }
        if (d === '"') { advance(1); closed = true; break; }
        if (d === '\n') break; // unterminated at end of line
        out += d; advance(1);
      }
      if (!closed) errors.push({ line: l, col: c, code: 'LEX_UNTERMINATED_STRING', message: 'string literal is not closed before end of line' });
      push('str', out, l, c);
      continue;
    }
    if (ch === '@') {
      const l = line; const c = col;
      advance(1);
      let triple = false;
      if (text[i] === '@') { advance(1); triple = false; } // "@@" empty-ish; still read to closing
      let out = '';
      let closed = false;
      while (i < n) {
        if (text[i] === '@') { advance(1); closed = true; break; }
        if (text[i] === '\n') break;
        out += text[i]; advance(1);
      }
      if (!closed) errors.push({ line: l, col: c, code: 'LEX_UNTERMINATED_ASSET', message: 'asset path @...@ is not closed' });
      push('asset', out, l, c);
      continue;
    }
    if (ch === '<') {
      const l = line; const c = col;
      advance(1);
      let out = '';
      let closed = false;
      while (i < n) {
        if (text[i] === '>') { advance(1); closed = true; break; }
        if (text[i] === '\n') break;
        out += text[i]; advance(1);
      }
      if (!closed) errors.push({ line: l, col: c, code: 'LEX_UNTERMINATED_PATH', message: 'path </...> is not closed' });
      push('path', out, l, c);
      continue;
    }
    // numbers: -1, +1, .5, 1., 1e-7, 0.0001
    if ((ch >= '0' && ch <= '9') || ch === '-' || ch === '+' || (ch === '.' && /[0-9]/.test(text[i + 1] || ''))) {
      const l = line; const c = col;
      const m = /^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?/.exec(text.slice(i, i + 64));
      if (m && m[0].length) {
        // a lone '+'/'-' followed by an identifier is a syntax error, not a number
        advance(m[0].length);
        push('num', m[0], l, c);
        continue;
      }
    }
    if (ID_START.test(ch)) {
      const l = line; const c = col;
      let j = i;
      while (j < n && ID_REST.test(text[j])) j += 1;
      const word = text.slice(i, j);
      advance(word.length);
      push('id', word, l, c);
      continue;
    }
    if ('()[]{}=;,'.includes(ch)) {
      push('punct', ch, line, col);
      advance(1);
      continue;
    }
    errors.push({ line, col, code: 'LEX_BAD_CHAR', message: `unexpected character ${JSON.stringify(ch)}` });
    advance(1);
  }
  tokens.push({ t: 'eof', v: '<eof>', line, col });
  return { tokens, errors };
}

/* ---------------------------------------------------------------- parser -- */

const PRIM_KEYWORDS = new Set(['def', 'over', 'class', 'block']);
const MODIFIERS = new Set(['custom', 'uniform', 'varying', 'config', 'incremental']);
const META_KEYS_BODY = new Set(['customData', 'doc', 'kind', 'apiSchemas', 'assetInfo', 'prepend', 'append', 'add', 'references', 'payload', 'inherits', 'variantSets', 'sublayers', 'subLayers', 'defaultPrim', 'metersPerUnit', 'upAxis', 'displayName', 'hidden', 'active', 'instanceable', 'specializes', 'permission']);
const NOT_PROPERTY = new Set(['true', 'false', 'none']);

class Parser {
  constructor(tokens, errors, name) {
    this.tk = tokens;
    this.i = 0;
    this.errors = errors;
    this.name = name;
    this.layer = { header: null, metadata: [], prims: [], stats: { prims: 0, meshes: 0, materials: 0, attributes: 0, maxDepth: 0 } };
  }

  peek(k = 0) { return this.tk[Math.min(this.i + k, this.tk.length - 1)]; }
  next() { const t = this.tk[this.i]; if (t.t !== 'eof') this.i += 1; return t; }
  isPunct(v, k = 0) { const t = this.peek(k); return t.t === 'punct' && t.v === v; }
  isId(v, k = 0) { const t = this.peek(k); return t.t === 'id' && (v === undefined || t.v === v); }
  err(tok, code, message) { this.errors.push({ line: tok.line, col: tok.col, code, message }); }
  expectPunct(v) {
    const t = this.next();
    if (!(t.t === 'punct' && t.v === v)) {
      this.err(t, 'PARSE_EXPECTED', `expected "${v}" but found ${JSON.stringify(t.v)}`);
      return null;
    }
    return t;
  }

  /* ---- layer ---- */
  parseLayer() {
    const first = this.peek();
    // The magic line is "#usda 1.0"; the tokenizer dropped it as a comment, so
    // re-check it from the raw text by scanning token positions is impossible.
    // Instead the caller passes `headerOk` — here we simply require that the
    // first significant token is "(" opening the metadata block.
    if (first.t === 'eof') {
      this.err(first, 'LAYER_EMPTY', 'layer is empty');
      return this.layer;
    }
    if (this.isPunct('(')) {
      this.layer.metadata = this.parseMetadata('layer');
    } else {
      this.err(first, 'LAYER_NO_HEADER', 'layer must start with "#usda 1.0" and a metadata block');
    }
    while (this.peek().t !== 'eof') {
      const t = this.peek();
      if (this.isPunct(';')) { this.next(); continue; }
      if (PRIM_KEYWORDS.has(t.v) && t.t === 'id') { this.layer.prims.push(this.parsePrim(0)); continue; }
      if (t.t === 'id' && META_KEYS_BODY.has(t.v)) { this.parseBodyMetadata(this.layer.metadata, 'layer'); continue; }
      this.err(t, 'PARSE_UNEXPECTED_TOPLEVEL', `unexpected top-level token ${JSON.stringify(t.v)}; only "def/over/class" prims and layer metadata are allowed here`);
      this.next();
    }
    return this.layer;
  }

  /* ---- metadata ---- */
  parseMetadata(scope) {
    const open = this.expectPunct('(');
    const items = [];
    while (!this.isPunct(')') && this.peek().t !== 'eof') {
      if (this.isPunct(',')) { this.next(); continue; }
      const item = this.parseMetaItem(scope);
      if (item) items.push(item);
    }
    const close = this.peek();
    if (!this.isPunct(')')) {
      this.err(open || close, 'PARSE_UNCLOSED_METADATA', `metadata block opened with "(" is never closed (started on line ${open ? open.line : '?'})`);
    } else this.next();
    return items;
  }

  parseMetaItem(scope) {
    const first = this.peek();
    const mods = [];
    while (this.peek().t === 'id' && MODIFIERS.has(this.peek().v) && this.peek(1).t === 'id') { mods.push(this.next().v); }
    // "type name = value" or "name = value"
    let type = null;
    let key = null;
    if (this.peek().t === 'id' && (this.isPunct('=', 1) || (this.isPunct('[', 1) && this.isPunct(']', 2) && this.isPunct('=', 3)))) {
      key = this.next().v;
    } else if (this.peek().t === 'id') {
      type = this.next().v;
      if (this.isPunct('[') && this.isPunct(']', 1)) { this.next(); this.next(); type += '[]'; }
      if (this.peek().t === 'id') key = this.next().v;
      else { this.err(this.peek(), 'PARSE_META_NO_KEY', `metadata type "${type}" is not followed by a name`); return null; }
    } else {
      this.err(first, 'PARSE_META_BAD', `expected a metadata name but found ${JSON.stringify(first.v)}`);
      this.next();
      return null;
    }
    if (!this.isPunct('=')) {
      this.err(this.peek(), 'PARSE_META_NO_EQUALS', `metadata "${key}" has no "= value" (line ${this.peek().line})`);
      this.skipStatement();
      return { key, type, mods, value: null, line: first.line };
    }
    this.next();
    const value = this.parseValue();
    return { key, type, mods, value, line: first.line };
  }

  parseBodyMetadata(sink, scope) {
    const item = this.parseMetaItem(scope);
    if (item) {
      item.inBody = true;
      sink.push(item);
    }
    return item;
  }

  /* ---- prims ---- */
  parsePrim(depth) {
    const kw = this.next();
    const prim = { keyword: kw.v, typeName: null, name: null, metadata: [], props: [], children: [], line: kw.line, depth };
    if (this.peek().t === 'id') prim.typeName = this.next().v;
    if (this.peek().t === 'str') prim.name = this.next().v;
    else {
      this.err(this.peek(), 'PARSE_PRIM_NO_NAME', `"${kw.v}" prim has no name string`);
    }
    if (this.isPunct('(')) prim.metadata = this.parseMetadata('prim');
    this.layer.stats.prims += 1;
    this.layer.stats.maxDepth = Math.max(this.layer.stats.maxDepth, depth);
    if (!this.isPunct('{')) {
      this.err(this.peek(), 'PARSE_PRIM_NO_BODY', `prim "${prim.name}" has no body; expected "{" but found ${JSON.stringify(this.peek().v)}`);
      return prim;
    }
    this.next(); // {
    this.parseBody(prim, depth);
    return prim;
  }

  parseBody(prim, depth) {
    while (this.peek().t !== 'eof' && !this.isPunct('}')) {
      const t = this.peek();
      if (this.isPunct(';') || this.isPunct(',')) { this.next(); continue; }
      if (t.t === 'id' && PRIM_KEYWORDS.has(t.v)) { prim.children.push(this.parsePrim(depth + 1)); continue; }
      if (t.t === 'id' && t.v === 'variantSet') { this.parseVariantSet(prim, depth); continue; }
      if (t.t === 'id' && t.v === 'rel') {
        const p = this.parseRel();
        if (p) prim.props.push(p);
        continue;
      }
      if (t.t === 'id' && META_KEYS_BODY.has(t.v) && (this.isPunct('=', 1) || this.isPunct('[', 1))) {
        // metadata authored in a prim BODY rather than in the prim's metadata
        // block. USD accepts this, but Apple never writes it — see STYLE_META_IN_BODY.
        this.parseBodyMetadata(prim.metadata, 'prim');
        continue;
      }
      const p = this.parseProperty();
      if (p) prim.props.push(p);
      else this.next();
    }
    if (this.isPunct('}')) this.next();
    else this.err(this.peek(), 'PARSE_UNCLOSED_PRIM', `prim "${prim.name}" is never closed with "}"`);
  }

  parseVariantSet(prim, depth) {
    const t = this.next(); // variantSet
    const nameTok = this.peek(); let name = null;
    if (nameTok.t === 'str') name = this.next().v;
    if (!this.isPunct('{')) { this.err(this.peek(), 'PARSE_VARIANTSET', 'variantSet is not followed by "{"'); this.skipStatement(); return; }
    this.next();
    while (!this.isPunct('}') && this.peek().t !== 'eof') {
      const vtok = this.peek();
      if (vtok.t === 'str') {
        this.next();
        if (!this.isPunct('{')) { this.err(this.peek(), 'PARSE_VARIANT', `variant "${vtok.v}" is not followed by "{"`); this.skipStatement(); continue; }
        this.next();
        const fake = { keyword: 'variant', typeName: null, name: `${name}:${vtok.v}`, metadata: [], props: [], children: [], line: vtok.line, depth: depth + 1 };
        this.parseBody(fake, depth + 1);
        prim.children.push(fake);
        continue;
      }
      this.err(vtok, 'PARSE_VARIANTSET_BODY', `unexpected token ${JSON.stringify(vtok.v)} inside variantSet`);
      this.next();
    }
    if (this.isPunct('}')) this.next();
  }

  parseRel() {
    const rel = this.next(); // "rel"
    const nameTok = this.peek();
    if (nameTok.t !== 'id') { this.err(nameTok, 'PARSE_REL_NAME', 'rel is not followed by a property name'); this.skipStatement(); return null; }
    const name = this.next().v;
    let targets = [];
    if (this.isPunct('=')) {
      this.next();
      if (this.isPunct('[')) {
        const arr = this.parseArray();
        targets = arr.items.filter((x) => x.kind === 'path').map((x) => x.value);
        if (arr.items.some((x) => x.kind !== 'path')) this.err(nameTok, 'PARSE_REL_VALUE', `rel "${name}" array contains a non-path value`);
      } else if (this.peek().t === 'path') {
        const p = this.next();
        targets = [p.v];
      } else {
        this.err(this.peek(), 'PARSE_REL_VALUE', `rel "${name}" has no path value`);
        this.skipStatement();
      }
    }
    const metadata = this.isPunct('(') ? this.parseMetadata('prop') : [];
    return { kind: 'rel', type: null, name, value: { kind: 'paths', value: targets }, metadata, line: rel.line };
  }

  parseProperty() {
    const start = this.peek();
    const mods = [];
    while (this.peek().t === 'id' && MODIFIERS.has(this.peek().v) && this.peek(1).t === 'id') {
      mods.push(this.next().v);
    }
    if (this.peek().t !== 'id') {
      return null;
    }
    let type = this.next().v;
    if (this.isPunct('[') && this.isPunct(']', 1)) { this.next(); this.next(); type += '[]'; }
    const nameTok = this.peek();
    if (nameTok.t !== 'id') {
      this.err(nameTok, 'PARSE_PROP_NO_NAME', `declaration of type "${type}" has no property name`);
      this.skipStatement();
      return null;
    }
    const name = this.next().v;
    let value = null;
    let metadata = [];
    let connection = null;
    if (this.isPunct('=')) {
      this.next();
      value = this.parseValue();
      if (this.isPunct('(')) metadata = this.parseMetadata('prop');
    } else if (this.isPunct('(')) {
      // metadata BEFORE the value: legal USD, never emitted by Apple.
      metadata = this.parseMetadata('prop');
      if (this.isPunct('=')) { this.next(); value = this.parseValue(); }
    }
    this.layer.stats.attributes += 1;
    return { kind: 'property', mods, type, name, value, metadata, connection, line: start.line };
  }

  /* ---- values ---- */
  parseValue() {
    const t = this.peek();
    if (t.t === 'num') { this.next(); return { kind: 'number', value: Number(t.v), raw: t.v, line: t.line }; }
    if (t.t === 'str') { this.next(); return { kind: 'string', value: t.v, line: t.line }; }
    if (t.t === 'asset') { this.next(); return { kind: 'asset', value: t.v, line: t.line }; }
    if (t.t === 'path') { this.next(); return { kind: 'path', value: t.v, line: t.line }; }
    if (this.isPunct('[')) return this.parseArray();
    if (this.isPunct('(')) return this.parseTuple();
    if (this.isPunct('{')) return this.parseDict();
    if (t.t === 'id') {
      this.next();
      const low = t.v.toLowerCase();
      if (low === 'true' || low === 'false') return { kind: 'bool', value: low === 'true', line: t.line };
      if (low === 'none') return { kind: 'none', value: null, line: t.line };
      return { kind: 'ident', value: t.v, line: t.line };
    }
    this.err(t, 'PARSE_BAD_VALUE', `expected a value but found ${JSON.stringify(t.v)}`);
    this.next();
    return { kind: 'invalid', value: null, line: t.line };
  }

  parseArray() {
    const open = this.next(); // [
    const items = [];
    while (!this.isPunct(']') && this.peek().t !== 'eof') {
      if (this.isPunct(',')) { this.next(); continue; }
      items.push(this.parseValue());
    }
    if (this.isPunct(']')) this.next();
    else this.err(open, 'PARSE_UNCLOSED_ARRAY', 'array "[" is never closed with "]"');
    return { kind: 'array', items, line: open.line };
  }

  parseTuple() {
    const open = this.next(); // (
    const items = [];
    while (!this.isPunct(')') && this.peek().t !== 'eof') {
      if (this.isPunct(',')) { this.next(); continue; }
      items.push(this.parseValue());
    }
    if (this.isPunct(')')) this.next();
    else this.err(open, 'PARSE_UNCLOSED_TUPLE', 'tuple "(" is never closed with ")"');
    return { kind: 'tuple', items, line: open.line };
  }

  parseDict() {
    const open = this.next(); // {
    const items = [];
    while (!this.isPunct('}') && this.peek().t !== 'eof') {
      if (this.isPunct(',') || this.isPunct(';')) { this.next(); continue; }
      const first = this.peek();
      let type = null;
      let key = null;
      if (first.t !== 'id') { this.err(first, 'PARSE_DICT_KEY', `expected a dictionary key but found ${JSON.stringify(first.v)}`); this.next(); continue; }
      if (this.isPunct('=', 1)) { key = this.next().v; }
      else {
        type = this.next().v;
        if (this.isPunct('[') && this.isPunct(']', 1)) { this.next(); this.next(); type += '[]'; }
        if (this.peek().t !== 'id') { this.err(this.peek(), 'PARSE_DICT_KEY', `dictionary type "${type}" is not followed by a key`); this.skipStatement(); continue; }
        key = this.next().v;
      }
      if (!this.isPunct('=')) { this.err(this.peek(), 'PARSE_DICT_EQUALS', `dictionary key "${key}" has no "= value"`); this.skipStatement(); continue; }
      this.next();
      const value = this.parseValue();
      items.push({ type, key, value, line: first.line });
    }
    if (this.isPunct('}')) this.next();
    else this.err(open, 'PARSE_UNCLOSED_DICT', 'dictionary "{" is never closed with "}"');
    return { kind: 'dict', items, line: open.line };
  }

  skipStatement() {
    let guard = 0;
    while (this.peek().t !== 'eof' && guard < 5000) {
      if (this.isPunct(';')) { this.next(); return; }
      const t = this.peek();
      if ((this.peek(-0) && this.isPunct('}')) || (t.t === 'id' && PRIM_KEYWORDS.has(t.v))) return;
      this.next(); guard += 1;
    }
  }
}

/* ------------------------------------------------------------- semantics -- */

const META_TEXT = { cmd: 1 };

function flattenNumbers(value, out) {
  if (!value) return out;
  if (value.kind === 'number') out.push(value);
  else if (value.kind === 'array' || value.kind === 'tuple') for (const it of value.items) flattenNumbers(it, out);
  return out;
}

function tupleArity(value) {
  return value && value.kind === 'tuple' ? value.items.length : (value && value.kind === 'array' ? null : null);
}

/** Component count implied by a USD type name, e.g. point3f -> 3, matrix4d -> 16. */
function componentsOf(type) {
  if (!type) return null;
  const m = /^([a-z0-9]+?)([234])?([fdh])?(\[\])?$/.exec(type);
  if (!m) return null;
  if (/^matrix/.test(type)) return 16;
  return m[2] ? Number(m[2]) : 1;
}

function primPathOf(scopePath, name) { return `${scopePath === '/' ? '' : scopePath}/${name}`; }

function walkPrims(prims, visit, parentPath = '/') {
  for (const p of prims) {
    const path = primPathOf(parentPath, p.name || '?');
    visit(p, path);
    walkPrims(p.children, visit, path);
  }
}

function lint(text, options) {
  const opts = options || {};
  const name = opts.name || '<usda>';
  const errors = [];
  const warnings = [];

  // --- magic line: checked on raw text, before tokenizing ---
  const firstLine = text.split('\n', 1)[0].replace(/\r$/, '');
  if (firstLine !== '#usda 1.0') {
    errors.push({ line: 1, col: 1, code: 'LAYER_MAGIC', message: `first line must be exactly "#usda 1.0" (found ${JSON.stringify(firstLine)})` });
  }

  const { tokens, errors: lexErrors } = tokenize(firstLine === '#usda 1.0' ? text.slice(text.indexOf('\n') + 1) : text);
  // Re-align line numbers when the magic line was stripped from the stream.
  const lineOffset = firstLine === '#usda 1.0' ? 1 : 0;
  if (lineOffset) for (const e of lexErrors) e.line += lineOffset;
  errors.push(...lexErrors);
  if (lineOffset) for (const t of tokens) t.line += lineOffset;

  const parser = new Parser(tokens, errors, name);
  const layer = parser.parseLayer();
  const stats = layer.stats;

  /* ---- layer metadata ---- */
  const meta = (key) => layer.metadata.filter((m) => m.key === key);
  const seenMeta = new Set();
  for (const m of layer.metadata) {
    if (seenMeta.has(m.key)) warnings.push({ line: m.line, col: 1, code: 'META_DUPLICATE', message: `layer metadata "${m.key}" appears more than once` });
    seenMeta.add(m.key);
    if (m.inBody) warnings.push({ line: m.line, col: 1, code: 'STYLE_META_IN_BODY', message: `"${m.key}" is written as a statement instead of inside the layer metadata block — Apple's exporter never does this` });
  }

  const header = { defaultPrim: null, metersPerUnit: null, upAxis: null };
  if (!meta('defaultPrim').length) {
    errors.push({ line: 1, col: 1, code: 'META_NO_DEFAULTPRIM', message: 'layer metadata has no "defaultPrim"; AR Quick Look needs a default prim to place the asset' });
  } else {
    const v = meta('defaultPrim')[0].value;
    if (!v || v.kind !== 'string') errors.push({ line: meta('defaultPrim')[0].line, col: 1, code: 'META_DEFAULTPRIM_TYPE', message: `defaultPrim must be a string (found ${v && v.kind})` });
    else header.defaultPrim = v.value;
  }
  if (!meta('metersPerUnit').length) {
    warnings.push({ line: 1, col: 1, code: 'META_NO_METERSPERUNIT', message: 'layer metadata has no "metersPerUnit"; USD defaults to 0.01 (centimetres), which silently scales the model 100x' });
  } else {
    const v = meta('metersPerUnit')[0].value;
    if (!v || v.kind !== 'number') errors.push({ line: meta('metersPerUnit')[0].line, col: 1, code: 'META_METERSPERUNIT_TYPE', message: 'metersPerUnit must be a number' });
    else header.metersPerUnit = v.value;
  }
  if (!meta('upAxis').length) {
    warnings.push({ line: 1, col: 1, code: 'META_NO_UPAXIS', message: 'layer metadata has no "upAxis"; USD defaults to "Y" but a reader using the stage default on a Z-up file lays the model on its side' });
  } else {
    const v = meta('upAxis')[0].value;
    if (!v || v.kind !== 'string') errors.push({ line: meta('upAxis')[0].line, col: 1, code: 'META_UPAXIS_TYPE', message: 'upAxis must be a string' });
    else if (!['Y', 'Z', 'X'].includes(v.value)) errors.push({ line: meta('upAxis')[0].line, col: 1, code: 'META_UPAXIS_VALUE', message: `upAxis "${v.value}" is not one of Y/Z/X` });
    else header.upAxis = v.value;
  }

  /* ---- prim tree ---- */
  const rootNames = new Set();
  for (const p of layer.prims) {
    if (rootNames.has(p.name)) errors.push({ line: p.line, col: 1, code: 'PRIM_DUPLICATE_ROOT', message: `duplicate root prim name "${p.name}"` });
    rootNames.add(p.name);
  }
  if (header.defaultPrim && !rootNames.has(header.defaultPrim)) {
    errors.push({ line: 1, col: 1, code: 'META_DEFAULTPRIM_MISSING', message: `defaultPrim "${header.defaultPrim}" does not name any root prim (roots: ${[...rootNames].map((r) => `"${r}"`).join(', ') || 'none'})` });
  }

  const allPaths = new Set();
  const primsByPath = new Map();
  walkPrims(layer.prims, (p, path) => { allPaths.add(path); primsByPath.set(path, p); });

  // duplicate sibling names + identifier validity + property/metadata anomalies
  let hasKind = 0; let hasMaterialBinding = 0; let meshCount = 0; let materialCount = 0;
  const KIND_OK = new Set(['assembly', 'group', 'component', 'subcomponent']);
  const seenPaths = new Set();

  walkPrims(layer.prims, (p, path) => {
    const siblingKey = path;
    if (seenPaths.has(siblingKey)) errors.push({ line: p.line, col: 1, code: 'PRIM_DUPLICATE', message: `duplicate prim path "${siblingKey}"` });
    seenPaths.add(siblingKey);

    if (p.name && !/^[A-Za-z_][A-Za-z0-9_]*$/.test(p.name)) {
      errors.push({ line: p.line, col: 1, code: 'PRIM_BAD_NAME', message: `prim name ${JSON.stringify(p.name)} is not a valid USD identifier ([A-Za-z_][A-Za-z0-9_]*)` });
    }
    if (!p.typeName) warnings.push({ line: p.line, col: 1, code: 'PRIM_NO_TYPE', message: `prim "${p.name}" has no type name (abstract/typeless prim)` });

    // metadata
    const childNames = new Set();
    for (const c of p.children) {
      if (childNames.has(c.name)) errors.push({ line: c.line, col: 1, code: 'PRIM_DUPLICATE_SIBLING', message: `duplicate prim "${c.name}" in scope "${path}" (first defined on line ${p.children.find((x) => x.name === c.name).line})` });
      childNames.add(c.name);
    }
    const propNames = new Set();
    for (const pr of p.props) {
      if (propNames.has(pr.name)) errors.push({ line: pr.line, col: 1, code: 'PROP_DUPLICATE', message: `property "${pr.name}" is declared twice on prim "${p.name}"` });
      propNames.add(pr.name);
    }
    for (const m of p.metadata) {
      if (m.inBody) warnings.push({ line: m.line, col: 1, code: 'STYLE_META_IN_BODY', message: `prim metadata "${m.key}" is written inside the prim body instead of the prim's metadata block; USD accepts it, Apple never writes it` });
      if (m.key === 'kind') {
        hasKind += 1;
        const v = m.value;
        if (!v || v.kind !== 'string') errors.push({ line: m.line, col: 1, code: 'META_KIND_TYPE', message: 'kind must be a token (bare identifier or string), e.g. kind = "component"' });
        else if (!KIND_OK.has(v.value)) errors.push({ line: m.line, col: 1, code: 'META_KIND_VALUE', message: `kind "${v.value}" is not a USD model kind (assembly/group/component/subcomponent)` });
      }
    }

    const isMesh = p.typeName === 'Mesh';
    const isGeom = ['Mesh', 'Cube'].includes(p.typeName);
    if (isMesh) { meshCount += 1; stats.meshes += 1; }
    if (p.typeName === 'Material') { materialCount += 1; stats.materials += 1; }

    const propByName = (n) => p.props.find((x) => x.name === n);

    // material binding
    const binding = p.props.find((x) => x.kind === 'rel' && (x.name === 'material:binding' || x.name.startsWith('material:binding:')));
    if (isGeom) {
      if (binding) hasMaterialBinding += 1;
      else warnings.push({ line: p.line, col: 1, code: 'STYLE_NO_MATERIAL_BINDING', message: `geometry prim "${p.name}" has no "rel material:binding"; Apple always binds a Material, a reader without one falls back to an untextured default` });
    }
    if (binding) {
      for (const target of binding.value.value) {
        if (!allPaths.has(target)) errors.push({ line: binding.line, col: 1, code: 'REL_UNRESOLVED', message: `material:binding of "${p.name}" points at ${target} which does not exist in this layer` });
      }
    }

    // connections
    for (const pr of p.props) {
      if (pr.value && pr.value.kind === 'path' && /\.connect$|\.timeSamples$/.test(pr.name)) {
        // A target may address a prim path plus a property: </A/B/mat.outputs:surface>
        const primPart = pr.value.value.replace(/\.[^/.]*$/, '');
        if (!allPaths.has(primPart)) errors.push({ line: pr.line, col: 1, code: 'CONNECT_UNRESOLVED', message: `${pr.name} points at ${pr.value.value} (prim ${primPart}) which does not exist in this layer` });
      }
    }

    // attribute type / arity sanity + numeric finiteness
    for (const pr of p.props) {
      if (pr.kind === 'rel' || !pr.value) continue;
      if (pr.value.kind === 'invalid') continue;
      const comps = componentsOf(pr.type);
      const nums = flattenNumbers(pr.value, []);
      for (const nmb of nums) {
        if (!Number.isFinite(nmb.value)) errors.push({ line: nmb.line || pr.line, col: 1, code: 'VALUE_NOT_FINITE', message: `property "${pr.name}" contains a non-finite number (${nmb.raw})` });
      }
      if (comps && comps > 1) {
        const isMatrix = /^matrix/.test(pr.type || '');
        const check = (v, want) => {
          if (v.kind === 'tuple') {
            if (v.items.length !== want) errors.push({ line: v.line, col: 1, code: 'VALUE_ARITY', message: `"${pr.name}" (${pr.type}) needs ${want} component(s) here but this tuple has ${v.items.length}` });
            for (const it of v.items) check(it, 1);
          } else if (v.kind === 'array') for (const it of v.items) check(it, want);
        };
        if (isMatrix) {
          // matrix4d is authored either as 4 rows of 4 (Apple's form) or flat 16
          const v = pr.value;
          if (v.kind === 'tuple') {
            if (v.items.length === 4 && v.items.every((r) => r.kind === 'tuple')) {
              for (const row of v.items) {
                if (row.items.length !== 4) errors.push({ line: row.line, col: 1, code: 'VALUE_ARITY', message: `"${pr.name}" (${pr.type}) row has ${row.items.length} components, expected 4` });
              }
            } else if (v.items.length !== 16) {
              errors.push({ line: v.line, col: 1, code: 'VALUE_ARITY', message: `"${pr.name}" (${pr.type}) needs 4 rows of 4 (or 16 flat) but this tuple has ${v.items.length}` });
            }
          } else if (v.kind === 'array') {
            for (const it of v.items) if (it.kind === 'tuple' && it.items.length !== 16) errors.push({ line: it.line, col: 1, code: 'VALUE_ARITY', message: `"${pr.name}" (${pr.type}) element has ${it.items.length} components, expected 16` });
          }
        } else {
          check(pr.value, comps);
        }
      }
      // scalar attributes must not get an array value and vice versa
      const isArrayType = /\[]$/.test(pr.type || '');
      if (isArrayType && pr.value.kind !== 'array' && pr.value.kind !== 'none') {
        errors.push({ line: pr.line, col: 1, code: 'VALUE_SHAPE', message: `"${pr.name}" is declared ${pr.type} (array) but its value is a ${pr.value.kind}` });
      }
      if (!isArrayType && pr.value.kind === 'array') {
        errors.push({ line: pr.line, col: 1, code: 'VALUE_SHAPE', message: `"${pr.name}" is declared ${pr.type} (scalar) but its value is an array` });
      }
      // interpolation metadata is only legal on array attributes
      for (const mt of pr.metadata) {
        if (mt.key === 'interpolation' && !isArrayType) {
          errors.push({ line: mt.line, col: 1, code: 'META_INTERPOLATION_SCOPE', message: `interpolation is only meaningful on an array attribute, but "${pr.name}" is ${pr.type}` });
        }
      }
    }

    /* ---- Mesh semantics ---- */
    if (isMesh) {
      const points = propByName('points');
      const counts = propByName('faceVertexCounts');
      const indices = propByName('faceVertexIndices');
      const normals = propByName('normals');
      const extent = propByName('extent');
      const scheme = propByName('subdivisionScheme');

      if (!points) errors.push({ line: p.line, col: 1, code: 'MESH_NO_POINTS', message: `def Mesh "${p.name}" has no "point3f[] points"` });
      if (!counts) errors.push({ line: p.line, col: 1, code: 'MESH_NO_COUNTS', message: `def Mesh "${p.name}" has no "int[] faceVertexCounts"` });
      if (!indices) errors.push({ line: p.line, col: 1, code: 'MESH_NO_INDICES', message: `def Mesh "${p.name}" has no "int[] faceVertexIndices"` });
      if (points && !/^point3f\[\]$/.test(points.type || '')) warnings.push({ line: points.line, col: 1, code: 'STYLE_POINTS_TYPE', message: `points is declared "${points.type}"; Apple always writes "point3f[]"${points.type === 'float3[]' ? ' (float3 is what people reach for, but it is not the USD mesh attribute type)' : ''}` });
      if (counts && !/^int\[\]$/.test(counts.type || '')) errors.push({ line: counts.line, col: 1, code: 'MESH_COUNTS_TYPE', message: `faceVertexCounts must be "int[]" (found "${counts.type}")` });
      if (indices && !/^int\[\]$/.test(indices.type || '')) errors.push({ line: indices.line, col: 1, code: 'MESH_INDICES_TYPE', message: `faceVertexIndices must be "int[]" (found "${indices.type}")` });

      if (scheme && scheme.value && scheme.value.kind !== 'string') {
        errors.push({ line: scheme.line, col: 1, code: 'MESH_SCHEME_TYPE', message: 'subdivisionScheme must be a token/string, e.g. "none" or "catmullClark"' });
      }

      const pts = points && points.value && points.value.kind === 'array' ? points.value.items : [];
      const cnt = counts && counts.value && counts.value.kind === 'array' ? counts.value.items.map((x) => x.value) : [];
      const idx = indices && indices.value && indices.value.kind === 'array' ? indices.value.items.map((x) => x.value) : [];

      if (points && points.value && points.value.kind !== 'array') errors.push({ line: points.line, col: 1, code: 'MESH_POINTS_SHAPE', message: 'points must be an array of 3-tuples' });
      if (pts.length && cnt.length) {
        const sum = cnt.reduce((a, b) => a + (Number.isFinite(b) ? b : 0), 0);
        if (sum !== idx.length) {
          errors.push({ line: indices ? indices.line : counts.line, col: 1, code: 'MESH_INDEX_COUNT', message: `sum(faceVertexCounts) = ${sum} but faceVertexIndices has ${idx.length} entries; every face must be fully indexed` });
        }
        if (idx.length) {
          const max = Math.max(...idx);
          const min = Math.min(...idx);
          if (max >= pts.length) errors.push({ line: indices.line, col: 1, code: 'MESH_INDEX_RANGE', message: `max(faceVertexIndices) = ${max} but points has only ${pts.length} vertices (max allowed ${pts.length - 1}); USD drops the whole mesh` });
          if (min < 0) errors.push({ line: indices.line, col: 1, code: 'MESH_INDEX_NEGATIVE', message: `faceVertexIndices contains a negative index (${min})` });
        }
        for (const c of cnt) {
          if (!(c >= 3)) errors.push({ line: counts.line, col: 1, code: 'MESH_FACE_TOO_SMALL', message: `faceVertexCounts contains ${c}; a face needs at least 3 vertices` });
          else if (c > 4) warnings.push({ line: counts.line, col: 1, code: 'STYLE_NGON', message: `faceVertexCounts contains an n-gon (${c}); Apple's exporter always triangulates` });
        }
        const allTri = cnt.every((c) => c === 3);
        if (!allTri) warnings.push({ line: counts.line, col: 1, code: 'STYLE_NOT_TRIANGULATED', message: 'mesh is not triangulated; every Apple-authored mesh in the reference corpus uses triangles only (382 of 382 faces are 3s)' });
      }

      if (normals) {
        if (!/^normal3f\[\]$/.test(normals.type || '')) errors.push({ line: normals.line, col: 1, code: 'MESH_NORMALS_TYPE', message: `normals must be "normal3f[]" (found "${normals.type}")` });
        const nrm = normals.value && normals.value.kind === 'array' ? normals.value.items : [];
        const interp = (normals.metadata.find((m) => m.key === 'interpolation') || {}).value;
        const mode = interp && interp.kind === 'string' ? interp.value : 'vertex';
        const expected = mode === 'faceVarying' ? cnt.reduce((a, b) => a + b, 0) : pts.length;
        if (nrm.length !== expected) {
          errors.push({ line: normals.line, col: 1, code: 'MESH_NORMALS_LENGTH', message: `normals has ${nrm.length} entries but interpolation "${mode}" requires ${expected} (points: ${pts.length}, face-vertices: ${cnt.reduce((a, b) => a + b, 0)})` });
        }
        for (const nv of nrm) {
          if (nv.kind !== 'tuple' || nv.items.length !== 3) { errors.push({ line: nv.line || normals.line, col: 1, code: 'MESH_NORMAL_ARITY', message: 'every normal must be a 3-tuple' }); break; }
        }
      }

      if (extent) {
        if (!/^(float3|point3f|double3)\[\]$/.test(extent.type || '')) {
          errors.push({ line: extent.line, col: 1, code: 'MESH_EXTENT_TYPE', message: `extent must be "float3[]" (found "${extent.type}")` });
        }
        const ex = extent.value && extent.value.kind === 'array' ? extent.value.items : [];
        if (ex.length !== 2) errors.push({ line: extent.line, col: 1, code: 'MESH_EXTENT_ARITY', message: `extent must have exactly 2 points (min and max), found ${ex.length}` });
        else if (pts.length) {
          const lo = ex[0].items.map((x) => x.value);
          const hi = ex[1].items.map((x) => x.value);
          const tol = 1e-4;
          for (let axis = 0; axis < 3; axis += 1) {
            if (!(lo[axis] <= hi[axis])) errors.push({ line: extent.line, col: 1, code: 'MESH_EXTENT_ORDER', message: `extent min[${axis}] = ${lo[axis]} is greater than max[${axis}] = ${hi[axis]}` });
          }
          let bad = null;
          for (const pv of pts) {
            for (let axis = 0; axis < 3; axis += 1) {
              const v = pv.items[axis] && pv.items[axis].value;
              if (!(v >= lo[axis] - tol && v <= hi[axis] + tol)) { bad = { v, axis, pv }; break; }
            }
            if (bad) break;
          }
          if (bad) errors.push({ line: extent.line, col: 1, code: 'MESH_EXTENT_COVERAGE', message: `extent does not enclose every vertex: vertex has ${bad.axis === 0 ? 'x' : bad.axis === 1 ? 'y' : 'z'} = ${bad.v} outside [${lo[bad.axis]}, ${hi[bad.axis]}]; a too-small extent makes Quick Look cull the geometry` });
        }
      }
    }
  });

  /* ---- xform opinion sanity ---- */
  walkPrims(layer.prims, (p) => {
    const props = p.props;
    const order = props.find((x) => x.name === 'xformOpOrder');
    if (!order) return;
    if (!/^token\[\]$/.test(order.type || '')) errors.push({ line: order.line, col: 1, code: 'XFORM_ORDER_TYPE', message: `xformOpOrder must be "uniform token[]" (found "${order.type}")` });
    const names = order.value && order.value.kind === 'array' ? order.value.items.map((x) => x.value) : [];
    for (const nm of names) {
      const found = props.some((x) => x.name === `xformOp:${nm.replace(/^xformOp:/, '')}`);
      if (!found) errors.push({ line: order.line, col: 1, code: 'XFORM_OP_MISSING', message: `xformOpOrder lists "${nm}" but the prim has no such attribute` });
    }
    for (const pr of props) {
      if (!/^xformOp:/.test(pr.name)) continue;
      if (!names.includes(pr.name)) warnings.push({ line: pr.line, col: 1, code: 'XFORM_OP_NOT_ORDERED', message: `attribute "${pr.name}" is not listed in xformOpOrder, so it is ignored by readers` });
    }
  });

  /* ---- reference corpus shape warnings ---- */
  if (layer.prims.length && !hasKind) {
    warnings.push({ line: layer.prims[0].line, col: 1, code: 'STYLE_NO_KIND', message: 'no prim in this layer carries "kind"; Apple tags the root "assembly", containers "group" and leaf components "component"' });
  }
  if (meshCount && !materialCount) {
    warnings.push({ line: 1, col: 1, code: 'STYLE_NO_MATERIAL', message: 'layer defines meshes but no "def Material"; every Apple mesh is bound to a UsdPreviewSurface material' });
  }

  return {
    name,
    ok: errors.length === 0,
    errors: errors.sort((a, b) => a.line - b.line || a.col - b.col),
    warnings: warnings.sort((a, b) => a.line - b.line || a.col - b.col),
    header,
    stats,
    layer,
  };
}

module.exports = { lint, tokenize, Parser };

/* ------------------------------------------------------------------ CLI -- */

if (require.main === module) {
  const fs = require('fs');
  const path = require('path');
  const args = process.argv.slice(2);
  if (!args.length) {
    console.error('usage: node usda-lint.js <file.usda> [more.usda ...]');
    process.exit(2);
  }
  let failed = 0;
  for (const file of args) {
    const abs = path.resolve(file);
    let text;
    try { text = fs.readFileSync(abs, 'utf8'); } catch (e) { console.error(`${file}: cannot read (${e.message})`); failed += 1; continue; }
    const r = lint(text, { name: file, baseDir: path.dirname(abs) });
    const tag = r.ok ? 'OK  ' : 'FAIL';
    console.log(`${tag} ${file}  prims=${r.stats.prims} meshes=${r.stats.meshes} attrs=${r.stats.attributes} errors=${r.errors.length} warnings=${r.warnings.length}`);
    for (const e of r.errors) console.log(`     ${file}:${e.line}:${e.col}  ${e.code}  ${e.message}`);
    if (process.env.USDA_LINT_VERBOSE) for (const w of r.warnings) console.log(`  ~  ${file}:${w.line}:${w.col}  ${w.code}  ${w.message}`);
    if (!r.ok) failed += 1;
  }
  process.exit(failed ? 1 : 0);
}
