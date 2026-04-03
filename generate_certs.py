import subprocess
import os

CA_KEY = "certs/ca.key"
CA_CERT = "certs/ca.crt"
SERVER_KEY = "certs/server.key"
SERVER_CSR = "certs/server.csr"
SERVER_CERT = "certs/server.pem"
SERVER_IP = "192.168.1.35"


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
