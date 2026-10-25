"""Local addresses shared by HTTP and WebSocket origin checks."""
import os


def configured_port():
    try:
        port = int(os.getenv('COACH_PORT', '8765'))
    except ValueError as error:
        raise ValueError('COACH_PORT must be an integer between 1024 and 65535') from error
    if not 1024 <= port <= 65535:
        raise ValueError('COACH_PORT must be between 1024 and 65535')
    return port


PORT = configured_port()
ALLOWED_ORIGINS = {
    f'http://{host}:{port}'
    for host in ('localhost', '127.0.0.1')
    for port in {PORT, 8766, 5173, 8000}
}
