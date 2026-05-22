# sense_voice — FunASR 中文語音辨識（Paraformer-zh + VAD + 標點 → SRT/TXT）

使用阿里巴巴 [FunASR](https://github.com/modelscope/FunASR)（[SenseVoice](https://github.com/FunAudioLLM/SenseVoice) 的同家族）的 **Paraformer-zh** + **fsmn-vad** + **ct-punc** 模型，將中文人聲錄音（mp3/wav/m4a 等）轉成：

- `.srt` — 含時間戳的字幕檔（可直接拖進播放器、影音剪輯軟體）
- `.txt` — 純文字逐字稿（含標點符號）

> 為什麼不直接用 SenseVoiceSmall？SenseVoice-Small 雖然支援多語言、推論快，但目前在 FunASR 中**不輸出可靠的 sentence-level timestamp**，難以產生時間軸對齊的字幕檔。Paraformer-zh + VAD + ct-punc 是 FunASR 官方推薦的「中文長語音 → SRT」管線，能拿到逐字 timestamp 與句子邊界。

支援的工具：

| 檔案 | 用途 |
|------|------|
| `transcribe.py` | 單檔辨識 → `.srt` + `.txt` |
| `batch_transcribe.py` | 目錄批次辨識，模型只載入一次，自動跳過已完成的檔案 |

## 需求

- **Python 3.10–3.12**（建議 3.11；本工具以 3.11 測試）
- **ffmpeg** 在 `PATH` 中（FunASR 用它解碼 mp3/m4a）
- 網路：首次執行會自動從 ModelScope 下載模型，快取在 `~/.cache/modelscope/hub/`
  - `paraformer-zh`（即 `iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch`）約 944 MB
  - `fsmn-vad` 約 1.5 MB
  - `ct-punc`（預設使用 Chinese-only 的 `iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch`）約 280 MB
  - 合計約 **1.2 GB**

> 如果你的網路會做 TLS MITM（公司代理 / VPN），本工具已加入 `truststore`，會自動讀取系統鑰匙圈的 CA。

## 安裝

```bash
cd tool/sense_voice
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install --prefer-binary -r requirements.txt
```

若在 Intel macOS 上看到 `Failed building wheel for llvmlite`，請先強制使用預編譯 wheel 再裝其餘套件：

```bash
pip install --only-binary=llvmlite,numba "llvmlite>=0.43" "numba>=0.60"
pip install --prefer-binary -r requirements.txt
```

若 `torch` 安裝失敗，可到 [PyTorch 官網](https://pytorch.org/get-started/locally/) 依你的 OS 選 CPU 版指令安裝後，再 `pip install --prefer-binary -r requirements.txt`。

## 使用方式

### 單檔辨識

預設：輸出 `<原檔名>.srt` 與 `<原檔名>.txt` 到輸入檔同目錄。

```bash
source .venv/bin/activate
python transcribe.py "/Users/paul/Documents/2026答疑音频/2026年1月5日Tai師父微信公眾號答疑.mp3"
```

指定輸出檔基底（會自動加 `.srt`、`.txt`）：

```bash
python transcribe.py input.mp3 -o /tmp/out
# 會產生 /tmp/out.srt 與 /tmp/out.txt
```

### 批次辨識整個資料夾

```bash
source .venv/bin/activate
python batch_transcribe.py "/Users/paul/Documents/2026答疑音频"
```

- 依檔案大小由小到大處理（先看到結果）
- 同名 `.srt` 與 `.txt` 都已存在則自動跳過
- 失敗的檔案會記錄到輸出目錄下的 `failed.log`，並繼續處理下一個

### 常用參數

兩個腳本共用：

| 參數 | 說明 | 預設 |
|------|------|------|
| `--asr-model` | ASR 模型名稱 | `paraformer-zh` |
| `--vad-model` | VAD 模型名稱 | `fsmn-vad` |
| `--punc-model` | 標點還原模型（`ct-punc` 用 cn-en 1GB 大模型；`none` 停用） | `iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch` |
| `--device` | `cpu` / `cuda:0` / `mps`（Mac 建議 `cpu`） | `cpu` |
| `--vad-max-segment-ms` | VAD 切段最大毫秒數 | `30000` |
| `--max-line-chars` | SRT 單行最多字數 | `28` |
| `--max-cue-seconds` | 單則字幕最長秒數 | `8.0` |

`transcribe.py` 額外參數：

| 參數 | 說明 |
|------|------|
| `--no-srt` / `--no-txt` | 不輸出對應檔案 |

`batch_transcribe.py` 額外參數：

| 參數 | 說明 | 預設 |
|------|------|------|
| `--output-dir` | 輸出資料夾 | 與輸入同目錄 |
| `--order` | `size` / `name` / `name-desc` | `size` |
| `--limit` | 只處理前 N 個檔案（0=不限） | `0` |
| `--force` | 即使已有 .srt/.txt 也重做 | 關閉 |

## 效能說明

在 Intel Mac CPU（OMP_NUM_THREADS=1）測試：

- 16 分鐘音檔：辨識約 **80 秒**（RTF ≈ 0.08，比 audio 快 10 倍以上）
- 30 分鐘音檔：辨識約 **2.5 分鐘**

首次執行需下載模型（約 1.2 GB），會慢一些（10–30 分鐘）；之後皆走本機快取。

## 限制

- 模型為**離線批次**辨識，本工具未做即時串流。
- 若音檔背景音過大，建議先用 `../audio_denoiser/denoise.py` 降噪後再辨識。
- SRT 切句時間以 FunASR 回傳的 `sentence_info` 為主、無 `sentence_info` 時退回到逐字 `timestamp` + 標點切句。極短或極長的句子會自動依時間/字數再切。
- 預設用 Chinese-only 的標點模型；若錄音中混雜大量英文，可加 `--punc-model ct-punc` 改用 cn-en 大模型（首次需下 ~1 GB）。
