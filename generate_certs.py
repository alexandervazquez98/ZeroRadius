import os
import socket
import subprocess

CA_KEY = "certs/ca.key"
CA_CERT = "certs/ca.crt"
SERVER_KEY = "certs/server.key"
SERVER_CSR = "certs/server.csr"
SERVER_CERT = "certs/server.pem"


def _resolve_server_ip():
    """Resolve the IP to embed in the server cert's SAN.

    Resolution order:
      1. ``SERVER_IP`` environment variable (explicit override; intended for
         tests and reproducible builds).
      2. Best-effort host IPv4 detection via a UDP socket connected to a
         public address (no packets leave the host).
      3. ``socket.gethostbyname(socket.gethostname())`` as a last resort.
      4. ``127.0.0.1`` as a final fallback so cert generation never crashes.

    Fixes Issue #79 — the previous hardcoded ``192.168.1.35`` silently
    produced certs with the wrong SAN on any other host.
    """
    env_ip = os.environ.get("SERVER_IP", "").strip()
    if env_ip:
        print(f"[generate_certs] Using SERVER_IP from environment: {env_ip}")
        return env_ip

    # UDP-socket trick: opening a socket to a public address does not send
    # any traffic, but the kernel picks the outbound interface and we can
    # read back the local address it chose.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        detected = sock.getsockname()[0]
        if detected and not detected.startswith("0."):
            print(f"[generate_certs] Auto-detected host IP: {detected}")
            return detected
    except OSError:
        pass
    finally:
        sock.close()

    try:
        detected = socket.gethostbyname(socket.gethostname())
        if detected and not detected.startswith("127."):
            print(f"[generate_certs] Auto-detected host IP via hostname: {detected}")
            return detected
    except socket.gaierror:
        pass

    print("[generate_certs] WARNING: could not detect a non-loopback host IP; "
          "falling back to 127.0.0.1. Set SERVER_IP to override.")
    return "127.0.0.1"


SERVER_IP = _resolve_server_ip()


def run_openssl(args):
    result = subprocess.run(["openssl"] + args, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"openssl error: {result.stderr}")
    return result.stdout


def create_ca():
    if not os.path.exists("certs"):
        os.makedirs("certs")

    run_openssl(["genrsa", "-out", CA_KEY, "2048"])
    run_openssl(
        [
            "req",
            "-new",
            "-x509",
            "-days",
            "3650",
            "-key",
            CA_KEY,
            "-out",
            CA_CERT,
            "-subj",
            "/C=US/ST=California/L=San Francisco/O=My Company/CN=ZeroRadius CA",
            "-extensions",
            "v3_ca",
        ]
    )
    print("CA key and certificate generated.")


def create_server_cert():
    run_openssl(["genrsa", "-out", SERVER_KEY, "2048"])
    print("Server key generated.")

    run_openssl(
        [
            "req",
            "-new",
            "-key",
            SERVER_KEY,
            "-out",
            SERVER_CSR,
            "-subj",
            "/C=US/ST=California/L=San Francisco/O=My Company/CN=server",
        ]
    )
    print("Server CSR generated.")

    config = """[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn

[dn]
C = US
ST = California
L = San Francisco
O = My Company
CN = server

[server_ext]
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = IP:{ip}
""".format(ip=SERVER_IP)

    config_file = "certs/server_ext.cnf"
    with open(config_file, "w") as f:
        f.write(config)

    run_openssl(
        [
            "x509",
            "-req",
            "-in",
            SERVER_CSR,
            "-CA",
            CA_CERT,
            "-CAkey",
            CA_KEY,
            "-CAcreateserial",
            "-out",
            SERVER_CERT,
            "-days",
            "365",
            "-extfile",
            config_file,
            "-extensions",
            "server_ext",
        ]
    )

    os.remove(config_file)
    print("Server certificate generated with CA:FALSE and IP:{ip}".format(ip=SERVER_IP))


if __name__ == "__main__":
    create_ca()
    create_server_cert()
    print("All certificates generated in certs/ directory.")
