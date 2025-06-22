from glowtalk.api import app
import httpx
import argparse

def server_mode(host: str, port: int):
    from glowtalk.server import start_server
    start_server(host=host, port=port)

def worker_mode(url: str, verbose: bool, idle_threshold_seconds: int):
    from glowtalk.worker import Worker
    client = httpx.Client(base_url=url)
    my_worker = Worker(client, verbose=verbose, idle_threshold_seconds=idle_threshold_seconds)
    my_worker.work()

def main():
    parser = argparse.ArgumentParser(description='GlowTalk CLI')
    parser.add_argument('--host', default='0.0.0.0', help='Host to run the server on')
    parser.add_argument('--port', type=int, default=8585, help='Port to run the server on')
    parser.add_argument('--work_for', help='URL of GlowTalk server to work for')
    parser.add_argument('--quiet', action='store_true', help='Disable verbose output')
    parser.add_argument('--idle_threshold', type=int, default=30, help='How long to wait for the system to be unused by any person before doing intensive work.')

    args = parser.parse_args()

    if args.work_for:
        worker_mode(args.work_for, not args.quiet, args.idle_threshold)
    else:
        server_mode(args.host, args.port)

if __name__ == "__main__":
    main()
