"""Launch the built local application: python -m backend."""
import uvicorn
from .runtime import PORT

if __name__ == '__main__':
    uvicorn.run('backend.app:app', host='127.0.0.1', port=PORT)
