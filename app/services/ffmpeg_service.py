from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from time import perf_counter
from typing import Any

import structlog
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_fixed

from app.config.settings import Settings
from app.core.exceptions import FFmpegExecutionError


class FFmpegService:
    """Safe async wrapper around ffmpeg and ffprobe."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = structlog.get_logger(__name__)

    async def is_available(self) -> bool:
        binary = shutil.which(self.settings.ffmpeg_binary) or (
            self.settings.ffmpeg_binary if Path(self.settings.ffmpeg_binary).exists() else None
        )
        probe = shutil.which(self.settings.ffprobe_binary) or (
            self.settings.ffprobe_binary if Path(self.settings.ffprobe_binary).exists() else None
        )
        return bool(binary and probe)

    async def get_version(self) -> str | None:
        if not await self.is_available():
            return None
        completed = await self._run_command(
            [self.settings.ffmpeg_binary, "-version"],
            timeout=15,
            retries=1,
        )
        return completed["stdout"].splitlines()[0] if completed["stdout"] else None

    async def extract_metadata(self, input_path: Path) -> dict[str, Any]:
        result = await self._run_command(
            [
                self.settings.ffprobe_binary,
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-print_format",
                "json",
                str(input_path),
            ],
            timeout=30,
            retries=self.settings.ffmpeg_retry_attempts,
        )
        try:
            return json.loads(result["stdout"] or "{}")
        except json.JSONDecodeError as exc:
            raise FFmpegExecutionError(
                message="ffprobe returned invalid JSON",
                error_code="ffprobe_invalid_json",
            ) from exc

    async def trim_clip(self, input_path: Path, output_path: Path, start: float, end: float) -> Path:
        duration = max(end - start, 0.1)
        await self._run_command(
            [
                self.settings.ffmpeg_binary,
                "-y",
                "-ss",
                str(start),
                "-i",
                str(input_path),
                "-t",
                str(duration),
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                str(output_path),
            ],
            timeout=self.settings.ffmpeg_timeout_seconds,
            retries=self.settings.ffmpeg_retry_attempts,
        )
        return output_path

    async def concat_clips(self, input_files: list[Path], output_path: Path) -> Path:
        concat_file = output_path.parent / "concat.txt"
        concat_file.write_text(
            "\n".join(f"file '{path.as_posix()}'" for path in input_files),
            encoding="utf-8",
        )
        await self._run_command(
            [
                self.settings.ffmpeg_binary,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(output_path),
            ],
            timeout=self.settings.ffmpeg_timeout_seconds,
            retries=self.settings.ffmpeg_retry_attempts,
        )
        return output_path

    async def add_transition(self, first_input: Path, second_input: Path, output_path: Path, duration: float = 0.5) -> Path:
        await self._run_command(
            [
                self.settings.ffmpeg_binary,
                "-y",
                "-i",
                str(first_input),
                "-i",
                str(second_input),
                "-filter_complex",
                f"[0:v][1:v]xfade=transition=fade:duration={duration}:offset=0[v]",
                "-map",
                "[v]",
                "-c:v",
                "libx264",
                str(output_path),
            ],
            timeout=self.settings.ffmpeg_timeout_seconds,
            retries=self.settings.ffmpeg_retry_attempts,
        )
        return output_path

    async def overlay_text(self, input_path: Path, output_path: Path, text: str) -> Path:
        escaped = text.replace(":", r"\:").replace("'", r"\'")
        await self._run_command(
            [
                self.settings.ffmpeg_binary,
                "-y",
                "-i",
                str(input_path),
                "-vf",
                f"drawtext=text='{escaped}':fontcolor=white:fontsize=42:x=(w-text_w)/2:y=h-200:box=1:boxcolor=black@0.4",
                "-codec:a",
                "copy",
                str(output_path),
            ],
            timeout=self.settings.ffmpeg_timeout_seconds,
            retries=self.settings.ffmpeg_retry_attempts,
        )
        return output_path

    async def resize_for_vertical(self, input_path: Path, output_path: Path) -> Path:
        await self._run_command(
            [
                self.settings.ffmpeg_binary,
                "-y",
                "-i",
                str(input_path),
                "-vf",
                "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                str(output_path),
            ],
            timeout=self.settings.ffmpeg_timeout_seconds,
            retries=self.settings.ffmpeg_retry_attempts,
        )
        return output_path

    async def mux_audio(self, input_video: Path, input_audio: Path, output_path: Path, duration: float) -> Path:
        await self._run_command(
            [
                self.settings.ffmpeg_binary,
                "-y",
                "-i",
                str(input_video),
                "-i",
                str(input_audio),
                "-t",
                str(duration),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                str(output_path),
            ],
            timeout=self.settings.ffmpeg_timeout_seconds,
            retries=self.settings.ffmpeg_retry_attempts,
        )
        return output_path

    async def _run_command(self, args: list[str], timeout: int, retries: int) -> dict[str, Any]:
        if not args or not all(isinstance(arg, str) and arg for arg in args):
            raise FFmpegExecutionError("Invalid FFmpeg command arguments", error_code="invalid_ffmpeg_command")

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(retries),
            wait=wait_fixed(1),
            retry=retry_if_exception_type(FFmpegExecutionError),
            reraise=True,
        ):
            with attempt:
                start = perf_counter()
                self.logger.info("ffmpeg_command_started", command=args)
                try:
                    process = await asyncio.create_subprocess_exec(
                        *args,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                except asyncio.TimeoutError as exc:
                    raise FFmpegExecutionError(
                        message="FFmpeg command timed out",
                        error_code="ffmpeg_timeout",
                        details={"command": args, "timeout": timeout},
                    ) from exc
                except FileNotFoundError as exc:
                    raise FFmpegExecutionError(
                        message="FFmpeg binary not found",
                        error_code="ffmpeg_missing",
                        details={"command": args},
                    ) from exc

                elapsed_ms = round((perf_counter() - start) * 1000, 2)
                stdout_text = stdout.decode("utf-8", errors="ignore")
                stderr_text = stderr.decode("utf-8", errors="ignore")

                self.logger.info(
                    "ffmpeg_command_completed",
                    command=args,
                    elapsed_ms=elapsed_ms,
                    return_code=process.returncode,
                )

                if process.returncode != 0:
                    raise FFmpegExecutionError(
                        message="FFmpeg command failed",
                        error_code="ffmpeg_non_zero_exit",
                        details={
                            "command": args,
                            "stdout": stdout_text[-4000:],
                            "stderr": stderr_text[-4000:],
                            "return_code": process.returncode,
                        },
                    )

                return {
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                    "return_code": process.returncode,
                    "elapsed_ms": elapsed_ms,
                }

        raise FFmpegExecutionError("FFmpeg command failed after retries", error_code="ffmpeg_retry_exhausted")
