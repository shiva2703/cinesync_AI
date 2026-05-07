from __future__ import annotations


async def test_upload_endpoint_accepts_image(client, sample_png_bytes: bytes):
    response = await client.post(
        "/api/v1/uploads",
        files=[("files", ("poster.png", sample_png_bytes, "image/png"))],
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["uploads"]) == 1
    upload = payload["uploads"][0]
    assert upload["filename"] == "poster.png"
    assert upload["asset_type"] == "image"
