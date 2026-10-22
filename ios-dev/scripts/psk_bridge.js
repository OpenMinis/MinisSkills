#!/usr/bin/env node
// psk_bridge.js — Relay the "on-device TLS-PSK channel" as a local Unix socket.
//
// Why it is needed: Python 3.12's ssl has no PSK client callback (only 3.13 does), while iOS's RemotePairing
// channel only accepts TLS 1.2 + PSK. Node's tls.connect supports pskCallback, so let Node handle this small piece.
//
// Contract (pairs with the caller session.py):
//   Usage:  node psk_bridge.js <host> <port> <unix_socket_path>
//   stdin: the first line is the hex of the 32-byte PSK (never on the command line, otherwise ps can see it)
//   stdout: after the TLS handshake succeeds and the local socket is listening, print one line READY
//   Exit:  exit by itself when stdin closes (parent process exited), TLS closes, or an error occurs — no orphan processes
//   Exit codes: 0 normal; 1 argument/PSK error; 2 TLS connection failed; 3 local socket failed
'use strict';
const fs = require('fs');
const net = require('net');
const tls = require('tls');
const readline = require('readline');

const [host, portArg, sockPath] = [process.argv[2], process.argv[3], process.argv[4]];
const port = parseInt(portArg, 10);
if (!host || !(port > 0 && port < 65536) || !sockPath) {
  console.error('Usage: node psk_bridge.js <host> <port> <unix_socket_path>');
  process.exit(1);
}

const die = (code, msg) => { if (msg) console.error(msg); process.exit(code); };

// Follow the parent process out when it disappears
process.stdin.on('end', () => process.exit(0));
process.stdin.on('close', () => process.exit(0));

const rl = readline.createInterface({ input: process.stdin, terminal: false });
rl.once('line', (line) => {
  const hex = line.trim();
  if (!/^[0-9a-fA-F]{2,}$/.test(hex) || hex.length % 2) die(1, 'PSK is not valid hex');
  rl.removeAllListeners('line');
  start(Buffer.from(hex, 'hex'));
});

function start(psk) {
  try { fs.unlinkSync(sockPath); } catch (_) { /* it doesn't exist, fine */ }

  const upstream = tls.connect({
    host, port,
    minVersion: 'TLSv1.2', maxVersion: 'TLSv1.2',        // the device only speaks TLS 1.2 PSK suites
    ciphers: 'PSK-AES128-GCM-SHA256:PSK-AES256-GCM-SHA384:PSK-CHACHA20-POLY1305:PSK',
    rejectUnauthorized: false,                            // PSK suites have no certificates, identity relies on the pre-shared key
    checkServerIdentity: () => undefined,
    pskCallback: () => ({ psk, identity: '' }),
  });
  upstream.setNoDelay(true);
  upstream.setTimeout(15000, () => die(2, 'TLS connection to the device timed out (15s)'));

  let ready = false;
  upstream.once('secureConnect', () => {
    upstream.setTimeout(0);                               // no more idle timeout disconnects once the handshake is done
    const server = net.createServer((local) => {
      // Relay only one local connection at a time: the RemotePairing channel is single-session anyway
      local.pipe(upstream, { end: false });
      upstream.pipe(local, { end: false });
      local.on('error', () => {});
      local.on('close', () => process.exit(0));
    });
    server.on('error', (e) => die(3, 'local socket failed: ' + e.message));
    server.listen(sockPath, () => {
      try { fs.chmodSync(sockPath, 0o600); } catch (_) {}
      ready = true;
      process.stdout.write('READY\n');
    });
  });
  upstream.on('error', (e) => die(ready ? 0 : 2, 'TLS error: ' + e.message));
  upstream.on('close', () => process.exit(ready ? 0 : 2));
}
