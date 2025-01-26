import os
import azure.cognitiveservices.speech as speechsdk
import pilk
import tempfile
import av
import io
import base64
import botpy
from botpy import logging
from botpy.message import GroupMessage
from botpy.ext.cog_yaml import read
import requests
import numpy
import re
import asyncio
import json

_log = logging.get_logger()

# 读取配置文件
test_config = read(os.path.join(os.path.dirname(__file__), "config.yaml"))
api_call_lock = asyncio.Lock()
# API 配置
API_URL = test_config.get("api_url")
API_KEY = test_config.get("api_key")
API_HEADERS = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}

# 记忆处理应用的 API 配置
MEMORY_API_URL = test_config.get("memory_api_url")
MEMORY_API_KEY = test_config.get("memory_api_key")
MEMORY_API_HEADERS = {
    'Authorization': f'Bearer {MEMORY_API_KEY}',
    'Content-Type': 'application/json'
}
# MEMORY_CONVERSATION_ID = test_config.get("memory_conversation_id")  # 移除此行，不再从配置文件读取
# 读取 emotion_config，如果为空或不存在则使用空字典
try:
    emotion_config = read(os.path.join(os.path.dirname(__file__), "emotion_config.yaml"))
except FileNotFoundError:
    emotion_config = {}  # Handle file not found
except Exception as e: # Handle other potential errors during YAML loading
    _log.error(f"Error loading emotion_config.yaml: {e}")
    emotion_config = {}

emotion_mapping = emotion_config.get("emotion_mapping", {})
# Azure 语音配置
speech_key = test_config.get("speech_key")
speech_region = test_config.get("speech_region")

if not all([speech_key, speech_region]):
     _log.warning("SPEECH_KEY 和 SPEECH_REGION 未配置，语音合成功能将不可用.")
     print("SPEECH_KEY 和 SPEECH_REGION 未配置，语音合成功能将不可用.")

else:
  speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
  speech_config.speech_synthesis_voice_name = 'zh-CN-XiaochenNeural'
# 对话轮次计数器
conversation_turn_counter = 0
# conversation_id 存储文件
API_CONVERSATION_ID_FILE = "api_conversation_id.txt"
MEMORY_API_CONVERSATION_ID_FILE = "memory_api_conversation_id.txt"
SUMMARY_REQUESTED_FLAG = "summary_requested.txt"
# 函数：读取 conversation_id
def read_conversation_data(filename):
    """
    读取 JSON 文件，返回 conversation_id 和计数。
    如果文件不存在或格式错误，返回 (None, 0)。    """
    try:
        with open(filename, "r") as f:
            data = json.load(f)
            conversation_id = data.get("conversation_id")
            count = data.get("count", 0)  # 如果 count 不存在，默认为 0
            return conversation_id, count
    except (FileNotFoundError, json.JSONDecodeError):
        return None, 0
# 函数：写入 conversation_id
def write_conversation_data(filename, conversation_id, count):
    """
    更新 JSON 文件中的 conversation_id 和计数。
    如果文件不存在，则创建新文件。    """
    data = {
        "conversation_id": conversation_id,
        "count": count
    }

    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

async def call_api(query):
    global conversation_turn_counter  # 保留全局变量以进行其他用途的计数，例如日志记录
    conversation_id, current_count = read_conversation_data(API_CONVERSATION_ID_FILE)

    data = {
        "inputs": {},
        "query": query,
        "response_mode": "blocking",
        "conversation_id": conversation_id,
        "user": "admin",
    }
    async with api_call_lock:
        response = requests.post(API_URL, json=data, headers=API_HEADERS)

        print(f"Received response: {response.status_code} - {response.text}")

        if response.status_code == 200:
            response_json = response.json()
            answer = response_json.get('answer', '没有返回数据')

            # 如果发送的 conversation_id 为空，则获取新的 conversation_id 并保存
            if not conversation_id:
                new_conversation_id = response_json.get("conversation_id")
                if new_conversation_id:
                    # 写入新 conversation_id 和初始计数 1
                    write_conversation_data(API_CONVERSATION_ID_FILE, new_conversation_id, 1)
                    print(f"New conversation_id for API saved: {new_conversation_id}, count initialized to 1")
                    conversation_id = new_conversation_id
            conversation_turn_counter = current_count
            return answer
        else:
            print(f"API请求失败，状态码：{response.status_code}")
            return "抱歉，服务暂时不可用"
