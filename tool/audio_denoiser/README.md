# audio_denoiser — Facebook Denoiser (DNS) 語音去雜音

使用 [facebookresearch/denoiser](https://github.com/facebookresearch/denoiser) 的預訓練模型（預設 `dns64`）對 MP3/WAV 做語音增強，降低非人聲雜音。模型在 **16 kHz 單聲道** 上運算，輸出可依參數轉成 **44.1 kHz 單聲道 MP3（128 kbps）**，方便與一般錄音檔一致。

## 需求

- **Python 3.11**（建議；本 repo 腳本以 3.11 測試）
- **ffmpeg** 在 `PATH` 中（用於解碼/重採樣/編碼 MP3）
- 網路：首次執行會從 Meta 的 URL 下載預訓練權重（約百 MB），快取在 `~/.cache/torch/hub/checkpoints/`。若 Python 出現 TLS/憑證錯誤，腳本會自動改用系統的 **curl** 下載；仍失敗時請用瀏覽器下載 `.th` 後以 `--checkpoint` 指定本機路徑。

## 安裝

```bash
cd tool/audio_denoiser
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

若 `torch` 安裝失敗，請到 [PyTorch 官網](https://pytorch.org/get-started/locally/) 依你的 OS 選擇 CPU 版安裝指令後，再 `pip install -r requirements.txt`（或手動裝齊其餘套件）。

## 使用方式

預設：輸出檔與輸入檔**同一目錄**，檔名為 `<原名>_denoised.mp3`（44.1 kHz 單聲道、128 kbps）。

```bash
source .venv/bin/activate
python denoise.py "../../2025年8月5日Tai师父讲经·六祖坛经（8）.mp3"
```

指定輸出路徑：

```bash
python denoise.py input.mp3 -o /path/to/out.mp3
```

保留中間產生的 16 kHz WAV（除錯用）：

```bash
python denoise.py input.mp3 --keep-wav
```

### 常用參數

| 參數 | 說明 |
|------|------|
| `--model` | `dns64`（預設）、`master64`、`dns48` |
| `--bitrate` | MP3 位元率，預設 `128k` |
| `--chunk-seconds` | 分段長度（秒），預設 `30`；記憶體不足可改小 |
| `--overlap-seconds` | 段與段重疊（秒），預設 `0.5`，減少接縫 |
| `--device` | `cpu` 或 `cuda` |

## 效能說明

- 在 **CPU** 上處理約 30 分鐘語音，可能需要數分鐘到十餘分鐘，視機器而定。
- 本工具以**分段 + 重疊加總**方式推論，避免一次載入過長波形造成記憶體不足。

## 限制

- 此模型為**語音增強 / 降噪**，不是「只保留人聲」的嚴格分離器；音樂或強背景人聲可能仍會部分保留。
- 產生的 `*_denoised.mp3`、`.wav` 已列在 `.gitignore`，避免誤提交大檔。
