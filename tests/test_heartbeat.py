import httpx

from ko_monitor.heartbeat import Heartbeat

URL = "https://hc-ping.com/1234-abcd"


def client_recording(requests, status=200):
    def handler(request: httpx.Request):
        requests.append(request)
        return httpx.Response(status)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_disabled_without_url():
    requests = []
    hb = Heartbeat("", "key", client_recording(requests))
    assert not hb.enabled
    assert hb.ping() is False and hb.pause() is False
    assert requests == []


def test_ping():
    requests = []
    assert Heartbeat(URL, "", client_recording(requests)).ping() is True
    assert (requests[0].method, str(requests[0].url)) == ("GET", URL)


def test_ping_failure_is_reported_not_raised():
    assert Heartbeat(URL, "", client_recording([], status=500)).ping() is False


def test_pause_uses_management_api():
    requests = []
    assert Heartbeat(URL, "secret", client_recording(requests)).pause() is True
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://healthchecks.io/api/v3/checks/1234-abcd/pause"
    assert request.headers["X-Api-Key"] == "secret"


def test_pause_needs_api_key():
    requests = []
    assert Heartbeat(URL, "", client_recording(requests)).pause() is False
    assert requests == []
