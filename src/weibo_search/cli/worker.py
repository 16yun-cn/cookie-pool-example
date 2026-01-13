"""CLI for starting RQ workers."""

import typer

from weibo_search.config import QueueConfig, get_settings, setup_logging

app = typer.Typer(help="Weibo Search Workers")


@app.command()
def cookie(
    headless: bool = typer.Option(True, help="Run browser in headless mode"),
    burst: bool = typer.Option(False, help="Run in burst mode (process and exit)"),
):
    """Start cookie generation worker."""
    import redis
    from rq import Queue, Worker

    settings = get_settings()
    setup_logging(settings.debug)
    
    conn = redis.from_url(settings.redis_url)
    queue = Queue(QueueConfig.COOKIE, connection=conn)
    
    typer.echo(f"Starting cookie worker (headless={headless})")
    typer.echo(f"Queue: {QueueConfig.COOKIE}")
    typer.echo(f"Redis: {settings.redis_url}")
    
    worker = Worker([queue], connection=conn)
    worker.work(burst=burst)


@app.command()
def search(
    burst: bool = typer.Option(False, help="Run in burst mode (process and exit)"),
):
    """Start search worker."""
    import redis
    from rq import Queue, Worker

    settings = get_settings()
    setup_logging(settings.debug)
    
    conn = redis.from_url(settings.redis_url)
    queue = Queue(QueueConfig.SEARCH, connection=conn)
    
    typer.echo(f"Starting search worker")
    typer.echo(f"Queue: {QueueConfig.SEARCH}")
    typer.echo(f"Redis: {settings.redis_url}")
    
    worker = Worker([queue], connection=conn)
    worker.work(burst=burst)


@app.command(name="all")
def all_workers(
    headless: bool = typer.Option(True, help="Run browser in headless mode"),
):
    """Start all workers (cookie + search)."""
    import redis
    from rq import Queue, Worker

    settings = get_settings()
    setup_logging(settings.debug)
    
    conn = redis.from_url(settings.redis_url)
    queues = [
        Queue(QueueConfig.COOKIE, connection=conn),
        Queue(QueueConfig.SEARCH, connection=conn),
    ]
    
    typer.echo(f"Starting all workers")
    typer.echo(f"Queues: {QueueConfig.ALL}")
    typer.echo(f"Redis: {settings.redis_url}")
    
    worker = Worker(queues, connection=conn)
    worker.work()


@app.command(name="fill-pool")
def fill_pool(
    count: int = typer.Option(1, help="Number of cookies to generate"),
    headless: bool = typer.Option(True, help="Run browser in headless mode"),
):
    """Fill cookie pool directly (without RQ)."""
    from weibo_search.workers.cookie.jobs import ensure_cookie_pool
    
    settings = get_settings()
    setup_logging(settings.debug)
    
    typer.echo(f"Filling cookie pool (count={count}, headless={headless})")
    
    result = ensure_cookie_pool(min_size=count, headless=headless)
    
    if result["success"]:
        typer.echo(f"✓ Pool size: {result['pool_size']}, generated: {result['generated']}")
    else:
        typer.echo(f"✗ Failed: {result.get('errors')}", err=True)
        raise typer.Exit(1)


def main():
    """Entry point for weibo-worker CLI."""
    app()


if __name__ == "__main__":
    main()
