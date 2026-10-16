"""
Victoria - Multimodal Vision & Video Analysis Tools
Enables Victoria to visually analyze any image, video file, or the live screen,
explaining what's happening, answering questions, reading text/code, and summarizing videos.
"""

from victoria.brain.multimodal import get_multimodal_engine


def analyze_image(image_path: str, question: str = "") -> str:
    """
    Visually analyze an image file (PNG, JPG, WEBP, BMP, GIF, SVG, screenshot, diagram).
    Explains what is in the image, reads any text/code/UI elements, and answers specific questions.

    Args:
        image_path: File path to the image to analyze
        question: Specific question or instructions about the image (optional)
    """
    engine = get_multimodal_engine()
    res = engine.analyze_image(image_path=image_path, question=question)
    return res.get("speech") or res.get("analysis", "विश्लेषण पूरा नहीं हो सका।")


def analyze_video(video_path: str, question: str = "", max_frames: int = 6) -> str:
    """
    Visually analyze a video file (MP4, MKV, AVI, WEBM, MOV, screen recording).
    Extracts chronological keyframes, generates a labeled visual montage,
    and provides a scene-by-scene breakdown of actions, timeline, objects, and narrative.

    Args:
        video_path: File path to the video to analyze
        question: Specific question or area to focus on in the video (optional)
        max_frames: Number of keyframes to sample (default: 6, range: 4-12)
    """
    engine = get_multimodal_engine()
    res = engine.analyze_video(video_path=video_path, question=question, sample_frames_count=max_frames)
    return res.get("speech") or res.get("analysis", "वीडियो विश्लेषण पूरा नहीं हो सका।")


def analyze_current_screen(question: str = "") -> str:
    """
    Take an instant live screenshot of Hariom's desktop screen and analyze what is visible.
    Explains open apps, active windows, code, error messages, or terminal outputs.

    Args:
        question: Specific question about what's currently on screen (optional)
    """
    engine = get_multimodal_engine()
    res = engine.analyze_screen(question=question)
    return res.get("speech") or res.get("analysis", "स्क्रीन विश्लेषण पूरा नहीं हो सका।")
