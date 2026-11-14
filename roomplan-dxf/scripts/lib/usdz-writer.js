'use strict';
/**
 * usdz-writer.js — a minimal, dependency-free USDZ (ZIP) writer.
 *
 * A .usdz file is an ordinary ZIP archive whose entries are stored UNCOMPRESSED
 * (method 0) and whose file data is padded so that every payload starts on a
 * 64-byte boundary. That is the whole format: QuickLook/AR Quick Look read the
 * first entry named `*.usda` as the root layer and resolve further layers and
 * textures through relative paths inside the same archive.
 *
 * What this writer does:
 *   - STORE only (no deflate), so a .usda layer is human-readable inside the
 *     archive and the bytes are exactly what usda-export.js produced;
 *   - 64-byte alignment of every payload, implemented as a ZIP "extra field"
 *     of zero padding in the local file header (a compliant reader — including
 *     Python's zipfile — skips the extra field, so the payload offset stays
 *     correct);
 *   - its own CRC-32 (IEEE 802.3, polynomial 0xEDB88320, reflected), so no
 *     package is required;
 *   - a FIXED DOS timestamp (1980-01-01 00:00) for every entry, which makes the
 *     output byte-for-byte reproducible: the same capture produces the same
 *     .usdz on every run and on every machine.
 *
 * What it deliberately does NOT do: Zip64 (>4 GiB), deflate, encryption, data
 * descriptors, comments, directories. Payloads here are a few hundred KB of
 * text; exceeding 4 GiB is treated as an error instead of silently producing a
 * corrupt archive.
 *
 * API:
 *   crc32(buf)                       -> unsigned 32-bit CRC of `buf`
 *   buildUsdz(files)                 -> Buffer (the whole .usdz)
 *   writeUsdz(outPath, files)        -> { path, bytes, entries:[{name,offset,size,crc}] }
 *   ZIP_LIMIT / MAX_ENTRIES          -> format limits enforced below
 *
 * `files` is [{ name: 'room.usda', data: Buffer|string }]. Order is preserved.
 */
const fs = require('fs');

/** Hard ZIP (non-Zip64) limits: 32-bit offsets/sizes and 65535 entries. */
const ZIP_LIMIT = 0xffffffff;
const MAX_ENTRIES = 0xffff;

/** Fixed DOS date/time: 1980-01-01 00:00:00 (the DOS epoch). Deterministic. */
const DOS_TIME = 0;
const DOS_DATE = ((1980 - 1980) << 9) | (1 << 5) | 1; // 0x0021

/* ---------------------------------------------------------------- CRC-32 -- */

const CRC_TABLE = (() => {
  const table = new Int32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c;
  }
  return table;
})();

/**
 * Standard CRC-32 as used by ZIP (reflected, init 0xFFFFFFFF, final xor).
 * @param {Buffer|Uint8Array|string} input
 * @returns {number} unsigned 32-bit CRC
 */
function crc32(input) {
  const buf = Buffer.isBuffer(input) ? input : Buffer.from(input);
  let c = -1;
  for (let i = 0; i < buf.length; i += 1) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}

/* --------------------------------------------------------------- helpers -- */

function toBuffer(data) {
  if (Buffer.isBuffer(data)) return data;
  if (data instanceof Uint8Array) return Buffer.from(data.buffer, data.byteOffset, data.byteLength);
  return Buffer.from(String(data), 'utf8');
}

/**
 * Length of the padding (an extra field) that puts the payload on a 64-byte
 * boundary. A ZIP extra field is itself a sequences of TLV records, so the
 * smallest usable field is 4 bytes; when less padding is needed we add a whole
 * 64-byte block (the alignment only cares about the total modulo 64).
 */
function alignedExtraLength(localHeaderOffset, nameLength) {
  const base = localHeaderOffset + 30 + nameLength;
  let pad = (64 - (base % 64)) % 64;
  if (pad !== 0 && pad < 4) pad += 64;
  return pad;
}

/* ----------------------------------------------------------------- write -- */

/**
 * @param {{name:string, data:Buffer|string}[]} files entry payloads, order kept
 * @returns {Buffer} the complete archive
 */
function buildUsdz(files) {
  return buildArchive(files).buffer;
}

