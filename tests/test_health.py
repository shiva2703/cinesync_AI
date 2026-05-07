from __future__ import annotations


async def test_healthcheck(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert "ffmpeg" in payload
    assert "disk" in payload
    assert "temp_storage" in payload
