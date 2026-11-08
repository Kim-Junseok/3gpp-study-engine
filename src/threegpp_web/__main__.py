"""Run a private local development server, never a deployment command."""
from __future__ import annotations

import argparse
import ipaddress

from .config import Settings


def main():
    parser = argparse.ArgumentParser(description="Private 3GPP research web app (Stage A)")
    parser.add_argument("--data-root", help="Existing prepared corpus (never acquired automatically)")
    parser.add_argument("--state-root", help="Persistent app state, separate from corpus")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--fixture", action="store_true", help="Label explicit synthetic fixture mode")
    args = parser.parse_args()
    if args.fixture and not args.data_root:
        parser.error("--fixture requires an explicit, separate --data-root directory")
    try:
        settings = Settings.from_env(source=args.data_root, state=args.state_root,
                                     fixture_mode=args.fixture)
        loopback = args.host == "localhost" or ipaddress.ip_address(args.host).is_loopback
        if not loopback and not settings.secure_cookies:
            parser.error("Remote binding requires HTTPS ingress and THREEGPP_WEB_SECURE_COOKIES=1")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    import uvicorn
    from .app import create_app
    uvicorn.run(create_app(settings), host=args.host, port=args.port,
                access_log=False, proxy_headers=False)


if __name__ == "__main__":
    main()
