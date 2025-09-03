#!/usr/bin/env python3
"""
Dump ONVIF events (incl. motion) to console.

Usage:
  python dump_onvif_events.py 192.168.1.50 --user admin --password yourpass
"""
import argparse
import json
import sys
from datetime import timedelta
from onvif import ONVIFCamera
from onvif.exceptions import ONVIFError
from zeep.helpers import serialize_object

def jprint(obj):
    print(json.dumps(serialize_object(obj), indent=2, default=str, ensure_ascii=False))

def main():
    ap = argparse.ArgumentParser(description="Dump ONVIF events to console")
    ap.add_argument("host")
    ap.add_argument("--user", default="")
    ap.add_argument("--password", default="")
    ap.add_argument("--port", type=int, default=80)
    ap.add_argument("--timeout", type=int, default=15, help="Pull timeout seconds")
    ap.add_argument("--limit", type=int, default=10, help="Messages per pull")
    ap.add_argument("--list-only", action="store_true", help="List topics then exit")
    ap.add_argument("--duration", type=int, default=0, help="Seconds to run; 0=forever")
    args = ap.parse_args()

    cam = ONVIFCamera(args.host, args.port, args.user, args.password)

    # Events service
    events = cam.create_events_service()

    print("=== Camera Event Properties (topics) ===")
    props = events.GetEventProperties()
    jprint(props)
    print("========================================\n")

    if args.list_only:
        return

    # --- Create PullPoint subscription (robust fallbacks) ---
    sub = None
    # Preferred: pass a single positional dict with xs:duration string
    try:
        sub = events.CreatePullPointSubscription({
            "InitialTerminationTime": "PT300S"  # 5 minutes
        })
    except TypeError:
        # Wrapper rejects kwargs-like dict? Try without args.
        sub = events.CreatePullPointSubscription()
    except ONVIFError:
        # Some stacks still wrap TypeError as ONVIFError
        try:
            sub = events.CreatePullPointSubscription()
        except Exception as e:
            print(f"CreatePullPointSubscription failed: {e}", file=sys.stderr)
            sys.exit(2)

    # --- Bind PullPoint client to the subscription endpoint ---
    pullpoint = cam.create_pullpoint_service()
    try:
        addr = getattr(getattr(sub, "SubscriptionReference", None), "Address", None)
        if addr:
            # Different forks expose set_location or set_address
            try:
                pullpoint.ws_client.set_location(addr)
            except Exception:
                pullpoint.ws_client.set_address(addr)
    except Exception:
        pass  # Some cams work without overriding

    # --- Pull loop ---
    print("Listening for ONVIF events (Ctrl+C to stop)…\n")
    elapsed = 0
    try:
        while args.duration == 0 or elapsed < args.duration:
            # Build a single positional request object (preferred)
            try:
                req = pullpoint.create_type("PullMessages")
                # Use xs:duration string for max compatibility
                req.Timeout = f"PT{args.timeout}S"
                req.MessageLimit = args.limit
                resp = pullpoint.PullMessages(req)
            except Exception:
                # Fallback: pass one positional dict (no kwargs)
                resp = pullpoint.PullMessages({
                    "Timeout": f"PT{args.timeout}S",
                    "MessageLimit": args.limit
                })

            msgs = getattr(resp, "NotificationMessage", []) or []
            for m in msgs:
                jprint(m)
                print("-" * 60)

            elapsed += args.timeout
    except KeyboardInterrupt:
        pass

    # Optional: Unsubscribe if supported
    try:
        mgr = cam.create_subscription_service()
        try:
            mgr.ws_client.set_location(sub.SubscriptionReference.Address)
        except Exception:
            pass
        if hasattr(mgr, "Unsubscribe"):
            mgr.Unsubscribe()
    except Exception:
        pass

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    main()
