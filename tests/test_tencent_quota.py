import asyncio

import httpx

from deepl_router.upstreams import UPSTREAMS

PROVIDER = {"id": 1, "name": "Tencent", "kind": "tencent", "endpoint": "https://tmt.tencentcloudapi.com", "api_key": "secret-id", "api_secret": "secret-key", "timeout_seconds": 20}


def test_query_quota_signs_billing_request_and_converts_cents():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["host"] = request.headers["host"]
        captured["action"] = request.headers["x-tc-action"]
        captured["version"] = request.headers["x-tc-version"]
        captured["authorization"] = request.headers["authorization"]
        return httpx.Response(200, json={"Response": {"Balance": 12345, "RequestId": "rid"}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await UPSTREAMS["tencent"].query_quota(client, PROVIDER)

    quota = asyncio.run(run())
    assert quota.type == "balance"
    assert quota.amount == 123.45  # Balance 单位为分
    assert quota.currency == "CNY"
    assert captured["host"] == "billing.tencentcloudapi.com"
    assert captured["action"] == "DescribeAccountBalance"
    assert captured["version"] == "2018-07-09"
    assert "/billing/tc3_request" in captured["authorization"]
