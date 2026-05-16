import argparse
import datetime as dt
from pathlib import Path

from internet_side.crawler.runner import run


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="sites.yaml")
    p.add_argument("--date", default="today", help="YYYY-MM-DD or 'today'")
    p.add_argument("--today-only", action="store_true", help="skip items not published on target date when publish_time is available")
    p.add_argument("--max-per-site", type=int, default=50)
    p.add_argument("--proxy", default=None, help="Override proxy for all sites, e.g. http://127.0.0.1:7890")
    p.add_argument("--site-id", action="append", default=None, help="Run only specific site_id; can be repeated")
    p.add_argument("--test-mode", action="store_true", help="Run only one site and up to 3 articles for testing")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.date == "today":
        target_date = dt.date.today()
    else:
        target_date = dt.date.fromisoformat(args.date)
    print(
        f"[main] start date={target_date} max_per_site={args.max_per_site} test_mode={args.test_mode} site_ids={args.site_id or '-'} proxy={args.proxy or '-'}",
        flush=True,
    )
    run(
        config_path=Path(args.config),
        target_date=target_date,
        today_only=args.today_only,
        max_per_site=args.max_per_site,
        proxy_override=args.proxy,
        site_ids=set(args.site_id) if args.site_id else None,
        test_mode=args.test_mode,
    )
    print("[main] completed", flush=True)


if __name__ == "__main__":
    main()
