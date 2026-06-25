from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from tg_support.config import (
    ConfigError,
    DEFAULT_EMBEDDING_MODEL,
    SupportConfig,
    clear_telegram_authorization,
    credentials_from_dict,
    config_from_dict,
    load_config,
    load_telegram_credentials,
    profile_dir,
    write_config,
    write_telegram_authorization,
    write_telegram_credentials,
)
from tg_support.crawler import WebCrawler
from tg_support.indexing.chunking import chunk_messages, chunk_pages
from tg_support.indexing.hybrid import HybridRetriever
from tg_support.storage.db import SupportDatabase
from tg_support.storage.schema import CURRENT_SCHEMA_VERSION
from tg_support.support.context import draft_context
from tg_support.support.drafting import create_draft
from tg_support.support.posting import PostingError, apply_confirmation
from tg_support.support.stats import active_users, link_usage, message_count, replied_to_users
from tg_support.telegram_client import MISSING_CREDENTIALS_ERROR, TelegramError, TelegramService, TelethonGateway


def emit(payload: dict, code: int = 0) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code


def config_for_args(args: argparse.Namespace) -> SupportConfig:
    cfg_path = Path(args.config) if getattr(args, "config", None) else profile_dir(args.profile) / "config.json"
    return load_config(cfg_path)


def load_config_for_status(args: argparse.Namespace) -> tuple[SupportConfig | None, str | None]:
    cfg_path = Path(args.config) if getattr(args, "config", None) else profile_dir(args.profile) / "config.json"
    try:
        return load_config(cfg_path), None
    except FileNotFoundError:
        return None, "missing_config"
    except (ConfigError, OSError, json.JSONDecodeError):
        return None, "invalid_config"


def db_for_args(args: argparse.Namespace, initialize: bool = False) -> tuple[SupportConfig, SupportDatabase]:
    config = config_for_args(args)
    db = SupportDatabase(config.db_path)
    if initialize:
        db.initialize()
    return config, db


def telegram_service_for_args(args: argparse.Namespace) -> tuple[SupportConfig, TelegramService]:
    config = config_for_args(args)
    db = SupportDatabase(config.db_path)
    try:
        credentials = load_telegram_credentials(config.credentials_path)
    except (ConfigError, OSError, json.JSONDecodeError) as exc:
        raise TelegramError(MISSING_CREDENTIALS_ERROR) from exc
    return config, TelegramService(db, TelethonGateway(config.session_path, credentials.api_id, credentials.api_hash))


def table_count(db: SupportDatabase, table: str) -> int:
    try:
        return db.count(table)
    except Exception:
        return 0


def usable_page_count(db: SupportDatabase) -> int:
    try:
        with db.connect() as conn:
            return int(
                conn.execute("SELECT COUNT(*) AS count FROM pages WHERE status = 'ok' AND length(text) > 0").fetchone()["count"]
            )
    except Exception:
        return 0


def database_ready(db: SupportDatabase) -> bool:
    try:
        return db.schema_version() == CURRENT_SCHEMA_VERSION
    except Exception:
        return False


def profile_status(config: SupportConfig) -> dict:
    db = SupportDatabase(config.db_path)
    credentials_valid = False
    try:
        load_telegram_credentials(config.credentials_path)
        credentials_valid = True
    except (ConfigError, OSError, json.JSONDecodeError):
        pass

    database_ok = database_ready(db)
    session_present = config.session_path.exists() and config.authorization_path.exists()
    messages = table_count(db, "messages") if database_ok else 0
    pages = usable_page_count(db) if database_ok else 0
    chunks = table_count(db, "chunks") if database_ok else 0
    index_stale = True
    if chunks:
        try:
            index_stale = HybridRetriever(db).stale(config.embedding_model)
        except Exception:
            index_stale = True

    checks = {
        "config": True,
        "database": database_ok,
        "credentials": credentials_valid,
        "telegram_session": session_present,
        "telegram_history": messages > 0,
        "web_crawl": pages > 0,
        "chunks": chunks > 0,
        "index": chunks > 0 and not index_stale,
    }
    if not checks["database"]:
        next_action = "setup"
    elif not checks["credentials"]:
        next_action = "credentials"
    elif not checks["telegram_session"]:
        next_action = "login"
    elif not checks["telegram_history"]:
        next_action = "sync"
    elif not checks["web_crawl"]:
        next_action = "crawl"
    elif not checks["chunks"] or not checks["index"]:
        next_action = "index"
    else:
        next_action = "ready"
    return {
        "ok": next_action == "ready",
        "profile": config.profile,
        "profile_dir": str(config.profile_dir),
        "chat": config.chat,
        "checks": checks,
        "counts": {"messages": messages, "pages": pages, "chunks": chunks},
        "next_action": next_action,
    }


