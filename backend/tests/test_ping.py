from fastapi.testclient import TestClient


# suuuper simple test to make sure that the endpoint is actually working
def test_ping(test_client: TestClient):
    resp = test_client.get("/ping")

    assert resp.status_code == 200
