# Copyright (c) 2025, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
import math
import numpy as np
import time
from dataclasses import dataclass
from tkinter import NO

from loguru import logger

from nemo_curator.backends.base import WorkerMetadata
from nemo_curator.stages.base import ProcessingStage
from nemo_curator.stages.resources import Resources
from nemo_curator.tasks.video import Video, VideoTask, ClipTask, Clip
from nemo_curator.utils.decoder_utils import (
    FrameExtractionPolicy,
    FrameExtractionSignature,
    FramePurpose,
    extract_frames,
    decode_video_cpu,
    with_preserved_stream_position,
    read_video_stream,
    extract_frames_with_clip_span,
    extract_frames_with_clip_span_generator,
    get_video_timestamps,
)


@dataclass
class ClipFrameExtractionV1Stage(ProcessingStage[ClipTask, ClipTask]):
    """Stage for extracting frames from video clips.

    This class processes video clips through a series of steps including frame extraction,
    target frame rate selection, and frame extraction signature creation.
    """

    extraction_policies: tuple[FrameExtractionPolicy, ...] = (FrameExtractionPolicy.sequence,)
    extract_purposes: list[FramePurpose] | None = None
    target_res: tuple[int, int] | None = None
    verbose: bool = True
    num_cpus: int = 3
    target_fps: list[float | int] | None = None
    _name: str = "clip_frame_extraction"

    def __post_init__(self) -> None:
        self._resources = Resources(cpus=self.num_cpus)

    def inputs(self) -> tuple[list[str], list[str]]:
        return ["data"], []

    def outputs(self) -> tuple[list[str], list[str]]:
        return ["data"], ["clips.extracted_frames"]

    def setup(self, worker_metadata: WorkerMetadata | None = None) -> None:  # noqa: ARG002
        if self.target_fps is None:
            if self.extract_purposes is not None:
                self.target_fps = [purpose.value for purpose in self.extract_purposes]
            else:
                self.target_fps = [2]  # default fallback

        if self.target_res is None:
            self.target_res = (-1, -1)
        logger.info(f"ClipFrameExtractionStage will extract frames at {self.target_fps} FPS")

    def process(self, task: ClipTask) -> ClipTask:
        t2 = time.time()
        video_clip: Clip = task.data
        fps = []
        source_video = video_clip.source_video
        start_s, end_s = video_clip.span
        clip_uuid = video_clip.uuid
        try:
            frame_generator = extract_frames_with_clip_span_generator(
                source_video,
                (start_s, end_s),
            )
            _count = 0
            _bytes_size = 0
            for i, frame in enumerate(frame_generator):
                _count += 1
                _bytes_size += frame.nbytes
        except (ValueError, OSError, RuntimeError) as e:
            logger.exception(f"Error extracting frames for clip {clip_uuid}: {e}")
            video_clip.errors["frame_extraction"] = "video_decode_failed"
            # reset the buffer to disable further operations on this clip
            video_clip.buffer = None
        if self.verbose:
            logger.info(f"Extracting video {source_video} frames num is {_count} from clip {video_clip.uuid} at {fps} fps, bytes size: {_bytes_size}")
        return task