def command_setup(args: argparse.Namespace) -> int:
    if not args.chat or not args.seed:
        return emit({"ok": False, "error": "setup requires --chat and at least one --seed"}, 2)
    try:
        config = config_from_dict(
            {
                "profile": args.profile,
                "chat": args.chat,
                "seeds": [{"url": seed, "render": args.render} for seed in args.seed],
                "history_limit": args.history_limit,
                "embedding_model": args.embedding_model,
            },
            profile_dir_override=profile_dir(args.profile),
        )
        path = write_config(config)
        db = SupportDatabase(config.db_path)
        db.initialize()
        return emit({"ok": True, "config": str(path), "profile_dir": str(config.profile_dir), "db": str(config.db_path)})
    except ConfigError as exc:
        return emit({"ok": False, "error": str(exc)}, 2)


def command_credentials(args: argparse.Namespace) -> int:
    try:
        config = config_for_args(args)
        credentials = credentials_from_dict({"api_id": args.api_id, "api_hash": telegram_api_hash_for_args(args)})
        path = write_telegram_credentials(config, credentials)
        return emit({"ok": True, "credentials": str(path), "api_id": credentials.api_id, "api_hash": "<redacted>"})
    except (ConfigError, OSError, json.JSONDecodeError) as exc:
        return emit({"ok": False, "error": str(exc)}, 2)


def telegram_api_hash_for_args(args: argparse.Namespace) -> str:
    if args.api_hash_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    if sys.stdin.isatty():
        return getpass.getpass("Telegram API hash: ")
    raise ConfigError("Telegram API hash is required. Use --api-hash-stdin or run credentials interactively.")


def command_status(args: argparse.Namespace) -> int:
    config, error = load_config_for_status(args)
    if config is None:
        return emit({"ok": False, "profile": args.profile, "checks": {"config": False}, "next_action": "setup", "error": error})
    return emit(profile_status(config))


def command_crawl(args: argparse.Namespace) -> int:
    config, db = db_for_args(args, initialize=True)
    crawler = WebCrawler(db)
    results = [crawler.crawl_seed(seed).__dict__ for seed in config.seeds]
    return emit({"ok": True, "results": results})


def command_login(args: argparse.Namespace) -> int:
    config = None
    try:
        config, service = telegram_service_for_args(args)
        ok = service.login()
        if ok:
            write_telegram_authorization(config)
        else:
            clear_telegram_authorization(config)
        return emit({"ok": ok})
    except TelegramError as exc:
        if config is not None:
            clear_telegram_authorization(config)
        return emit({"ok": False, "error": str(exc)}, 2)


def command_sync(args: argparse.Namespace) -> int:
    try:
        config, service = telegram_service_for_args(args)
        count = service.ingest_history(config.chat, args.limit or config.history_limit)
        return emit({"ok": True, "messages": count})
    except TelegramError as exc:
        return emit({"ok": False, "error": str(exc)}, 2)


def command_index(args: argparse.Namespace) -> int:
    config, db = db_for_args(args, initialize=True)
    page_chunks = chunk_pages(db)
    message_chunks = chunk_messages(db)
    run_id = HybridRetriever(db).build(config.embedding_model)
    return emit({"ok": True, "index_run_id": run_id, "page_chunks": page_chunks, "message_chunks": message_chunks})


