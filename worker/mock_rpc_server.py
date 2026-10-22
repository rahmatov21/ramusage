"""Lightweight fallback RPC server for testing and simulation.
Runs on Windows without requiring any precompiled binaries or admin rights.
"""

import argparse
import socket
import sys
import time


def run_server(host: str = "0.0.0.0", port: int = 50052):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((host, port))
        server.listen(10)
        print(f"[MockRPC] Server listening on {host}:{port}", flush=True)

        while True:
            conn, addr = server.accept()
            try:
                data = conn.recv(1024)
                if data:
                    # Echo handshake / acknowledgment
                    conn.sendall(b"RPC_OK_V1\n")
            except Exception:
                pass
            finally:
                conn.close()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[MockRPC ERROR] {e}", file=sys.stderr, flush=True)
    finally:
        server.close()


def main():
    parser = argparse.ArgumentParser(description="Fallback RPC Server")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=50052)
    args = parser.parse_args()
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
