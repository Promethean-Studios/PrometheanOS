#!/usr/bin/env python3
import argparse
from src.system.api.local_api import LocalPrometheanAPI
from src.system.services.promethean_service import PrometheanService


def main():
    parser = argparse.ArgumentParser(description="Promethean local system API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    args = parser.parse_args()

    api = LocalPrometheanAPI(service=PrometheanService(poll_interval=args.poll_interval), host=args.host, port=args.port)
    api.serve_forever()


if __name__ == "__main__":
    main()
