"""CLI for submitting search tasks."""

from pathlib import Path

import typer

from weibo_search.config import get_settings, setup_logging

app = typer.Typer(help="Weibo Search CLI")


@app.command()
def search(
    keyword: str = typer.Argument(None, help="Search keyword (or use --keywords)"),
    keywords: str = typer.Option(None, "--keywords", "-k", help="Path to keywords.jsonl"),
    pages: int = typer.Option(None, "--pages", "-p", help="Max pages per keyword"),
    direct: bool = typer.Option(False, "--direct", "-d", help="Run directly (no RQ)"),
    enqueue: bool = typer.Option(False, "--enqueue", "-e", help="Enqueue to RQ workers"),
):
    """Search Weibo for keywords.
    
    Examples:
        weibo-search 人工智能 --pages 5
        weibo-search --keywords data/keywords.jsonl
        weibo-search 测试 --direct
    """
    settings = get_settings()
    setup_logging(settings.debug)
    
    if pages is None:
        pages = settings.max_pages
    
    if keywords:
        # Process JSONL file
        path = Path(keywords)
        if not path.exists():
            typer.echo(f"File not found: {keywords}", err=True)
            raise typer.Exit(1)
        
        if direct:
            # Run directly
            from weibo_search.workers.search.jobs import search_keywords_from_jsonl
            
            typer.echo(f"Processing keywords from: {keywords}")
            result = search_keywords_from_jsonl(str(path), max_pages=pages)
            
            if result["success"]:
                typer.echo(f"✓ Completed: {result['success_count']}/{result['total_keywords']} keywords")
            else:
                typer.echo(f"✗ Failed: {result.get('error')}", err=True)
                raise typer.Exit(1)
        else:
            # Enqueue each keyword
            import json
            import redis
            from rq import Queue
            
            from weibo_search.config import QueueConfig
            from weibo_search.models import KeywordTask
            
            conn = redis.from_url(settings.redis_url)
            queue = Queue(QueueConfig.SEARCH, connection=conn)
            
            keywords_list = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        task = KeywordTask(**data)
                        keywords_list.append(task)
                    except Exception as e:
                        typer.echo(f"Skipping invalid line: {e}", err=True)
            
            # Sort by priority
            keywords_list.sort(key=lambda k: k.priority)
            
            typer.echo(f"Enqueuing {len(keywords_list)} keywords to {QueueConfig.SEARCH}")
            
            for task in keywords_list:
                from weibo_search.workers.search.jobs import search_keyword_job
                queue.enqueue(search_keyword_job, task.keyword, max_pages=pages)
                typer.echo(f"  + {task.keyword} (priority={task.priority})")
            
            typer.echo(f"✓ Enqueued {len(keywords_list)} jobs")
    
    elif keyword:
        # Single keyword
        if direct:
            from weibo_search.workers.search.jobs import search_keyword_job
            
            typer.echo(f"Searching: {keyword} (pages={pages})")
            result = search_keyword_job(keyword, max_pages=pages)
            
            if result["success"]:
                typer.echo(f"✓ Found {result['total_posts']} posts in {result['pages_fetched']} pages")
            else:
                error = result.get("error", "Unknown error")
                if result.get("needs_cookie"):
                    typer.echo("✗ No cookies available. Run: weibo-worker fill-pool", err=True)
                else:
                    typer.echo(f"✗ Failed: {error}", err=True)
                raise typer.Exit(1)
        else:
            import redis
            from rq import Queue
            
            from weibo_search.config import QueueConfig
            from weibo_search.workers.search.jobs import search_keyword_job
            
            conn = redis.from_url(settings.redis_url)
            queue = Queue(QueueConfig.SEARCH, connection=conn)
            
            job = queue.enqueue(search_keyword_job, keyword, max_pages=pages)
            typer.echo(f"✓ Enqueued search job: {job.id}")
    
    else:
        typer.echo("Please provide a keyword or --keywords file", err=True)
        raise typer.Exit(1)


@app.command()
def status():
    """Show search status and queue info."""
    import redis
    from rq import Queue
    
    from weibo_search.config import QueueConfig
    from weibo_search.storage.redis_client import CookieStore
    
    settings = get_settings()
    conn = redis.from_url(settings.redis_url)
    
    # Cookie pool status
    cookie_store = CookieStore(conn)
    pool_size = cookie_store.pool_size()
    
    # Queue status
    cookie_queue = Queue(QueueConfig.COOKIE, connection=conn)
    search_queue = Queue(QueueConfig.SEARCH, connection=conn)
    
    typer.echo("=== Weibo Search Status ===")
    typer.echo(f"Cookie Pool: {pool_size} cookies")
    typer.echo(f"Cookie Queue: {len(cookie_queue)} pending")
    typer.echo(f"Search Queue: {len(search_queue)} pending")


def main():
    """Entry point for weibo-search CLI."""
    app()


if __name__ == "__main__":
    main()
