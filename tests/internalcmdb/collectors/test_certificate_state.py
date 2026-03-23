"""Tests for certificate_state collector helpers."""

from __future__ import annotations

from internalcmdb.collectors.agent.collectors.certificate_state import _rdn_tuple_to_dict


def test_rdn_tuple_to_dict_flattens_openssl_subject() -> None:
    # Typical getpeercert() subject layout: tuple of RDNs, each RDN is tuple of (attr, value).
    subject = (
        (("countryName", "US"),),
        (("commonName", "example.internal"),),
    )
    assert _rdn_tuple_to_dict(subject) == {
        "countryName": "US",
        "commonName": "example.internal",
    }


def test_rdn_tuple_to_dict_multiple_avas_same_rdn() -> None:
    rdn = (("organizationName", "Acme"), ("organizationalUnitName", "Infra"))
    assert _rdn_tuple_to_dict((rdn,)) == {
        "organizationName": "Acme",
        "organizationalUnitName": "Infra",
    }


def test_rdn_tuple_to_dict_empty() -> None:
    assert _rdn_tuple_to_dict(()) == {}
