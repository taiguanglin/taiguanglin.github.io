#!/usr/bin/env bash
# batch_clean.sh — 批次處理音訊：Facebook Denoiser 去雜音 + ffmpeg 後製濾波
#
# 流程（每個輸入檔）：
#   1. denoise.py（dns64）           → <stem>_denoised.mp3   （44.1k mono 128k；放暫存目錄）
#   2. ffmpeg highpass + acompressor + loudnorm
#                                    → <stem>_clean.mp3      （44.1k mono 64k；放輸出目錄）
#   3. 刪除暫存的 *_denoised.mp3
#
# 用法：
#   batch_clean.sh [-o OUT_DIR] [-n] FILE [FILE ...]
#   batch_clean.sh [-o OUT_DIR] [-n] -d SRC_DIR -p 'GLOB'
#
# 參數：
#   -o OUT_DIR   輸出目錄（預設：與第一個輸入檔同目錄）
#   -d SRC_DIR   來源目錄（搭配 -p 使用）
#   -p GLOB      在 SRC_DIR 下匹配的 glob（例如 '2024年2月1?日*.MP3'）
#   -n           dry-run，僅列出要處理的檔案就退出
#
# 範例：
#   ./batch_clean.sh "/Users/paul/Documents/2024答疑音频/2024年2月11日Tai师父答疑（音频版）.MP3"
#
#   ./batch_clean.sh -d "/Users/paul/Documents/2024答疑音频" \
#                    -p '2024年2月1?日Tai师父答疑（音频版）.MP3'

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="${SCRIPT_DIR}/.venv/bin/python"
DENOISE_PY="${SCRIPT_DIR}/denoise.py"

if [[ ! -x "${VENV_PY}" ]]; then
  echo "找不到虛擬環境 Python：${VENV_PY}" >&2
  echo "請先：" >&2
  echo "  cd ${SCRIPT_DIR}" >&2
  echo "  python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "找不到 ffmpeg，請先安裝。" >&2
  exit 1
fi

OUT_DIR=""
SRC_DIR=""
GLOB_PATTERN=""
DRY_RUN=0

while getopts ":o:d:p:n" opt; do
  case "${opt}" in
    o) OUT_DIR="${OPTARG}" ;;
    d) SRC_DIR="${OPTARG}" ;;
    p) GLOB_PATTERN="${OPTARG}" ;;
    n) DRY_RUN=1 ;;
    *) echo "未知參數：-${OPTARG}" >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

# 收集輸入檔
INPUTS=()
if [[ -n "${SRC_DIR}" || -n "${GLOB_PATTERN}" ]]; then
  if [[ -z "${SRC_DIR}" || -z "${GLOB_PATTERN}" ]]; then
    echo "-d 與 -p 必須一起使用。" >&2
    exit 2
  fi
  if [[ ! -d "${SRC_DIR}" ]]; then
    echo "找不到來源目錄：${SRC_DIR}" >&2
    exit 1
  fi
  shopt -s nullglob
  pushd "${SRC_DIR}" >/dev/null
  for f in ${GLOB_PATTERN}; do
    INPUTS+=("${SRC_DIR%/}/${f}")
  done
  popd >/dev/null
  shopt -u nullglob
fi

while [[ $# -gt 0 ]]; do
  INPUTS+=("$1")
  shift
done

if [[ ${#INPUTS[@]} -eq 0 ]]; then
  echo "沒有任何輸入檔。" >&2
  echo "請傳入檔案路徑，或使用 -d SRC_DIR -p 'GLOB'。" >&2
  exit 2
fi

# 預設輸出目錄＝第一個輸入檔的目錄
if [[ -z "${OUT_DIR}" ]]; then
  OUT_DIR="$(dirname "${INPUTS[0]}")"
fi
mkdir -p "${OUT_DIR}"

echo "== 將處理 ${#INPUTS[@]} 個檔案 =="
for f in "${INPUTS[@]}"; do
  echo "  - ${f}"
done
echo "輸出目錄：${OUT_DIR}"
echo

if [[ ${DRY_RUN} -eq 1 ]]; then
  exit 0
fi

# 暫存目錄（denoise.py 的中間 mp3 放這裡，跑完即刪）
TMP_DIR="$(mktemp -d -t audio_clean_XXXXXX)"
cleanup() { rm -rf "${TMP_DIR}"; }
trap cleanup EXIT

ok=0
fail=0
failed_files=()

idx=0
total=${#INPUTS[@]}
for src in "${INPUTS[@]}"; do
  idx=$((idx + 1))
  if [[ ! -f "${src}" ]]; then
    echo "[${idx}/${total}] 找不到檔案，跳過：${src}" >&2
    fail=$((fail + 1))
    failed_files+=("${src}")
    continue
  fi

  stem="$(basename "${src}")"
  stem="${stem%.*}"

  denoised="${TMP_DIR}/${stem}_denoised.mp3"
  cleaned="${OUT_DIR%/}/${stem}_clean.mp3"

  echo "============================================================"
  echo "[${idx}/${total}] ${src}"
  echo "  -> denoise: ${denoised}"
  echo "  -> clean  : ${cleaned}"
  echo "============================================================"

  start_ts=$(date +%s)

  # Step 1: Facebook Denoiser
  if ! "${VENV_PY}" "${DENOISE_PY}" "${src}" -o "${denoised}"; then
    echo "denoise.py 失敗：${src}" >&2
    fail=$((fail + 1))
    failed_files+=("${src}")
    continue
  fi

# Step 2: ffmpeg 頻段過濾 + 噪音閘門 + 動態壓縮 + 靜態放大 + 限制器防爆音
  if ! ffmpeg -hide_banner -loglevel error -y \
        -i "${denoised}" \
        -filter:a "highpass=f=80,lowpass=f=12000,agate=threshold=-45dB:attack=10:release=100,acompressor=threshold=-28dB:ratio=4:attack=20:release=120,volume=12dB,alimiter=limit=-1.0dB" \
        -c:a libmp3lame \
        -b:a 64k \
        -ac 1 \
        -ar 44100 \
        "${cleaned}"; then
    echo "ffmpeg 失敗：${denoised}" >&2
    fail=$((fail + 1))
    failed_files+=("${src}")
    rm -f "${denoised}"
    continue
  fi

  rm -f "${denoised}"

  end_ts=$(date +%s)
  elapsed=$((end_ts - start_ts))
  echo "[${idx}/${total}] 完成（${elapsed}s）：${cleaned}"
  ok=$((ok + 1))
done

echo
echo "== 全部完成 =="
echo "  成功：${ok} / ${total}"
echo "  失敗：${fail}"
if [[ ${fail} -gt 0 ]]; then
  for f in "${failed_files[@]}"; do
    echo "    - ${f}"
  done
  exit 1
fi
