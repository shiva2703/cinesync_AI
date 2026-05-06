# app/services/timeline_service.py

def generate_timeline(clips, prompt):
    # simple logic for MVP

    reverse = "slow" in prompt.lower()

    sorted_clips = sorted(
        clips,
        key=lambda x: x["motion"],
        reverse=not reverse
    )

    timeline = []
    start = 0

    for clip in sorted_clips:
        timeline.append({
            "file": clip["file"],
            "start": 0,
            "end": 3
        })

    return timeline