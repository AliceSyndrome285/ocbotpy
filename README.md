# QQ群聊机器人

这个项目是一个基于 BotPY 和 Python 的 QQ 群聊机器人，集成了 Dify API、记忆处理应用和 Azure 语音合成服务，提供智能对话、记忆总结和语音回复等功能。

## 功能

* **智能对话:** 通过 接入Dify API 实现智能对话，根据用户的问题提供相应的答案。
* **记忆和总结:**  将对话历史记录发送到一个独立的记忆处理应用，并定期对对话内容进行总结，发送给 Dify API，帮助维持上下文和提升对话连贯性。
* **语音合成:**  使用 Azure 语音合成服务将机器人的回复转换为语音，并以 SILK 格式发送到群聊中 (需要配置 Azure 语音服务)。
* **情绪图片:** 支持配置情绪词典，将消息中的情绪词替换为对应的图片。

## 架构

该机器人主要由以下几个部分组成：

* **BotPY 客户端:** 负责接收群消息、@机器人消息，并调用 Dify API 获取回复。
* **Dify API:** 提供智能对话的核心功能。
* **记忆处理应用:** 接收对话历史记录，并定期生成总结。
* **Azure 语音合成服务 (可选):** 将文本转换为语音。

## 安装

1.  **克隆仓库:** `git clone https://github.com/your-username/your-repo-name.git`
2.  **安装依赖:** `pip install -r requirements.txt`
3.  **配置:**
    *   复制 `config.yaml.example` 并重命名为 `config.yaml`，填写你的 AppID、AppSecret、API Key 等配置信息。
    *   复制 `emotion_config.yaml.example` 并重命名为 `emotion_config.yaml`，配置情绪词和对应的 base64 图片字符串。

## 使用

1.  运行 `python main.py` 启动机器人。
2.  在 QQ 群中 @机器人，即可与其进行对话。
3.  在消息中添加 `-v` 可以触发语音回复功能 (需要配置 Azure 语音服务)。

## 配置

### `config.yaml`

*   `appid`: 你的机器人 AppID。
*   `secret`: 你的机器人 AppSecret。
*   `api_url`: Workshop API 的 URL。
*   `api_key`: Workshop API 的 Key。
*   `memory_api_url`: 记忆处理应用的 API URL。
*   `memory_api_key`: 记忆处理应用的 API Key。
*   `speech_key`: Azure 语音服务的 Key (可选)。
*   `speech_region`: Azure 语音服务的区域 (可选)。
*   `xml_lang`: SSML 的语言，默认为 `zh-CN`。
*   `voice_name`:  语音名称，默认为 `zh-CN-XiaochenNeural`。
*   `style`:  语音风格，默认为 `live_commercial`。
*   `style_degree`: 语音风格程度，默认为 `2`。



### `emotion_config.yaml`

*   `emotion_mapping`:  一个字典，键为情绪词，值为对应的 base64 图片字符串。

## Ocworkshop应用和memory应用文件获取

![微信图片_20250123204448](https://github.com/user-attachments/assets/24b3f43b-3fb3-4e3b-bdfa-c8aa800e58ee)

## 给作者买杯奶茶
![微信图片_20250123204355](https://github.com/user-attachments/assets/090ede99-669a-4ab4-9e60-5deaf4a95569)
