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


def extract_subtitle(filepath: str, track_index: int, suffix: str, codec: str = "ass", convert_to_srt: bool = False) -> str:
    """Extract a single subtitle track from an MKV using -c:s copy.

    Args:
        filepath: path to the MKV file
        track_index: subtitle stream index (0-based among subtitle streams)
        suffix: output suffix e.g. ".en.dialogue"
        codec: source codec from probe (subrip, ass, ssa) — determines output extension
        convert_to_srt: if True and source is ASS, convert to SRT after extraction

    Returns: path to the extracted subtitle file
    """
    # Determine output extension from source codec
    if codec in ("ass", "ssa"):
        ext = "ass"
    else:
        ext = "srt"

    fpath = Path(filepath)
    out_name = fpath.stem + suffix + "." + ext
    out_path = fpath.parent / out_name

    cmd = [
        "ffmpeg", "-y",
        "-i", str(fpath),
        "-map", f"0:s:{track_index}",
        "-c:s", "copy",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        err = result.stderr.strip()
        raise RuntimeError(f"ffmpeg failed: {err[-300:]}")

    # Convert to SRT if requested and source was ASS
    if convert_to_srt and ext == "ass":
        srt_path = out_path.with_suffix(".srt")
        convert_cmd = [
            "ffmpeg", "-y",
            "-i", str(out_path),
            "-c:s", "srt",
            str(srt_path),
        ]
        conv_result = subprocess.run(convert_cmd, capture_output=True, text=True, timeout=60)
        if conv_result.returncode == 0:
            out_path.unlink()
            return str(srt_path)

    return str(out_path)


async def run_probe(file_paths: list) -> dict:
    """Probe all selected MKVs and return track info + styles.

    Returns {filepath: [tracks]} dict. Also stores detected styles in module state.
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


async def run_extract(file_paths: list, track_index: int, suffix: str, convert_to_srt: bool = False) -> None:
    """Extract subtitle track from all selected MKVs."""
    import logger
    logger.reset_job_status()
    logger.clear_cancel()

    try:
        jlog(SEP)
        jlog(f"EXTRACT - {len(file_paths)} files, track {track_index}, suffix: '{suffix}'")

        # Determine codec from first file's probe
        codec = "ass"
        try:
            tracks = probe_file(file_paths[0])
            if track_index < len(tracks):
                codec = tracks[track_index].get("codec", "ass")
        except Exception:
            pass

        ext = "ass" if codec in ("ass", "ssa") else "srt"
        jlog(f"Source codec: {codec} -> output: .{ext}")
        if convert_to_srt and ext == "ass":
            jlog(f"Will convert to SRT after extraction")

        completed, failed = [], []
        for i, fp in enumerate(file_paths, 1):
            if is_cancelled():
                jlog(f"CANCELLED after {i - 1} files")
                break
            fpath = Path(fp)
            jlog(f"  [{i:02d}/{len(file_paths)}] {fpath.name}")
            try:
                out = extract_subtitle(fp, track_index, suffix, codec, convert_to_srt)
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


def _filter_ass_styles(filepath: str, keep_styles: list) -> dict:
    """Remove styles and dialogue lines not in keep_styles from an ASS file.
    
    Returns stats: {styles_removed, lines_removed, lines_kept}
    """
    content = Path(filepath).read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    output = []
    in_styles = False
    in_events = False
    format_fields = []
    styles_removed = 0
    lines_removed = 0
    lines_kept = 0

    for line in lines:
        lower = line.strip().lower()
        if lower.startswith("[v4"):
            in_styles = True
            in_events = False
            output.append(line)
            continue
        if lower == "[events]":
            in_styles = False
            in_events = True
            output.append(line)
            continue
        if line.startswith("["):
            in_styles = False
            in_events = False
            output.append(line)
            continue

        if in_styles:
            if line.startswith("Format:"):
                output.append(line)
            elif line.startswith("Style:"):
                name = line.split(":", 1)[1].split(",")[0].strip()
                if name in keep_styles:
                    output.append(line)
                else:
                    styles_removed += 1
                    log.info(f"    Removed style: {name}")
            else:
                output.append(line)
        elif in_events:
            if line.startswith("Format:"):
                format_fields = [f.strip().lower() for f in line.split(":", 1)[1].split(",")]
                output.append(line)
            elif line.startswith("Dialogue:"):
                raw_after = line.split(":", 1)[1]
                values = raw_after.split(",", len(format_fields) - 1)
                if "style" in format_fields:
                    style_idx = format_fields.index("style")
                    if style_idx < len(values):
                        style_name = values[style_idx].strip()
                        if style_name in keep_styles:
                            output.append(line)
                            lines_kept += 1
                        else:
                            lines_removed += 1
                    else:
                        output.append(line)
                        lines_kept += 1
                else:
                    output.append(line)
                    lines_kept += 1
            else:
                output.append(line)
        else:
            output.append(line)

    Path(filepath).write_text("\n".join(output), encoding="utf-8")
    log.info(f"    {Path(filepath).name}: kept {lines_kept} lines, removed {lines_removed} lines, removed {styles_removed} styles")
    return {"styles_removed": styles_removed, "lines_removed": lines_removed, "lines_kept": lines_kept}
