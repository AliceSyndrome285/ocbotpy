# 更新日志
20250126：1.更新test.py，调整了记忆应用中总结功能和永久记忆功能的代码，并更新Dify中的记忆应用以适配。2.更新gif2base64.py，将图片转为base64格式并写入emotion_config中，实现根据聊天内容匹配角色表情包

# 使用方法
在code中下载压缩包，解压后的ocbotpy文件夹就是xhs教程中所需的文件夹

# xhs教程相关（账号：末期少女病）
* **Windterm下载地址（页面最后的Asset的windows安装包，先检查自己是32位系统64位系统，再选择要下载的安装包）:** https://github.com/kingToolbox/WindTerm/releases/tag/2.6.0
* **宝塔面板安装命令:** ：
  Ubuntu/Deepin安装命令：
  `wget -O install.sh https://download.bt.cn/install/install-ubuntu_6.0.sh && sudo bash install.sh`
* **宝塔面板终端-安装依赖命令:**
  `/www/server/pyporject_evn/examples_venv/bin/python -m pip install -r /www/server/pyporject_evn/examples_venv/requirements.txt`
  examples_venv是宝塔面板创建的虚拟环境文件夹名称，根据创建python项目时输入的名称而定，教程中的项目名为examples。
* **OCworkshop和记忆应用:** 本项目需要导入Dify应用：memory.yml和OCworkshop.yml的情况下使用，群文件获取，群：1017292082，帮忙迁移角色到QQAI，持续更新角色设定和好玩的应用，但只限AI聊天爱好者，oc爱好者和创作者入群，见谅

* 
# 项目介绍
## QQ群聊AI+基于Dify工作流的AI角色创作＆永久记忆

这个项目是一个基于 BotPY 和 Python 的 QQ 群聊机器人，集成了 Dify API、记忆处理应用和 Azure 语音合成服务，提供智能对话、记忆总结和语音回复等功能。

## 功能

* **智能对话:** 通过 接入Dify API 实现智能对话，根据用户的问题提供相应的答案。
* **记忆和总结:**  将对话历史记录发送到一个独立的记忆处理应用，并定期对对话内容进行总结，发送给 Dify API，帮助维持上下文和提升对话连贯性。
* **语音合成:**  使用 Azure 语音合成服务将机器人的回复转换为语音，并以 SILK 格式发送到群聊中 (需要配置 Azure 语音服务的speech_key和speech_region)。
* **情绪图片:** 支持配置情绪词典，将消息中的情绪词替换为对应的图片。

## 架构

该机器人主要由以下几个部分组成：

* **BotPY:** 负责接收群消息，并调用 Dify API 获取回复。
* **Dify:** 接入在线大模型生成聊天内容，总结聊天记忆，向知识库写入永久记忆
* **Azure 语音合成服务 (可选):** 将文本转换为语音。
* **表情包发送:** 根据聊天内容匹配角色表情包

## 使用

1.  运行 `python test.py` 启动机器人。
2.  在 QQ 群中 @机器人，即可与其进行对话。
3.  在消息中添加 `-v` 可以触发语音回复功能 (需要配置 Azure 语音服务的speech_key和speech_region)。
4.  在examples文件夹上传自己的表情包，命名格式类似：[高兴].png，运行gif2base64.py后，在Dify-OCworkshop中作相应的提示词要求，机器人即可在回复时输出表情包。

## 配置

### `config.yaml`

*   `appid`: `你的机器人 AppID`
*   `secret`: 你的机器人 AppSecret
*   `api_url`: Workshop API 的 URL
*   `api_key`: Workshop API 的 Key
*   `memory_api_url`: 记忆处理应用的 API URL
*   `memory_api_key`: 记忆处理应用的 API Key
*   `dataset_base_url`: 知识库API的 URL
*   `dataset_api_key`: 知识库API 的 Key
*   `speech_key`: Azure 语音服务的 Key (可选)
*   `speech_region`: Azure 语音服务的区域 (可选)
*   `xml_lang`: SSML 的语言
*   `voice_name`:  语音名称
*   `style`:  语音风格
*   `style_degree`: 语音风格程度

### `emotion_config.yaml`

*   `emotion_mapping`:  一个字典，键为情绪词，值为对应的 base64 图片字符串。

## Ocworkshop应用和memory应用文件获取

qq群：

![微信图片_20250123204448](https://github.com/user-attachments/assets/24b3f43b-3fb3-4e3b-bdfa-c8aa800e58ee)

## 给作者买杯奶茶

![微信图片_20250123204355](https://github.com/user-attachments/assets/090ede99-669a-4ab4-9e60-5deaf4a95569)
