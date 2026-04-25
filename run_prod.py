import os
from waitress import serve
from fabouanes.app_factory import create_app
from fabouanes.runtime_app import log_server_start

app = create_app()

if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', '5000'))
    log_server_start()
    serve(app, host=host, port=port, threads=int(os.environ.get('WAITRESS_THREADS', '8')))
