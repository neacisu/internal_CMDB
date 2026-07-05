"""Tests for registry host search filter."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from internalcmdb.api.routers.registry import list_hosts, HostFilterParams


def test_list_hosts_applies_search_filter() -> None:
    db = MagicMock()
    mock_q = MagicMock()
    db.query.return_value = mock_q
    mock_q.filter.return_value = mock_q
    mock_q.order_by.return_value = mock_q

    host = MagicMock()
    host.hostname = "web-01"
    mock_q.offset.return_value.limit.return_value.all.return_value = [host]
    mock_q.count.return_value = 1

    filters = HostFilterParams(search="web")
    page = list_hosts(db=db, filters=filters, page=1, page_size=20)

    assert page.meta.total == 1
    assert mock_q.filter.called
    sql_filter = mock_q.filter.call_args[0]
    assert sql_filter  # ilike clause applied
