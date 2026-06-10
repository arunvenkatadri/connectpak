"""Offline tests for CassandraConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.nosql.cassandra.connector import CassandraConnector, _parse_config


def test_class_metadata() -> None:
    c = CassandraConnector.__new__(CassandraConnector)
    assert c.name == "cassandra"


def test_parse_config_hosts_only() -> None:
    p = _parse_config("10.0.0.1,10.0.0.2")
    assert p["contact_points"] == ["10.0.0.1", "10.0.0.2"]
    assert p["port"] == 9042
    assert p["user"] is None


def test_parse_config_with_auth_and_port() -> None:
    p = _parse_config("u:pw@cass.example.com:9043")
    assert p["contact_points"] == ["cass.example.com"]
    assert p["port"] == 9043
    assert p["user"] == "u"
    assert p["password"] == "pw"


@pytest.mark.parametrize(
    "cql",
    [
        "INSERT INTO users (id) VALUES (1)",
        "UPDATE users SET x = 1",
        "DELETE FROM users",
        "DROP TABLE users",
        "CREATE TABLE foo (id int PRIMARY KEY)",
        "TRUNCATE users",
    ],
)
def test_query_rejects_write_cql(cql: str) -> None:
    c = CassandraConnector("127.0.0.1")
    with pytest.raises(WriteOperationError):
        c.query(cql)
