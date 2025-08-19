# OpenAI API Key 安全使用指南

## 🚨 重要安全提醒

**请勿在 `config.ini` 文件中直接设置您的 OpenAI API Key！**
这样做会导致以下问题：
- 每次提交代码时都会产生警告
- API Key 可能被意外泄露
- 违反安全最佳实践

## ✅ 推荐的使用方式

### 方式1：命令行参数（最推荐）

```bash
python3 qa_classifier_v2.py --api-key "your-actual-api-key-here"
```

**优点：**
- 最安全，API Key 不会保存到任何文件
- 每次使用时明确指定
- 不会产生 commit 警告

### 方式2：环境变量

```bash
# 设置环境变量
export OPENAI_API_KEY="your-actual-api-key-here"

# 运行脚本
python3 qa_classifier_v2.py
```

**优点：**
- 相对安全，API Key 不会出现在代码中
- 一次设置，多次使用
- 适合开发环境

**注意：** 环境变量在终端关闭后会失效，需要重新设置

### 方式3：配置文件（不推荐）

如果必须使用配置文件，请确保：
1. `config.ini` 已添加到 `.gitignore`
2. 不要将包含真实 API Key 的配置文件提交到代码库

```ini
[openai]
api_key = your-actual-api-key-here
model = gpt-4.1
temperature = 0.3
max_tokens = 1000
```

## 🔧 脚本参数说明

```bash
python3 qa_classifier_v2.py [选项]

选项:
  -h, --help         显示帮助信息
  --api-key API_KEY  OpenAI API Key（推荐使用此方式）
  --config CONFIG    配置文件路径（默认: config.ini）
```

## 📝 使用示例

### 基本使用
```bash
# 使用命令行参数
python3 qa_classifier_v2.py --api-key "sk-..."

# 使用环境变量
export OPENAI_API_KEY="sk-..."
python3 qa_classifier_v2.py

# 指定配置文件
python3 qa_classifier_v2.py --config "my_config.ini" --api-key "sk-..."
```

### 查看帮助
```bash
python3 qa_classifier_v2.py --help
```

## 🛡️ 安全最佳实践

1. **永远不要**将 API Key 提交到代码库
2. **优先使用**命令行参数方式
3. **定期轮换**您的 API Key
4. **监控使用**情况，及时发现异常
5. **使用最小权限**原则设置 API Key

## 🔍 故障排除

### 问题：API Key 无效
```
Error code: 401 - Incorrect API key provided
```
**解决方案：** 检查 API Key 是否正确，确保没有多余的空格或特殊字符

### 问题：找不到配置文件
```
FileNotFoundError: [Errno 2] No such file or directory: 'config.ini'
```
**解决方案：** 使用 `--config` 参数指定正确的配置文件路径

### 问题：权限不足
```
Error code: 403 - You don't have access to this model
```
**解决方案：** 检查您的 OpenAI 账户是否有权限使用指定的模型

## 📞 获取帮助

如果遇到问题，请：
1. 检查错误信息
2. 运行 `--help` 查看选项
3. 确认 API Key 和模型设置
4. 查看日志文件 `qa_classification.log`
