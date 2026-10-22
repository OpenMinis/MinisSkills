"""srp_client.py — The SRP-6a variant used by GrandSlam (line-by-line equivalent of xtool's SRPClient.swift).
This is Apple's non-standard variant, so a generic srp library cannot be used:
 - The password is SHA256'd first, then PBKDF2 (s2k uses the bytes directly; s2k_fo uses the lowercase hex string)
 - x = H(salt || H(":" || passkey))
 - u and k use H(pad(x)||pad(y)) padded to 256 bytes
 - M1 is built from xor(H(g),H(N)), H(username), salt, A, B, K
 - There is also a rolling transcript digest used to verify the server's np
"""
import hashlib, hmac, os
from cryptography.hazmat.primitives import padding as _pad
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

N = int("""AC6BDB41324A9A9BF166DE5E1389582FAF72B6651987EE07FC3192943DB56050A37329CBB4A099ED8193E0757767A13DD52312AB4B03310DCD7F48A9DA04FD50E8083969EDB767B0CF6095179A163AB3661A05FBD5FAAAE82918A9962F0B93B855F97993EC975EEAA80D740ADBF4FF747359D041D5C33EA71D281E446B14773BCA97B43A23FB801676BD207A436C6481F1D2B9078717461A5B9D32E688F87748544523B524B0D57D5EA77A2775D2ECFA032CFBDBF52FB3786160279004E57AE6AF874E7303CE53299CCC041C7BC308D82A5698F3A8D0C38271AE35F8E9DBFBB694B5C803D89F7AE435DE236D525F54759B65E372FCD68EF20FA7111F9E4AFF73""".replace("\n", ""), 16)
g = 2
NLEN = (N.bit_length() + 7) // 8   # 256

def sha(*parts): return hashlib.sha256(b"".join(parts)).digest()
def i2b(x):  # BigUInt.serialize(): big-endian, no leading zeros
    return x.to_bytes(max(1, (x.bit_length() + 7) // 8), "big")
def b2i(b): return int.from_bytes(b, "big")
def pad(b, n): return b.rjust(n, b"\0")

class SRPClient:
    def __init__(self, a=None):
        self.a = a if a is not None else b2i(os.urandom(32))
        self.A = pow(g, self.a, N)
        self.digest = hashlib.sha256()
        self.K = None; self.hamk = None

    # --- transcript ---
    def add_str(self, s): self.digest.update(s.encode())
    def add_data(self, d):
        self.digest.update(len(d).to_bytes(4, "little"))   # withUnsafeBytes(of: UInt32) is little-endian
        self.digest.update(d)

    def public_key(self): return i2b(self.A)

    def process_challenge(self, username, password, salt, iterations, legacy, B_raw):
        B = b2i(B_raw)
        if B % N == 0: raise ValueError("invalid B")
        hp = sha(password.encode())
        pin = hp.hex().encode() if legacy else hp
        passkey = hashlib.pbkdf2_hmac("sha256", pin, salt, iterations, 32)
        x = b2i(sha(salt, sha(b":", passkey)))
        u = b2i(sha(pad(i2b(self.A), NLEN), pad(i2b(B), NLEN)))
        k = b2i(sha(pad(i2b(N), NLEN), pad(i2b(g), NLEN)))
        base = (B - (pow(g, x, N) * k) % N) % N
        rawK = pow(base, self.a + u * x, N)
        self.K = sha(i2b(rawK))
        A_b = i2b(self.A)
        gH = sha(pad(i2b(g), 256))                          # padded(to: SHA256.byteCount * 8) = 256
        NH = sha(i2b(N))
        xorH = bytes(p ^ q for p, q in zip(gH, NH))
        M = sha(xorH, sha(username.encode()), salt, A_b, B_raw, self.K)
        self.hamk = sha(A_b, M, self.K)
        return M

    # --- verify / decrypt ---
    def _skey(self, name): return hmac.new(self.K, name.encode(), hashlib.sha256).digest()
    def verify_hamk(self, h): return hmac.compare_digest(h, self.hamk)
    def verify_np(self, np_):
        mac = hmac.new(self._skey("HMAC key:"), self.digest.copy().digest(), hashlib.sha256).digest()
        return hmac.compare_digest(np_, mac)
    def decrypt_cbc(self, data):
        key = self._skey("extra data key:"); iv = self._skey("extra data iv:")[:16]
        dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        pt = dec.update(data) + dec.finalize()
        un = _pad.PKCS7(128).unpadder()
        return un.update(pt) + un.finalize()
