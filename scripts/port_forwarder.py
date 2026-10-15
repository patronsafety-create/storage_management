"""
NexusPour ERP - Port 80 to Port 8000 Forwarder
Enables opening http://localhost directly without typing :8000
"""
import socket
import threading

def handle_client(client_socket):
    try:
        remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_socket.connect(('127.0.0.1', 8000))
    except Exception as e:
        client_socket.close()
        return

    def forward(src, dst):
        try:
            while True:
                data = src.recv(4096)
                if not data:
                    break
                dst.sendall(data)
        except Exception:
            pass
        finally:
            try:
                src.close()
            except Exception:
                pass
            try:
                dst.close()
            except Exception:
                pass

    t1 = threading.Thread(target=forward, args=(client_socket, remote_socket), daemon=True)
    t2 = threading.Thread(target=forward, args=(remote_socket, client_socket), daemon=True)
    t1.start()
    t2.start()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(('0.0.0.0', 80))
        server.listen(50)
        print("Port 80 forwarder listening on 0.0.0.0:80 -> 127.0.0.1:8000")
        while True:
            client, addr = server.accept()
            threading.Thread(target=handle_client, args=(client,), daemon=True).start()
    except Exception as e:
        print(f"Port 80 error: {e}")

if __name__ == '__main__':
    main()