async def call_memory_api(query, answer=None):
    global conversation_turn_counter

    conversation_id, current_count = read_conversation_data(MEMORY_API_CONVERSATION_ID_FILE)

    if answer:
        formatted_message = f"用户：{query}\nAI：{answer}"
    else:
        formatted_message = query

    data = {
        "inputs": {},
        "query": formatted_message,
        "response_mode": "blocking",
        "conversation_id": conversation_id,
        "user": "bot",
    }

    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, lambda: requests.post(MEMORY_API_URL, json=data, headers=MEMORY_API_HEADERS))
    response = await future

    print(f"Memory API Received response: {response.status_code} - {response.text}")

    if response.status_code == 200:
        response_json = response.json()
        memory_answer = response_json.get('answer', '没有返回数据')

        # 如果发送的 conversation_id 为空，则获取新的 conversation_id 并保存
        if not conversation_id:
            new_conversation_id = response_json.get("conversation_id")
            if new_conversation_id:
                # 写入新 conversation_id 和初始计数 1
                write_conversation_data(MEMORY_API_CONVERSATION_ID_FILE, new_conversation_id, 1)
                print(f"New conversation_id for Memory API saved: {new_conversation_id}, count initialized to 1")
                conversation_id = new_conversation_id
        return memory_answer
    else:
        print(f"Memory API 请求失败，状态码：{response.status_code}")
        return None

def search_databases(api_key, base_url):
    """
    查询知识库列表，获取第一个 dataset 的 ID。

    Args:
      api_key: 你的 API 密钥。
      base_url: API 的 base URL。

    Returns:
      第一个 dataset 的 ID，如果没有找到则返回 None。
    """
    url = f"{base_url}/v1/datasets?page=1&limit=1"  # Limit to 1 to get only the first dataset
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    response_json = response.json()

    if response_json and response_json['data']:
        dataset_id = response_json['data'][0]['id']
        print(f"Found dataset ID: {dataset_id}")
        return dataset_id
    else:
        print("No datasets found.")
        return None

def get_documents_in_dataset(api_key, base_url, dataset_id):
    """
    查询指定知识库的文档列表，获取第一个 document 的 ID。

    Args:
      api_key: 你的 API 密钥。
      base_url: API 的 base URL。
      dataset_id: 知识库 ID。

    Returns:
      第一个 document 的 ID，如果没有找到则返回 None。
    """
    url = f"{base_url}/v1/datasets/{dataset_id}/documents?page=1&limit=1"  # Limit to 1 to get only the first document
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    response_json = response.json()

    if response_json and response_json['data']:
        document_id = response_json['data'][0]['id']
        print(f"Found document ID: {document_id}")
        return document_id
    else:
        print(f"No documents found in dataset {dataset_id}.")
        return None

def update_document_by_text(api_key, base_url, dataset_id, document_id, text):
    """
    通过文本更新知识库中的文档。

    Args:
      api_key: 你的 API 密钥。
      base_url: API 的 base URL。
      dataset_id: 知识库 ID。
      document_id: 文档 ID。
      text: 要更新的文本内容。
      name: 文档名称 (可选，默认为 "rag_memory.txt")。

    Returns:
      API 响应的 JSON 对象。
    """

    url = f"{base_url}/v1/datasets/{dataset_id}/documents/{document_id}/segments"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    segments = [{"content": paragraph} for paragraph in text.split('\n')]
    data = {"segments": segments}

    response = requests.post(url, headers=headers, data=json.dumps(data))
    response.raise_for_status()

    return response.json()

