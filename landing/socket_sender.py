import socket
import json

class SocketSender:
    def __init__(self, host='127.0.0.1', port=5005):
        """
        Initializes a UDP socket for local communication.
        """
        self.host = host
        self.port = port
        # Using SOCK_DGRAM for UDP protocol (fast, no handshake)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, data):
        """
        Converts the dictionary to a JSON string and sends it.
        """
        try:
            # Convert dict to JSON string and then to bytes
            message = json.dumps(data).encode('utf-8')
            self.sock.sendto(message, (self.host, self.port))
        except Exception as e:
            print(f"Failed to send data: {e}")

    def __del__(self):
        """
        Cleanup the socket when the object is destroyed.
        """
        self.sock.close()