import argparse
import datetime as dt
from pathlib import Path

from intranet_side.info_extract.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="pipeline.yaml")
    p.add_argument("--action", choices=["crawl", "upload", "pull", "extract", "all"], default="all")
    p.add_argument("--date", default="today", help="YYYY-MM-DD or 'today'")
    p.add_argument("--max-per-site", type=int, default=50)
    p.add_argument("--proxy", default=None)
    p.add_argument("--site-id", action="append", default=None)
    p.add_argument("--test-mode", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    target_date = dt.date.today() if args.date == "today" else dt.date.fromisoformat(args.date)
    print(
        f"[info_extract_main] start action={args.action} date={target_date} max_per_site={args.max_per_site} test_mode={args.test_mode} site_ids={args.site_id or '-'}",
        flush=True,
    )
    run_pipeline(
        config_path=Path(args.config),
        action=args.action,
        target_date=target_date,
        max_per_site=args.max_per_site,
        proxy=args.proxy,
        site_ids=set(args.site_id) if args.site_id else None,
        test_mode=args.test_mode,
    )
    print("[info_extract_main] completed", flush=True)


if __name__ == "__main__":
    main()