def command_search(args: argparse.Namespace) -> int:
    _config, db = db_for_args(args)
    results = HybridRetriever(db).search(args.query, limit=args.limit)
    return emit({"ok": True, "results": results})


def command_stats(args: argparse.Namespace) -> int:
    _config, db = db_for_args(args)
    if args.kind == "message-count":
        payload = {"count": message_count(db, args.since)}
    elif args.kind == "active-users":
        payload = {"users": active_users(db, args.limit)}
    elif args.kind == "replied-to-users":
        payload = {"users": replied_to_users(db, args.limit)}
    elif args.kind == "links":
        payload = {"links": link_usage(db, args.limit)}
    else:
        return emit({"ok": False, "error": f"Unsupported stats kind: {args.kind}"}, 2)
    return emit({"ok": True, "kind": args.kind, **payload})


def command_draft_context(args: argparse.Namespace) -> int:
    _config, db = db_for_args(args)
    context = draft_context(db, args.query or "", username=args.user, message_id=args.message_id, limit=args.limit)
    return emit({"ok": True, "context": context})


def command_draft_create(args: argparse.Namespace) -> int:
    config, db = db_for_args(args)
    evidence = json.loads(Path(args.evidence_json).read_text()) if args.evidence_json else {}
    result = create_draft(db, config.chat, args.text, evidence, target_user=args.user, target_message_id=args.message_id)
    return emit({"ok": True, **result, "target_chat": config.chat, "target_user": args.user, "target_message_id": args.message_id, "message_text": args.text})


def command_confirm(args: argparse.Namespace) -> int:
    config, db = db_for_args(args)
    try:
        credentials = load_telegram_credentials(config.credentials_path)
        result = apply_confirmation(db, args.token, TelethonGateway(config.session_path, credentials.api_id, credentials.api_hash))
        return emit({"ok": True, **result})
    except (ConfigError, OSError, json.JSONDecodeError):
        return emit({"ok": False, "error": MISSING_CREDENTIALS_ERROR}, 2)
    except (PostingError, TelegramError) as exc:
        return emit({"ok": False, "error": str(exc)}, 2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tg-support")
    parser.add_argument("--profile", default="default")
    parser.add_argument("--config")
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup")
    setup.add_argument("--chat", required=True)
    setup.add_argument("--seed", action="append")
    setup.add_argument("--render", choices=["auto", "always", "never"], default="auto")
    setup.add_argument("--history-limit", type=int, default=1000)
    setup.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    setup.set_defaults(func=command_setup)

    credentials = sub.add_parser("credentials")
    credentials.add_argument("--api-id", required=True)
    credentials.add_argument("--api-hash-stdin", action="store_true")
    credentials.set_defaults(func=command_credentials)

    sub.add_parser("status").set_defaults(func=command_status)
    sub.add_parser("crawl").set_defaults(func=command_crawl)
    sub.add_parser("login").set_defaults(func=command_login)
    sync = sub.add_parser("sync")
    sync.add_argument("--limit", type=int)
    sync.set_defaults(func=command_sync)

    sub.add_parser("index").set_defaults(func=command_index)
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)
    search.set_defaults(func=command_search)

    stats = sub.add_parser("stats")
    stats.add_argument("kind", choices=["message-count", "active-users", "replied-to-users", "links"])
    stats.add_argument("--since")
    stats.add_argument("--limit", type=int, default=10)
    stats.set_defaults(func=command_stats)

    draft = sub.add_parser("draft-context")
    draft.add_argument("--query", default="")
    draft.add_argument("--user")
    draft.add_argument("--message-id", type=int)
    draft.add_argument("--limit", type=int, default=6)
    draft.set_defaults(func=command_draft_context)

    create = sub.add_parser("draft-create")
    create.add_argument("--text", required=True)
    create.add_argument("--user")
    create.add_argument("--message-id", type=int)
    create.add_argument("--evidence-json")
    create.set_defaults(func=command_draft_create)

    confirm = sub.add_parser("confirm")
    confirm.add_argument("token")
    confirm.set_defaults(func=command_confirm)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