function buildArchive(files) {
  if (!Array.isArray(files) || files.length === 0) throw new Error('usdz: at least one file is required');
  if (files.length > MAX_ENTRIES) throw new Error(`usdz: ${files.length} entries exceeds the non-Zip64 limit of ${MAX_ENTRIES}`);

  const entries = [];
  const chunks = [];
  let offset = 0;

  const push = (buf) => {
    chunks.push(buf);
    offset += buf.length;
    if (offset > ZIP_LIMIT) {
      throw new Error('usdz: archive would exceed 4 GiB; Zip64 is not implemented (this writer only handles small captures)');
    }
  };

  for (const file of files) {
    const name = String(file && file.name || '');
    if (!name) throw new Error('usdz: every entry needs a name');
    const nameBuf = Buffer.from(name, 'utf8');
    if (nameBuf.length > 0xffff) throw new Error(`usdz: entry name too long: ${name}`);
    const data = toBuffer(file && file.data);
    if (data.length > ZIP_LIMIT) throw new Error(`usdz: entry "${name}" exceeds 4 GiB`);

    const localOffset = offset;
    const extraLength = alignedExtraLength(localOffset, nameBuf.length);
    const crc = crc32(data);

    const header = Buffer.alloc(30);
    header.writeUInt32LE(0x04034b50, 0); // local file header signature
    header.writeUInt16LE(10, 4); // version needed to extract (1.0, STORE only)
    header.writeUInt16LE(0, 6); // general purpose flags (0 = stored, no descriptor)
    header.writeUInt16LE(0, 8); // compression method 0 = STORE
    header.writeUInt16LE(DOS_TIME, 10);
    header.writeUInt16LE(DOS_DATE, 12);
    header.writeUInt32LE(crc, 14);
    header.writeUInt32LE(data.length, 18); // compressed size == uncompressed (STORE)
    header.writeUInt32LE(data.length, 22);
    header.writeUInt16LE(nameBuf.length, 26);
    header.writeUInt16LE(extraLength, 28);

    push(header);
    push(nameBuf);

    if (extraLength > 0) {
      // Apple's USDZ alignment field (id 0x1986) padded with zeros. usdzip writes
      // exactly this; a generic 0x0000 field is legal ZIP but QuickLook refuses it.
      // unknown ids; we only need the length so the payload lands on 64 bytes.
      const extra = Buffer.alloc(extraLength);
      extra.writeUInt16LE(0x1986, 0);
      extra.writeUInt16LE(extraLength - 4, 2);
      push(extra);
    }

    // The payload must start 64-byte aligned. alignedExtraLength() guarantees it.
    if (offset % 64 !== 0) throw new Error(`usdz: internal alignment error for "${name}" (offset ${offset})`);
    const dataOffset = offset;
    push(data);

    entries.push({ name, offset: localOffset, dataOffset, size: data.length, crc });
  }

  const centralOffset = offset;
  for (const entry of entries) {
    const nameBuf = Buffer.from(entry.name, 'utf8');
    const cd = Buffer.alloc(46);
    cd.writeUInt32LE(0x02014b50, 0); // central directory header signature
    cd.writeUInt16LE(10, 4); // version made by (1.0, MS-DOS)
    cd.writeUInt16LE(10, 6); // version needed
    cd.writeUInt16LE(0, 8); // flags
    cd.writeUInt16LE(0, 10); // method STORE
    cd.writeUInt16LE(DOS_TIME, 12);
    cd.writeUInt16LE(DOS_DATE, 14);
    cd.writeUInt32LE(entry.crc, 16);
    cd.writeUInt32LE(entry.size, 20);
    cd.writeUInt32LE(entry.size, 24);
    cd.writeUInt16LE(nameBuf.length, 28);
    cd.writeUInt16LE(0, 30); // extra field length
    cd.writeUInt16LE(0, 32); // comment length
    cd.writeUInt16LE(0, 34); // disk number start
    cd.writeUInt16LE(0, 36); // internal attributes
    cd.writeUInt32LE(0, 38); // external attributes
    cd.writeUInt32LE(entry.offset, 42); // relative offset of local header
    push(cd);
    push(nameBuf);
  }

  const centralSize = offset - centralOffset;
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0); // end of central directory signature
  eocd.writeUInt16LE(0, 4); // this disk
  eocd.writeUInt16LE(0, 6); // disk with central directory
  eocd.writeUInt16LE(entries.length, 8);
  eocd.writeUInt16LE(entries.length, 10);
  eocd.writeUInt32LE(centralSize, 12);
  eocd.writeUInt32LE(centralOffset, 16);
  eocd.writeUInt16LE(0, 20); // comment length
  push(eocd);

  return { buffer: Buffer.concat(chunks, offset), entries };
}

/**
 * Write a .usdz archive.
 * @param {string} outPath
 * @param {{name:string, data:Buffer|string}[]} files
 * @returns {{path:string, bytes:number, entries:object[]}} entries carry the
 *   local-header offset, the (64-byte aligned) payload offset, size and CRC.
 */
function writeUsdz(outPath, files) {
  const { buffer, entries } = buildArchive(files);
  fs.writeFileSync(outPath, buffer);
  return { path: outPath, bytes: buffer.length, entries };
}

module.exports = { crc32, buildUsdz, writeUsdz, ZIP_LIMIT, MAX_ENTRIES, DOS_DATE, DOS_TIME };
