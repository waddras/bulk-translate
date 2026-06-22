#!/usr/bin/env python3
"""MKV subtitle extraction: probe tracks with ffprobe, extract with ffmpeg."""
import json
import subprocess
from pathlib import Path

from config import cfg
from logger import jlog, log, is_cancelled

SEP = "=" * 60


def probe_file(filepath: str) -> list:
    """Probe an MKV file and return its subtitle tracks.

    Returns list of dicts: [{index, codec, language, title}, ...]
    """
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "s",
        str(filepath),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")

    data = json.loads(result.stdout)
    tracks = []
    for i, stream in enumerate(data.get("streams", [])):
        tracks.append({
            "index": i,
            "stream_index": stream.get("index"),
            "codec": stream.get("codec_name", "unknown"),
            "language": stream.get("tags", {}).get("language", "und"),
            "title": stream.get("tags", {}).get("title", ""),
        })
    return tracks


def extract_subtitle(filepath: str, track_index: int, suffix: str) -> str:
    """Extract a single subtitle track from an MKV.

    Args:
        filepath: path to the MKV file
        track_index: subtitle stream index (0-based among subtitle streams)
        suffix: output suffix e.g. ".en.dialogue"

    Returns: path to the extracted subtitle file
    """
    ext = cfg.get("EXTRACT_FORMAT", "ass")
    fpath = Path(filepath)
    out_name = fpath.stem + suffix + "." + ext
    out_path = fpath.parent / out_name

    cmd = [
        "ffmpeg", "-y",
        "-i", str(fpath),
        "-map", f"0:s:{track_index}",
        "-c:s", "copy" if ext == "ass" else "srt",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg extraction failed: {result.stderr.strip()[:500]}")

    return str(out_path)


async def run_probe(file_paths: list) -> dict:
    """Probe all selected MKVs and return track info.

    Returns {filepath: [tracks]} dict.
    """
    import logger
    logger.reset_job_status()
    logger.clear_cancel()

    try:
        jlog(SEP)
        jlog(f"PROBE - {len(file_paths)} MKV files")

        results = {}
        for i, fp in enumerate(file_paths, 1):
            if is_cancelled():
                jlog("CANCELLED")
                break
            fpath = Path(fp)
            if not fpath.exists():
                jlog(f"  [{i:02d}] {fpath.name} - NOT FOUND")
                continue
            try:
                tracks = probe_file(fp)
                results[fp] = tracks
                jlog(f"  [{i:02d}] {fpath.name}:")
                if not tracks:
                    jlog(f"        No subtitle tracks found")
                for t in tracks:
                    title = f' "{t["title"]}"' if t["title"] else ""
                    jlog(f"        Track {t['index']}: [{t['language']}] ({t['codec']}){title}")
            except Exception as e:
                jlog(f"  [{i:02d}] {fpath.name} - ERROR: {e}")
                results[fp] = []

        jlog(SEP)
        jlog(f"PROBE COMPLETE - {len(results)} files analyzed")
        logger.set_done()
        return results

    except Exception as e:
        log.error(f"Probe FAILED: {e}")
        logger.set_error(str(e))
        logger.set_done()
        return {}
    finally:
        logger.set_running(False)


async def run_extract(file_paths: list, track_index: int, suffix: str) -> None:
    """Extract subtitle track from all selected MKVs."""
    import logger
    logger.reset_job_status()
    logger.clear_cancel()

    try:
        jlog(SEP)
        jlog(f"EXTRACT - {len(file_paths)} files, track {track_index}, suffix: '{suffix}'")
        jlog(f"Output format: {cfg.get('EXTRACT_FORMAT', 'ass')}")

        completed, failed = [], []
        for i, fp in enumerate(file_paths, 1):
            if is_cancelled():
                jlog(f"CANCELLED after {i - 1} files")
                break
            fpath = Path(fp)
            jlog(f"  [{i:02d}/{len(file_paths)}] {fpath.name}")
            try:
                out = extract_subtitle(fp, track_index, suffix)
                jlog(f"        -> {Path(out).name}")
                completed.append(Path(out).name)
            except Exception as e:
                jlog(f"        ERROR: {e}")
                failed.append(fpath.name)

        logger.set_completed(completed)
        logger.set_skipped(failed)

        jlog(SEP)
        cancelled = is_cancelled()
        if cancelled:
            logger.mark_cancelled()
        jlog(f"{'CANCELLED' if cancelled else 'EXTRACT COMPLETE'} - "
             f"{len(completed)} extracted, {len(failed)} failed")
        for f in completed:
            jlog(f"  done: {f}")
        for f in failed:
            jlog(f"  failed: {f}")

        logger.set_done()

    except Exception as e:
        log.error(f"Extract FAILED: {e}")
        logger.set_error(str(e))
        logger.set_done()
    finally:
        logger.set_running(False)
