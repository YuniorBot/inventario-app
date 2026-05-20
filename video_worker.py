from redis import Redis
from rq import Worker

from inventario_app import create_app


app = create_app({"SKIP_DATA_SEED": True})


if __name__ == "__main__":
    with app.app_context():
        redis_conn = Redis.from_url(app.config["REDIS_URL"])
        worker = Worker([app.config.get("VIDEO_QUEUE_NAME", "videos")], connection=redis_conn)
        worker.work()
