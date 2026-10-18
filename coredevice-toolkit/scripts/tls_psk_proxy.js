#!/usr/bin/env node
/**
 * tls_psk_proxy.js: Node.js TLS-PSK to Unix Domain Socket relay bridge.
 * 
 * Security:
 * - PSK is read securely from stdin (never passed via argv or logged).
 * - Unix domain socket is hosted inside an isolated 0700 private directory.
 * - Auto-terminates when stdin closes (parent process exit).
 */

const tls = require('tls');
const net = require('net');
const fs = require('fs');
const readline = require('readline');

const host = process.argv[2] || '10.7.0.1';
const port = parseInt(process.argv[3], 10);
const unixSock = process.argv[4];

if (!port || !unixSock) {
  console.error("Usage: node tls_psk_proxy.js <host> <port> <unix_sock>");
  process.exit(1);
}

// 监听 stdin 关闭事件：父进程退出时自动自尽，杜绝孤儿/僵尸进程
process.stdin.on('end', () => { process.exit(0); });
process.stdin.on('close', () => { process.exit(0); });

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false
});

rl.once('line', (line) => {
  const trimmed = line.trim();
  if (!trimmed) {
    console.error("Error: Empty PSK received via stdin");
    process.exit(1);
  }
  try {
    const psk = Buffer.from(trimmed, 'hex');
    rl.close();
    startProxy(psk);
  } catch (err) {
    console.error("Error parsing PSK:", err.message);
    process.exit(1);
  }
});

function startProxy(psk) {
  if (fs.existsSync(unixSock)) {
    try { fs.unlinkSync(unixSock); } catch(e) {}
  }

  const tlsSocket = tls.connect({
    host: host,
    port: port,
    ciphers: 'PSK-AES128-GCM-SHA256:PSK-AES256-GCM-SHA384:PSK-CHACHA20-POLY1305:PSK-AES128-CBC-SHA256:PSK-AES256-CBC-SHA384:PSK-AES128-CBC-SHA:PSK-AES256-CBC-SHA:PSK',
    minVersion: 'TLSv1.2',
    maxVersion: 'TLSv1.2',
    checkServerIdentity: () => undefined,
    rejectUnauthorized: false,
    pskCallback: () => {
      return { psk: psk, identity: '' };
    }
  }, () => {
    process.stdout.write('READY\n');
  });

  tlsSocket.on('error', (err) => {
    console.error('TLS Socket Error:', err.message);
    process.exit(1);
  });

  tlsSocket.on('close', () => {
    process.exit(0);
  });

  const server = net.createServer((clientSocket) => {
    clientSocket.pipe(tlsSocket);
    tlsSocket.pipe(clientSocket);
    clientSocket.on('error', () => {});
    tlsSocket.on('error', () => {});
  });

  server.listen(unixSock, () => {});
}
