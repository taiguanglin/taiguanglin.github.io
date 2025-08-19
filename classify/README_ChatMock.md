# ChatMock 集成使用说明

## 概述

本系统现在支持使用 [ChatMock](https://github.com/RayBytes/ChatMock) 作为OpenAI API的替代方案。ChatMock是一个本地服务器，通过您的ChatGPT Plus/Pro账户来提供GPT-5等模型的访问。

## 优势

- **无需OpenAI API Key**：使用您的ChatGPT订阅
- **支持GPT-5模型**：访问最新的AI模型
- **本地运行**：数据不离开您的设备
- **成本效益**：利用现有的ChatGPT订阅

## 安装和设置

### 1. 安装ChatMock

```bash
# 克隆ChatMock项目
git clone https://github.com/RayBytes/ChatMock.git
cd ChatMock

# 安装依赖
pip install -r requirements.txt
```

### 2. 登录ChatGPT账户

```bash
# 使用您的ChatGPT账户登录
python chatmock.py login

# 验证登录状态
python chatmock.py info
```

### 3. 启动ChatMock服务器

```bash
# 启动服务器（默认端口8000）
python chatmock.py serve

# 或者使用自定义参数
python chatmock.py serve --reasoning-effort high --reasoning-summary detailed
```

## 配置系统

### 1. 修改config.ini

将API类型设置为ChatMock：

```ini
[api]
# API類型選擇
type = chatmock

[chatmock]
# ChatMock本地服務器設定
base_url = http://127.0.0.1:8000/v1
model = gpt-5
reasoning_effort = medium
reasoning_summary = auto
```

### 2. 配置选项说明

#### API类型选择
- `type = openai`：使用OpenAI官方API
- `type = chatmock`：使用ChatMock本地服务器

#### ChatMock服务器设置
- `base_url`：ChatMock服务器地址（默认：http://127.0.0.1:8000/v1）
- `model`：使用的模型名称（推荐：gpt-5）
- `reasoning_effort`：推理努力等级（low/medium/high）
- `reasoning_summary`：推理摘要类型（auto/concise/detailed/none）

## 使用方法

### 1. 启动ChatMock服务器

```bash
cd ChatMock
python chatmock.py serve
```

### 2. 运行分类系统

#### 使用配置文件设置
```bash
# 使用ChatMock配置
python3 qa_classifier_v2.py

# 或者指定配置文件
python3 qa_classifier_v2.py --config config.ini
```

#### 使用命令行参数覆盖
```bash
# 强制使用OpenAI API（覆盖配置文件）
python3 qa_classifier_v2.py --api-key YOUR_API_KEY --api-type openai

# 强制使用ChatMock（覆盖配置文件）
python3 qa_classifier_v2.py --api-type chatmock

# 指定自定义ChatMock服务器地址
python3 qa_classifier_v2.py --api-type chatmock --chatmock-url http://localhost:9000/v1
```

### 3. 验证连接

系统启动时会显示：
```
ChatMock設置完成 - 服務器: http://127.0.0.1:8000/v1
使用模型: gpt-5
```

## 参数调优

### 推理努力等级

- **low**：最快回应，推理质量较低
- **medium**：平衡速度和质量（推荐）
- **high**：最高推理质量，回应较慢

### 推理摘要类型

- **auto**：自动选择（推荐）
- **concise**：简洁摘要
- **detailed**：详细摘要
- **none**：无摘要，最快回应

## 故障排除

### 1. 连接错误

如果遇到"Connection error"：

```bash
# 检查ChatMock服务器是否运行
curl http://127.0.0.1:8000/v1/models

# 重启ChatMock服务器
python chatmock.py serve
```

### 2. 配置文件与命令行参数冲突

如果配置文件设置为ChatMock但您想使用OpenAI API：

```bash
# 使用命令行参数强制覆盖
python3 qa_classifier_v2.py --api-key YOUR_API_KEY --api-type openai
```

### 3. 验证API类型选择

启动时查看日志确认使用的API类型：

```
使用API類型: openai
OpenAI設置完成 - 模型: gpt-5-nano
```

或

```
使用API類型: chatmock
ChatMock設置完成 - 服務器: http://127.0.0.1:8000/v1
```

### 2. 认证错误

如果遇到认证问题：

```bash
# 重新登录
python chatmock.py login

# 检查登录状态
python chatmock.py info
```

### 3. 模型不可用

确保ChatMock支持您选择的模型：

```bash
# 查看可用模型
curl http://127.0.0.1:8000/v1/models
```

## 性能建议

### 最佳配置

```ini
[chatmock]
reasoning_effort = medium
reasoning_summary = auto
```

### 快速配置

```ini
[chatmock]
reasoning_effort = low
reasoning_summary = none
```

### 高质量配置

```ini
[chatmock]
reasoning_effort = high
reasoning_summary = detailed
```

## 注意事项

1. **需要ChatGPT Plus/Pro账户**：免费账户无法使用
2. **网络连接**：需要稳定的网络连接
3. **速率限制**：可能比ChatGPT应用有更严格的限制
4. **模型限制**：仅支持ChatMock支持的模型

## 技术支持

- ChatMock项目：[https://github.com/RayBytes/ChatMock](https://github.com/RayBytes/ChatMock)
- 问题反馈：在ChatMock项目页面提交Issue

## 许可证

ChatMock使用MIT许可证，本集成遵循相同的许可证条款。
