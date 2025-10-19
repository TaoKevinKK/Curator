import subprocess
import json
import tempfile
import os
import numpy as np
import av
from pathlib import Path

class VideoFFmpegPyavComparator:
    """Comparator for FFmpeg and PyAV."""

    def __init__(self, ffmpeg_file: str, pyav_file: str):
        self._ffmpeg_file = ffmpeg_file
        self._pyav_file = pyav_file

    def _ffprobe_info(self, video_path: str) -> dict:
        inp = None
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
        ]

        real_video_path = Path(video_path)
        if not real_video_path.exists():
            error_msg = f"Video file {real_video_path.as_posix()} not found!"
            raise FileNotFoundError(error_msg)

        cmd.append(real_video_path.as_posix())
        result = subprocess.run(cmd, input=inp, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)  # noqa: UP022, S603
        video_info = json.loads(result.stdout)

        video_stream, audio_codec = None, None
        for stream in video_info["streams"]:
            if stream["codec_type"] == "video":
                video_stream = stream
            elif stream["codec_type"] == "audio":
                audio_codec = stream["codec_name"]
        if not video_stream:
            error_msg = "No video stream found!"
            raise ValueError(error_msg)

        # Convert avg_frame_rate to float
        num, denom = map(int, video_stream["avg_frame_rate"].split("/"))
        fps = num / denom

        # not all formats store duration at stream level, so fallback to format container
        if "duration" in video_stream:
            video_duration = float(video_stream["duration"])
        elif "format" in video_info and "duration" in video_info["format"]:
            video_duration = float(video_info["format"]["duration"])
        else:
            error_msg = "Could not find `duration` in video metadata."
            raise KeyError(error_msg)
        num_frames = int(video_duration * fps)

        # store bit_rate if available
        bit_rate_k = 2000  # default to 2000K (2M) bit rate
        if "bit_rate" in video_stream:
            bit_rate_k = int(int(video_stream["bit_rate"]) / 1024)

        return {
            "height": video_stream["height"],
            "width": video_stream["width"],
            "fps": fps,
            "num_frames": num_frames,
            "video_codec": video_stream["codec_name"],
            "pixel_format": video_stream["pix_fmt"],
            "audio_codec": audio_codec,
            "video_duration": video_duration,
            "bit_rate_k": bit_rate_k,
        }

    def compare_metadata(self) -> bool:
        """Compare metadata between FFmpeg and PyAV."""
        ffmpeg_metadata = self._ffprobe_info(self._ffmpeg_file)
        pyav_metadata = self._ffprobe_info(self._pyav_file)
        for key in ffmpeg_metadata:
            if ffmpeg_metadata[key] != pyav_metadata[key]:
                return False
        return True
        