def parse_rag_memory(text):
    """
    解析 RAG 记忆构建智能体生成的文本，并去除 Dify 添加的单个转义符 \。
    （这个函数在之前的回答中已经提供，无需修改）
    """
    # ... (省略代码，与之前回答中的 parse_rag_memory 函数相同) ...
    # 找到第一个 "type:" 的位置
    start_index = text.find("type:")
    if start_index == -1:
        return ""  # 如果没有找到 "type:"，则返回空字符串

    # 找到最后一个 "type:" 的位置
    last_type_index = text.rfind("type:")

    # 找到最后一个 "type:" 所在行的最后一个非 \ 字符的位置
    end_index = -1

    # 从最后一个 "type:" 所在位置开始向后查找
    for i in range(last_type_index, len(text)):
        # 遇到换行符或到达文本末尾，则停止查找
        if text[i] == '\n' or i == len(text) - 1:
            end_index = i
            break

    # 提取指定范围内的文本
    extracted_text = text[start_index:end_index + 1]

    # 使用正则表达式去除单独的 \，保留 \n
    extracted_text = re.sub(r'(?<!\\)\\(?!n)', '', extracted_text)

    # 去除多余的空格
    extracted_text = extracted_text.strip()

    return extracted_text

async def process_memory(query, answer):
    """异步处理记忆相关逻辑"""
    # 获取 Memory API 的 conversation_id 和计数
    memory_conversation_id, memory_current_count = read_conversation_data(MEMORY_API_CONVERSATION_ID_FILE)
    memory_current_count += 1
    write_conversation_data(MEMORY_API_CONVERSATION_ID_FILE, memory_conversation_id, memory_current_count)

    # 获取 API 的 conversation_id 和计数
    api_conversation_id, api_current_count = read_conversation_data(API_CONVERSATION_ID_FILE)
    api_current_count += 1
    write_conversation_data(API_CONVERSATION_ID_FILE, api_conversation_id, api_current_count)



    #  每次都将query 和 answer 发送到记忆处理应用
    await call_memory_api(query, answer)

    if memory_current_count % 10 == 0:
        # 检查是否已经请求过总结
        if os.path.exists(SUMMARY_REQUESTED_FLAG):
            print("总结请求已发送，不再重复发送")
            return
        # 发送总结指令
        summary_response = await call_memory_api("【【开始总结】】")
        _log.info(f"收到总结请求的响应: {summary_response}")

        if summary_response:
            # 使用锁来确保发送总结结果时，不会处理新的用户消息
            async with api_call_lock:
                # 使用 re.DOTALL 标志来匹配所有字符，包括换行符
                parts = re.split(r"(【【.+?】】)", summary_response, flags=re.DOTALL)
                _log.info(f"总结内容拆分结果: {parts}")
                summary_content = ""
                permanent_memory_content = ""

                # 遍历 parts，找到 "【【总结】】" 和 "【【永久记忆】】"
                for i in range(1, len(parts), 2):
                    if parts[i] == "【【总结】】":
                        summary_content = (parts[i] + parts[i+1].strip())
                    elif parts[i] == "【【永久记忆】】":
                        permanent_memory_content = parts[i+1].strip()

                # 去除 summary_content 首尾的空白字符
                summary_content = summary_content.strip()

                # 打印 summary_content 的长度和是否为空
                print(f"summary_content 的长度: {len(summary_content)}, 内容是否为空: {not summary_content}")

                # 发送总结内容给 ocworkshop
                if summary_content:
                    _log.info(f"准备发送给 ocworkshop 的总结内容: {summary_content}")
                    await call_api(summary_content)
                    print(f"已发送总结内容给 ocworkshop: {summary_content}")

                # 将永久记忆内容写入知识库
                if permanent_memory_content:
                    dataset_api_key = test_config.get("dataset_api_key")
                    dataset_base_url = test_config.get("dataset_base_url")
                    if dataset_api_key and dataset_base_url:
                        parsed_memory = parse_rag_memory(permanent_memory_content)
                        dataset_id = search_databases(dataset_api_key, dataset_base_url)
                        if dataset_id:
                            document_id = get_documents_in_dataset(dataset_api_key, dataset_base_url, dataset_id)
                            if document_id:
                                try:
                                    response_json = update_document_by_text(dataset_api_key, dataset_base_url, dataset_id, document_id, parsed_memory)
                                    print("API 响应:")
                                    print(json.dumps(response_json, indent=2))
                                except requests.exceptions.RequestException as e:
                                    print(f"请求失败: {e}")
                            else:
                                print("获取文档 ID 失败")
                        else:
                            print("获取知识库 ID 失败")
                    else:
                        print("未配置知识库 API 密钥或基础 URL")

                # 标记已请求总结
                with open(SUMMARY_REQUESTED_FLAG, "w") as f:
                    f.write("requested")
        else:
            print("获取总结内容失败")

