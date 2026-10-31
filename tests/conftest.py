import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import database as db  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.config import Config  # noqa: E402
from backend.models import MetricSample  # noqa: E402


def make_cfg(tmp_path, token=""):
    return Config(host="127.0.0.1", port=5000, db_path=str(tmp_path / "t.db"), poll_seconds=1,
                  retention_days=7, disk_path="/", services=["ssh", "cron"], api_token=token,
                  disable_collector=True)


def make_sample(ts=1000.0, cpu=10.0, mem=10.0, disk=10.0, host="testhost"):
    return MetricSample(ts=ts, hostname=host, cpu_percent=cpu, load1=0.1, load5=0.1, load15=0.1,
                        mem_percent=mem, mem_total=100, mem_used=10, mem_available=90,
                        disk_percent=disk, disk_total=100, disk_used=10, disk_free=90,
                        net_bytes_sent=1000, net_bytes_recv=2000, net_packets_sent=10, net_packets_recv=20)


@pytest.fixture
def cfg(tmp_path):
    return make_cfg(tmp_path)


@pytest.fixture
def dbpath(cfg):
    db.init_db(cfg.db_path)
    return cfg.db_path


@pytest.fixture
def client(cfg):
    return create_app(cfg, start_agent=False).test_client()


@pytest.fixture
def secure_client(tmp_path):
    return create_app(make_cfg(tmp_path, token="s3cret"), start_agent=False).test_client()
