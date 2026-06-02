#!/usr/bin/env python3
"""
CLI: decode audio with ffmpeg -> 16 kHz mono WAV -> Facebook Denoiser -> MP3 (or keep WAV).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Help torch.hub / urllib download checkpoints on macOS or locked-down CA stores.
try:
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

import numpy as np
import soundfile as sf
import torch
from tqdm import tqdm

from denoiser.pretrained import dns48, dns64, master64

SR_MODEL = 16_000
MODEL_LOADERS = {
    "dns64": dns64,
    "dns48": dns48,
    "master64": master64,
}


def die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def require_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        die("找不到 ffmpeg。請先安裝 ffmpeg 並加入 PATH。")
    return exe


def download_url_with_curl(url: str, dest: Path) -> None:
    """Save URL to dest using curl (works when Python's TLS store is broken)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    curl = shutil.which("curl")
    if not curl:
        die("無法下載權重：Python SSL 失敗且找不到 curl。請手動下載後使用 --checkpoint。")
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        subprocess.run(
            [curl, "-fsSL", "-o", str(tmp), url],
            check=True,
            capture_output=True,
            text=True,
        )
        tmp.replace(dest)
    except subprocess.CalledProcessError as e:
        err = (e.stderr or "").strip()
        die(f"curl 下載失敗：{url}\n{err}")


def load_state_dict_from_url_or_curl(url: str, map_location) -> dict:
    """Like torch.hub.load_state_dict_from_url but falls back to curl on SSL errors."""
    hub_dir = Path(torch.hub.get_dir()) / "checkpoints"
    hub_dir.mkdir(parents=True, exist_ok=True)
    filename = url.rsplit("/", 1)[-1]
    cached = hub_dir / filename
    if cached.is_file():
        return torch.load(cached, map_location=map_location)
    try:
        return torch.hub.load_state_dict_from_url(
            url,
            map_location=map_location,
            model_dir=str(hub_dir),
            file_name=filename,
        )
    except Exception as e:
        err = str(e).lower()
        if "certificate" not in err and "ssl" not in err:
            die(f"無法下載權重：{e}")
        print("Python TLS 驗證失敗，改用 curl 下載權重…", file=sys.stderr)
        download_url_with_curl(url, cached)
        return torch.load(cached, map_location=map_location)


def ffmpeg_run(ffmpeg: str, args: list[str]) -> None:
    # -stats 強制顯示進度（frame=/time=/speed=）即使 -loglevel error
    # stderr 直接傳到終端機讓使用者看到進度；stdout 丟掉（ffmpeg 沒寫到 stdout）
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-stats", "-y", *args]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=None)
    except FileNotFoundError:
        die(f"無法執行 ffmpeg：{ffmpeg}")
    except subprocess.CalledProcessError as e:
        die(f"ffmpeg 失敗（exit {e.returncode}）；錯誤訊息見上方 ffmpeg 輸出。")


def decode_to_16k_mono_wav(ffmpeg: str, src: Path, dst_wav: Path) -> None:
    ffmpeg_run(
        ffmpeg,
        [
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            str(SR_MODEL),
            "-f",
            "wav",
            str(dst_wav),
        ],
    )


def encode_wav_to_mp3(ffmpeg: str, src_wav: Path, dst_mp3: Path, bitrate: str) -> None:
    ffmpeg_run(
        ffmpeg,
        [
            "-i",
            str(src_wav),
            "-ar",
            "44100",
            "-ac",
            "1",
            "-c:a",
            "libmp3lame",
            "-b:a",
            bitrate,
            str(dst_mp3),
        ],
    )


def segment_weights(length: int, overlap: int, is_first: bool, is_last: bool) -> np.ndarray:
    """Linear ramps in overlap zones for simple crossfade (overlap-add)."""
    w = np.ones(length, dtype=np.float64)
    if overlap <= 0:
        return w.astype(np.float32)
    o = min(overlap, length)
    if not is_first:
        ramp = np.linspace(0.0, 1.0, o, endpoint=False, dtype=np.float64)
        w[:o] *= ramp
    if not is_last:
        ramp = np.linspace(1.0, 0.0, o, endpoint=False, dtype=np.float64)
        w[-o:] *= ramp
    return w.astype(np.float32)


def denoise_chunks(
    model: torch.nn.Module,
    wav: np.ndarray,
    device: torch.device,
    chunk_samples: int,
    overlap_samples: int,
) -> np.ndarray:
    if wav.ndim != 1:
        die(f"預期單聲道一維陣列，得到 shape={wav.shape}")
    n = int(wav.shape[0])
    if n == 0:
        die("音訊長度為 0")

    hop = max(chunk_samples - overlap_samples, 1)
    out = np.zeros(n, dtype=np.float32)
    wsum = np.zeros(n, dtype=np.float32)

    starts = list(range(0, n, hop))
    # Ensure last segment reaches end
    if starts[-1] + chunk_samples < n:
        starts.append(max(0, n - chunk_samples))
    starts = sorted(set(starts))

    model.eval()
    with torch.no_grad():
        for i, start in enumerate(
            tqdm(starts, desc="Denoising", unit="chunk", dynamic_ncols=True)
        ):
            end = min(start + chunk_samples, n)
            seg = wav[start:end]
            pad = chunk_samples - seg.shape[0]
            if pad > 0:
                seg = np.pad(seg.astype(np.float32), (0, pad), mode="constant")
            is_first = start == 0
            is_last = end >= n
            win = segment_weights(seg.shape[0], overlap_samples, is_first, is_last)

            t = torch.from_numpy(seg).float().to(device).unsqueeze(0).unsqueeze(0)
            enhanced = model(t)[0, 0].detach().cpu().numpy().astype(np.float32)
            enhanced = enhanced[: end - start]
            win = win[: enhanced.shape[0]]

            out[start:end] += enhanced * win
            wsum[start:end] += win

    wsum = np.maximum(wsum, 1e-8)
    return (out / wsum).astype(np.float32)


def default_output_mp3(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_denoised.mp3")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="以 Facebook Denoiser 對 MP3/WAV 去雜音，輸出 MP3（預設 44.1k mono 128k）。"
    )
    p.add_argument("input", type=Path, help="輸入音訊（mp3 / wav 等 ffmpeg 可讀格式）")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="輸出 MP3 路徑（預設：與輸入同目錄，檔名 <stem>_denoised.mp3）",
    )
    p.add_argument(
        "--model",
        choices=list(MODEL_LOADERS.keys()),
        default="dns64",
        help="預訓練模型（預設 dns64）",
    )
    p.add_argument(
        "--bitrate",
        default="128k",
        help="輸出 MP3 位元率（預設 128k）",
    )
    p.add_argument(
        "--chunk-seconds",
        type=float,
        default=30.0,
        help="每段長度（秒），預設 30",
    )
    p.add_argument(
        "--overlap-seconds",
        type=float,
        default=0.5,
        help="段與段重疊（秒），預設 0.5",
    )
    p.add_argument(
        "--device",
        default="cpu",
        help="torch device，例如 cpu 或 cuda",
    )
    p.add_argument(
        "--keep-wav",
        action="store_true",
        help="保留 16 kHz 去雜音後的 WAV（與輸出 MP3 同目錄，副檔名 _denoised_16k.wav）",
    )
    p.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="本機權重檔 .th（略過網路下載）。對應 dns64："
        " https://dl.fbaipublicfiles.com/adiyoss/denoiser/dns64-a7761ff99a7d5bb6.th",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    src = args.input.expanduser().resolve()
    if not src.is_file():
        die(f"找不到輸入檔：{src}")

    out_mp3 = (args.output or default_output_mp3(src)).expanduser().resolve()
    out_mp3.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = require_ffmpeg()

    chunk_samples = max(int(args.chunk_seconds * SR_MODEL), SR_MODEL // 4)
    overlap_samples = max(int(args.overlap_seconds * SR_MODEL), 0)
    if overlap_samples >= chunk_samples:
        die("--overlap-seconds 必須小於 --chunk-seconds")

    device = torch.device(args.device)
    try:
        loader = MODEL_LOADERS[args.model]
        print(f"載入模型 {args.model}…", file=sys.stderr)
        model = loader(pretrained=False).to(device)
        if args.checkpoint:
            ckpt = args.checkpoint.expanduser().resolve()
            if not ckpt.is_file():
                die(f"找不到 --checkpoint 檔案：{ckpt}")
            state = torch.load(ckpt, map_location=device)
            model.load_state_dict(state)
        else:
            # Use torch.hub download (needs working TLS / CA bundle).
            from denoiser import pretrained as _pre

            urls = {
                "dns64": _pre.DNS_64_URL,
                "dns48": _pre.DNS_48_URL,
                "master64": _pre.MASTER_64_URL,
            }
            url = urls[args.model]
            print(f"下載權重：{url}", file=sys.stderr)
            state = load_state_dict_from_url_or_curl(url, map_location=device)
            model.load_state_dict(state)
    except Exception as e:
        die(f"無法載入模型：{e}")

    tmpdir = tempfile.mkdtemp(prefix="audio_denoiser_")
    tmp_path = Path(tmpdir)
    in_16k = tmp_path / "input_16k.wav"
    out_16k = tmp_path / "output_16k.wav"

    try:
        print("ffmpeg：解碼為 16 kHz 單聲道 WAV…", file=sys.stderr)
        decode_to_16k_mono_wav(ffmpeg, src, in_16k)

        wav, sr = sf.read(in_16k, dtype="float32", always_2d=False)
        if sr != SR_MODEL:
            die(f"內部 WAV 取樣率應為 {SR_MODEL}，實際為 {sr}")
        if wav.ndim > 1:
            wav = wav.mean(axis=1).astype(np.float32)

        # Clip to reasonable range before model (soundfile usually [-1,1])
        wav = np.clip(wav, -1.0, 1.0).astype(np.float32)

        if device.type == "cpu":
            torch.set_num_threads(max(1, torch.get_num_threads()))

        denoised = denoise_chunks(
            model, wav, device, chunk_samples, overlap_samples
        )
        denoised = np.clip(denoised, -1.0, 1.0)

        sf.write(out_16k, denoised, SR_MODEL, subtype="PCM_16")

        print("ffmpeg：編碼為 MP3（44.1 kHz 單聲道）…", file=sys.stderr)
        encode_wav_to_mp3(ffmpeg, out_16k, out_mp3, args.bitrate)

        if args.keep_wav:
            keep = out_mp3.with_name(f"{out_mp3.stem}_16k.wav")
            shutil.copy2(out_16k, keep)
            print(f"已保留 16 kHz WAV：{keep}", file=sys.stderr)

        print(f"完成：{out_mp3}", file=sys.stderr)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
