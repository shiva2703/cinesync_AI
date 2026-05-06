# app/services/render_service.py
import os
import subprocess

OUTPUT_PATH = "data/outputs/output.mp4"

def render_video(timeline):
    temp_files = []

    for i, clip in enumerate(timeline):
        out = f"data/processed/clip_{i}.mp4"

        cmd = [
            "ffmpeg",
            "-i", clip["file"],
            "-ss", str(clip["start"]),
            "-to", str(clip["end"]),
            "-c", "copy",
            out
        ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        temp_files.append(out)

    # Create concat list
    with open("concat.txt", "w") as f:
        for file in temp_files:
            f.write(f"file '{file}'\n")

    cmd_concat = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", "concat.txt",
        "-c", "copy",
        OUTPUT_PATH
    ]

    subprocess.run(cmd_concat)

    return OUTPUT_PATH