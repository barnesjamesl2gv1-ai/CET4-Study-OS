import socket

from launcher.windows_launcher import choose_socket


def test_port_conflict_chooses_another_loopback_port():
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        listener = choose_socket(occupied.getsockname()[1])
        try:
            assert listener.getsockname()[0] == "127.0.0.1"
            assert listener.getsockname()[1] != occupied.getsockname()[1]
        finally:
            listener.close()
