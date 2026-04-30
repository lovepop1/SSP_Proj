import socket
import threading

def handle_client(conn):
    try:
        while True:
            # We simply read up to a large chunk and echo back
            # For the baseline test, we bypass any encoding overhead
            data = conn.recv(1024 * 1024)
            if not data:
                break
            conn.sendall(data)
    except ConnectionResetError:
        pass
    finally:
        conn.close()

def start_tcp_server(host='0.0.0.0', port=9000):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    server.bind((host, port))
    server.listen(100) # Large backlog equivalent to an HTTP server
    print(f"TCP Baseline server listening on {host}:{port}")

    try:
        while True:
            conn, addr = server.accept()
            # Standard thread per connection logic
            thread = threading.Thread(target=handle_client, args=(conn,))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("TCP server shutting down.")
    finally:
        server.close()

if __name__ == "__main__":
    start_tcp_server()