def to_pcm_from_buffer(audio_buffer: bytes, file_type: str) -> tuple[bytes, int]:
    """将内存中的音频数据转换为 PCM"""
    with av.open(io.BytesIO(audio_buffer), format=file_type) as in_container:
        if len(in_container.streams.audio) == 0:
            raise ValueError("输入音频没有音频流")

        in_stream = in_container.streams.audio[0]
        sample_rate = in_stream.codec_context.sample_rate

        pcm_buffer = bytes()
        for frame in in_container.decode(in_stream):
            audio_data = frame.to_ndarray()
            pcm_buffer += audio_data.tobytes()

        return pcm_buffer, sample_rate

def convert_to_silk_from_buffer(audio_buffer: bytes, in_format: str) -> bytes:
    """将内存中的音频数据转换为 Silk，返回 Silk 数据的字节串"""
    pcm_buffer, sample_rate = to_pcm_from_buffer(audio_buffer, in_format)

    # 使用 NamedTemporaryFile 创建临时 PCM 和 Silk 文件
    with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as temp_pcm_file, \
            tempfile.NamedTemporaryFile(suffix=".silk", delete=False) as temp_silk_file:

        temp_pcm_filename = temp_pcm_file.name
        temp_silk_filename = temp_silk_file.name

        with open(temp_pcm_filename, "wb") as f:
            f.write(pcm_buffer)

        # 正确调用 pilk.encode，提供输入和输出文件路径
        pilk.encode(temp_pcm_filename, temp_silk_filename, pcm_rate=sample_rate, tencent=True)

        # 读取转换后的 Silk 数据
        with open(temp_silk_filename, "rb") as f:
            silk_buffer = f.read()

    # 删除中间的 PCM 和 Silk 文件
    os.remove(temp_pcm_filename)
    os.remove(temp_silk_filename)

    return silk_buffer

def convert_silk_to_base64(silk_data: bytes) -> str:
    """将 Silk 数据 (字节串) 转换为 Base64 编码的字符串"""
    base64_encoded_data = base64.b64encode(silk_data)
    base64_string = base64_encoded_data.decode('utf-8')
    return base64_string

