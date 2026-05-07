from __future__ import annotations

import asyncio


async def test_job_lifecycle(client, sample_png_bytes: bytes):
    upload_response = await client.post(
        "/api/v1/uploads",
        files=[("files", ("storyboard.png", sample_png_bytes, "image/png"))],
    )
    assert upload_response.status_code == 200
    upload_id = upload_response.json()["uploads"][0]["upload_id"]

    job_response = await client.post(
        "/api/v1/jobs/create",
        json={
            "prompt": "Create a fast 8 second product teaser with clean text overlay",
            "upload_ids": [upload_id],
        },
    )
    assert job_response.status_code == 200
    job_id = job_response.json()["job_id"]

    terminal_statuses = {"completed", "failed", "cancelled"}
    final_payload = None
    for _ in range(30):
        status_response = await client.get(f"/api/v1/jobs/{job_id}/status")
        assert status_response.status_code == 200
        final_payload = status_response.json()
        if final_payload["status"] in terminal_statuses:
            break
        await asyncio.sleep(0.2)

    assert final_payload is not None
    assert final_payload["status"] == "completed", final_payload

    output_response = await client.get(f"/api/v1/jobs/{job_id}/output")
    assert output_response.status_code == 200
    output_payload = output_response.json()
    assert output_payload["job_id"] == job_id
    assert output_payload["output_path"].endswith(".mp4")
