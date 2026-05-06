# app/services/analysis_service.py

import cv2

def analyze_clips(files):
    results = []

    for file in files:
        cap = cv2.VideoCapture(file)

        motion_score = 0
        prev_frame = None
        count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if prev_frame is not None:
                diff = cv2.absdiff(prev_frame, gray)
                motion_score += diff.mean()

            prev_frame = gray
            count += 1

        cap.release()

        avg_motion = motion_score / max(count, 1)

        results.append({
            "file": file,
            "motion": avg_motion
        })

    return results