async def synthesize_speech_to_silk_base64(text: str) -> str:
    """合成语音，转换为 Silk 格式，并返回 Base64 编码"""
    # 添加条件，检查 speech_key 和 speech_region 是否都存在
    if not all([speech_key, speech_region]):
      _log.warning("由于 SPEECH_KEY 和 SPEECH_REGION 未配置，无法合成语音.")
      print("由于 SPEECH_KEY 和 SPEECH_REGION 未配置，无法合成语音.")
      return None
    # 创建语音合成器 (不使用 audio_config)
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

    # 从配置文件读取 SSML 相关属性
    xml_lang = test_config.get("xml_lang", "zh-CN")
    voice_name = test_config.get("voice_name", "zh-CN-XiaochenNeural")
    style = test_config.get("style", "live_commercial")
    style_degree = test_config.get("style_degree", "2")

    ssml = '''
    <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{xml_lang}">
    <voice name="{voice_name}">
    <mstts:express-as style="{style}" styledegree="{style_degree}">
    {text}
    </mstts:express-as>
    </voice>
    </speak>
    '''.format(xml_lang=xml_lang, voice_name=voice_name, style=style, style_degree=style_degree, text=text)

    # 合成语音并获取 AudioDataStream
    synthesis_result = speech_synthesizer.speak_ssml_async(ssml).get()

    # 处理 AudioDataStream
    if synthesis_result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("Speech synthesized successfully.")
        stream = speechsdk.AudioDataStream(synthesis_result)

        # 使用 save_to_wav_file 保存到临时文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav_file:
            temp_wav_filename = temp_wav_file.name
            stream.save_to_wav_file(temp_wav_filename)

        # 读取临时文件
        with open(temp_wav_filename, "rb") as f:
            audio_buffer = f.read()

        # 删除临时文件
        os.remove(temp_wav_filename)

        # 将 WAV 转换为 Silk
        silk_data = convert_to_silk_from_buffer(audio_buffer, "wav")
        # 将 Silk 转换为 Base64
        base64_string = convert_silk_to_base64(silk_data)
        return base64_string
    else:
        print(f"Speech synthesis failed: {synthesis_result.error_details}")
        return None
def replace_emotion_with_base64(paragraph: str) -> list:
    """将段落中的情绪词替换为对应的 base64 图片, 处理 emotion_mapping 为 None 的情况"""
    parts = []
    last_match_end = 0
    if emotion_mapping: # Check if emotion_mapping is not empty
        for emotion, base64_str in emotion_mapping.items():
            for match in re.finditer(re.escape(emotion), paragraph):
                start, end = match.span()

            # 添加匹配之前的文本
            if start > last_match_end:
                parts.append(("text", paragraph[last_match_end:start]))

            # 添加图片标签
            parts.append(("image", base64_str))
            last_match_end = end

    # 添加匹配后的剩余文本
    if last_match_end < len(paragraph):
        parts.append(("text", paragraph[last_match_end:]))
    else: # If emotion_mapping is empty, just return the entire paragraph as text
        parts.append(("text", paragraph))
    return parts

async def upload_and_build_media_message(base64_str: str, message: GroupMessage):
    """上传图片并构建媒体消息"""
    try:
        uploadMedia = await message._api.post_group_file(
            group_openid=message.group_openid,
            file_type=1,  # 1 表示图片
            file_data=base64_str
        )

        file_uuid = uploadMedia.get('file_uuid')
        file_info = uploadMedia.get('file_info')
        ttl = uploadMedia.get('ttl')

        if file_uuid and file_info and ttl:
            return {
                "file_uuid": file_uuid,
                "file_info": file_info,
                "ttl": ttl
            }
        else:
            _log.error(f"上传媒体失败，缺少必要的字段: file_uuid, file_info, ttl. Response: {uploadMedia}")
            print(f"上传媒体失败，缺少必要的字段: file_uuid, file_info, ttl. Response: {uploadMedia}")
            return None
    except Exception as e:
        _log.error(f"上传媒体时发生异常: {e}")
        print(f"上传媒体时发生异常: {e}")
        return None
