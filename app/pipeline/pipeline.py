# app/pipeline/pipeline.py

from app.services.analysis_service import analyze_clips
from app.services.timeline_service import generate_timeline
from app.services.render_service import render_video


def run_pipeline(files, prompt):
    print("Step 1: Analyzing clips...")
    analyzed_data = analyze_clips(files)

    print("Step 2: Generating timeline...")
    timeline = generate_timeline(analyzed_data, prompt)

    print("Step 3: Rendering video...")
    output = render_video(timeline)

    return output