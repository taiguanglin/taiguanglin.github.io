#!/usr/bin/env bash
# batch_create.sh — 把當前資料夾下所有 .mp3 檔案配上 animation.mp4 做成影片
# 用法：cd 到包含 .mp3 的資料夾後直接執行
#   ~/taiguanglin.github.io/tool/video_creator/batch_create.sh
#
# 所需檔案：
#   - <此腳本所在目錄>/animation.mp4   作為循環播放的視訊
# 輸出：
#   - ./output_mp4/<原檔名>.mp4

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANIMATION="${SCRIPT_DIR}/animation.mp4"

if [[ ! -f "${ANIMATION}" ]]; then
  echo "找不到視訊來源：${ANIMATION}" >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "找不到 ffmpeg，請先安裝。" >&2
  exit 1
fi

mkdir -p output_mp4

shopt -s nullglob nocaseglob
mp3_files=( *.mp3 )
shopt -u nocaseglob

if [[ ${#mp3_files[@]} -eq 0 ]]; then
  echo "目前資料夾找不到任何 .mp3 檔。" >&2
  exit 1
fi

total=${#mp3_files[@]}
idx=0
for f in "${mp3_files[@]}"; do
  idx=$((idx + 1))
  out="output_mp4/${f%.*}.mp4"
  echo "[${idx}/${total}] 正在處理：${f} -> ${out}"
  ffmpeg -hide_banner -loglevel error -stats -y \
    -stream_loop -1 -i "${ANIMATION}" \
    -i "${f}" \
    -map 0:v:0 -map 1:a:0 \
    -c:v libx264 -c:a aac -b:a 192k \
    -pix_fmt yuv420p -shortest \
    "${out}"
done

echo "全部轉換完成！輸出於：$(pwd)/output_mp4/"
