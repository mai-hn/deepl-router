import pytest

from deepl_router.router import ProviderRouter, TranslationError
from deepl_router.store import Store


def make_provider(store, name, **overrides):
    payload = {"name": name, "kind": "deeplx", "endpoint": f"https://{name}.example", "api_key": "", "priority": 1, "weight": 1, "enabled": True, "timeout_seconds": 20}
    payload.update(overrides)
    return store.create_provider(payload)


def test_quota_exceeded_provider_is_skipped_but_stays_enabled(tmp_path):
    store = Store(tmp_path / "router.db")
    router = ProviderRouter(store)
    ok = make_provider(store, "ok")
    limited = make_provider(store, "limited", kind="volcengine", api_key="ak", api_secret="sk", quota_limit=10.0)
    store.set_quota(limited["id"], {"type": "balance", "amount": 5.0, "currency": "CNY"})

    names = [provider["name"] for provider in router.candidates()]
    assert names == ["ok"]
    assert store.provider(limited["id"], reveal_key=False)["enabled"] is True
    assert ok["id"] in [provider["id"] for provider in router.candidates()]


def test_quota_recovery_restores_candidate(tmp_path):
    store = Store(tmp_path / "router.db")
    router = ProviderRouter(store)
    limited = make_provider(store, "limited", kind="volcengine", api_key="ak", api_secret="sk", quota_limit=10.0)
    store.set_quota(limited["id"], {"type": "balance", "amount": 5.0, "currency": "CNY"})
    assert router.candidates() == []
    store.set_quota(limited["id"], {"type": "balance", "amount": 50.0, "currency": "CNY"})
    assert [provider["id"] for provider in router.candidates()] == [limited["id"]]


def test_all_quota_exceeded_gives_specific_error(tmp_path):
    store = Store(tmp_path / "router.db")
    router = ProviderRouter(store)
    limited = make_provider(store, "limited", kind="volcengine", api_key="ak", api_secret="sk", quota_limit=10.0)
    store.set_quota(limited["id"], {"type": "balance", "amount": 5.0, "currency": "CNY"})
    with pytest.raises(TranslationError, match="限额"):
        router.order()


def test_no_enabled_provider_keeps_original_error(tmp_path):
    store = Store(tmp_path / "router.db")
    router = ProviderRouter(store)
    with pytest.raises(TranslationError, match="No enabled upstream route"):
        router.order()


def test_characters_quota_exceeded_is_skipped(tmp_path):
    store = Store(tmp_path / "router.db")
    router = ProviderRouter(store)
    deepl = make_provider(store, "deepl-route", kind="deepl", api_key="key:fx")
    store.set_quota(deepl["id"], {"type": "characters", "used": 500000, "limit": 500000})
    assert router.candidates() == []
