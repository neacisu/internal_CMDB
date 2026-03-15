"""Tests for internalcmdb.seeds.taxonomy_seed — mocked DB seed function."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from internalcmdb.seeds.taxonomy_seed import (
    _CATALOGUE,
    seed,
)

# ---------------------------------------------------------------------------
# Catalogue structure tests (no DB needed)
# ---------------------------------------------------------------------------


class TestCatalogueStructure:
    def test_catalogue_is_non_empty(self) -> None:
        assert len(_CATALOGUE) > 0

    def test_all_entries_have_four_elements(self) -> None:
        for entry in _CATALOGUE:
            assert len(entry) == 4, f"Entry {entry[0]} has wrong length"

    def test_all_domain_codes_are_strings(self) -> None:
        for domain_code, *_ in _CATALOGUE:
            assert isinstance(domain_code, str)
            assert domain_code

    def test_all_names_are_strings(self) -> None:
        for _, name, *_ in _CATALOGUE:
            assert isinstance(name, str)
            assert name

    def test_all_descriptions_are_strings(self) -> None:
        for _, _, description, _ in _CATALOGUE:
            assert isinstance(description, str)
            assert description

    def test_all_terms_are_lists(self) -> None:
        for _, _, _, terms in _CATALOGUE:
            assert isinstance(terms, list)

    def test_all_terms_have_two_elements(self) -> None:
        for domain_code, _, _, terms in _CATALOGUE:
            for term in terms:
                assert len(term) == 2, f"Term in {domain_code} has wrong structure: {term}"

    def test_entity_kind_domain_exists(self) -> None:
        codes = [entry[0] for entry in _CATALOGUE]
        assert "entity_kind" in codes

    def test_domain_codes_are_unique(self) -> None:
        codes = [entry[0] for entry in _CATALOGUE]
        assert len(codes) == len(set(codes))

    def test_at_least_ten_domains(self) -> None:
        assert len(_CATALOGUE) >= 10

    def test_entity_kind_has_host_term(self) -> None:
        entry = next((e for e in _CATALOGUE if e[0] == "entity_kind"), None)
        assert entry is not None
        term_codes = [t[0] for t in entry[3]]
        assert "host" in term_codes

    def test_entity_kind_has_cluster_term(self) -> None:
        entry = next((e for e in _CATALOGUE if e[0] == "entity_kind"), None)
        assert entry is not None
        term_codes = [t[0] for t in entry[3]]
        assert "cluster" in term_codes


# ---------------------------------------------------------------------------
# seed() with mocked Connection
# ---------------------------------------------------------------------------


class TestSeedFunction:
    def _make_conn(self) -> MagicMock:
        conn = MagicMock()
        # Each execute() returns a result mock; fetchone returns a fixed uuid row
        uid = uuid.uuid4()
        result_mock = MagicMock()
        result_mock.fetchone.return_value = (uid,)
        conn.execute.return_value = result_mock
        return conn

    def test_seed_calls_commit(self) -> None:
        conn = self._make_conn()
        seed(conn)
        conn.commit.assert_called_once()

    def test_seed_calls_execute_for_each_domain(self) -> None:
        conn = self._make_conn()
        seed(conn)
        # Each domain does: INSERT + SELECT = 2 execute calls min
        # Plus each term does another INSERT = N+2 execute calls per domain
        assert conn.execute.call_count > len(_CATALOGUE)

    def test_seed_inserts_at_least_one_domain(self) -> None:
        conn = self._make_conn()
        seed(conn)
        # Verify execute was called (regardless of exact count)
        assert conn.execute.called

    def test_seed_prints_ok_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        conn = self._make_conn()
        seed(conn)
        captured = capsys.readouterr()
        assert "OK" in captured.out
        assert "taxonomy domains seeded" in captured.out