class MyClient(botpy.Client):
    async def on_ready(self):
        _log.info(f"robot 「{self.robot.name}」 on_ready!")

    async def on_group_at_message_create(self, message: GroupMessage):
        # 清理总结请求标志文件
        if os.path.exists(SUMMARY_REQUESTED_FLAG):
            os.remove(SUMMARY_REQUESTED_FLAG)
        # 获取群消息的内容
        query = message.content
        answer = await call_api(query)
        if api_call_lock.locked():
            print("正在处理总结，请稍后再试")
            return
        if answer:
            # 异步处理记忆逻辑
            asyncio.create_task(process_memory(query, answer))
        if answer:
            if "-v" in query:  # 检查 query 中是否包含 "-v"
                # 将 answer 作为输入，合成语音并转换为 Base64
                base64_audio = await synthesize_speech_to_silk_base64(answer)
                if base64_audio:
                    # 调用 API 发送群消息
                    try:
                         uploadMedia = await message._api.post_group_file(
                             group_openid=message.group_openid,
                             file_type=3,
                             file_data=base64_audio
                         )
                         _log.info(f"uploadMedia: {uploadMedia}")

                         # 直接从 uploadMedia 获取所需的字段
                         file_uuid = uploadMedia.get('file_uuid')
                         file_info = uploadMedia.get('file_info')
                         ttl = uploadMedia.get('ttl')
                         if file_uuid and file_info and ttl:
                            # 使用获取到的字段创建 Media 对象
                            media_data = {
                                "file_uuid": file_uuid,
                                "file_info": file_info,
                                "ttl": ttl
                            }

                            messageResult = await message._api.post_group_message(
                                group_openid=message.group_openid,
                                msg_type=7,
                                msg_id=message.id,
                                media=media_data,
                                msg_seq=21314
                            )
                            _log.info(messageResult)
                         else:
                            # 处理缺少必要字段的情况
                            _log.error("上传媒体失败，缺少必要的字段: file_uuid, file_info, ttl")
                            print("上传媒体失败，缺少必要的字段: file_uuid, file_info, ttl")
                    except Exception as e:
                       _log.error(f"发送媒体消息时发生异常: {e}")
                       print(f"发送媒体消息时发生异常: {e}")
                else:
                    _log.error("语音合成或转换失败")
                    print("语音合成或转换失败")
            else:
                # 分割 answer
                paragraphs = re.split(r"\n\s*\n+", answer.strip())

                current_msg_seq = 21314
                messages_to_send = []  # 存储待发送的消息，可以是文本或媒体消息
                for paragraph in paragraphs:
                    # 替换情绪词为 base64 图片标记
                    parts = replace_emotion_with_base64(paragraph)

                    for msg_type, msg_content in parts:
                        if msg_type == "text":
                            messages_to_send.append(("text", msg_content))
                        elif msg_type == "image":
                           media_message = await upload_and_build_media_message(msg_content, message)
                           if media_message:
                              messages_to_send.append(("media", media_message))

                # 循环发送所有消息
                for msg_type, msg_content in messages_to_send:
                    try:
                         if msg_type == "text":
                            messageResult = await message._api.post_group_message(
                                group_openid=message.group_openid,
                                msg_type=0,
                                msg_id=message.id,
                                content=msg_content,
                                msg_seq=current_msg_seq
                            )
                            _log.info(f"文本消息发送结果：{messageResult}, msg_seq: {current_msg_seq}")
                         elif msg_type == "media":
                            messageResult = await message._api.post_group_message(
                                group_openid=message.group_openid,
                                msg_type=7,  # 7 表示富媒体
                                msg_id=message.id,
                                media=msg_content,
                                msg_seq=current_msg_seq
                            )
                            _log.info(f"媒体消息发送结果：{messageResult}, msg_seq: {current_msg_seq}")
                         current_msg_seq += 5
                    except Exception as e:
                        _log.error(f"发送消息时发生异常: {e}")
                        print(f"发送消息时发生异常: {e}")
                _log.info(f"成功发送 {len(messages_to_send)} 条消息.")
                print(f"成功发送 {len(messages_to_send)} 条消息.")

        else:
            _log.error("未能从 API 获取答案")
            print("未能从 API 获取答案")

if __name__ == "__main__":
    intents = botpy.Intents(public_messages=True)
    client = MyClient(intents=intents)
    client.run(appid=test_config["appid"], secret=test_config["secret"])
