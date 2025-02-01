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

_log = logging.get_logger()

# 读取配置文件
test_config = read(os.path.join(os.path.dirname(__file__), "config.yaml"))
emotion_config = read(os.path.join(os.path.dirname(__file__), "emotion_config.yaml"))
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
def read_conversation_id(filename):
    try:
        with open(filename, "r") as f:
            conversation_id = f.read().strip()
            return conversation_id if conversation_id else None
    except FileNotFoundError:
        return None

# 函数：写入 conversation_id
def write_conversation_id(filename, conversation_id):
    with open(filename, "w") as f:
        f.write(conversation_id)
async def call_api(query):
    conversation_id = read_conversation_id(API_CONVERSATION_ID_FILE)

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
                    write_conversation_id(API_CONVERSATION_ID_FILE, new_conversation_id)
                    print(f"New conversation_id for API saved: {new_conversation_id}")

            return answer
        else:
            print(f"API请求失败，状态码：{response.status_code}")
            return "抱歉，服务暂时不可用"
async def call_memory_api(query, answer=None):
    conversation_id = read_conversation_id(MEMORY_API_CONVERSATION_ID_FILE)

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
                write_conversation_id(MEMORY_API_CONVERSATION_ID_FILE, new_conversation_id)
                print(f"New conversation_id for Memory API saved: {new_conversation_id}")

        return memory_answer
    else:
        print(f"Memory API 请求失败，状态码：{response.status_code}")
        return None
async def process_memory(query, answer):
    """异步处理记忆相关逻辑"""
    global conversation_turn_counter
    conversation_turn_counter += 1

    #  每次都将query 和 answer 发送到记忆处理应用
    await call_memory_api(query, answer)

    if conversation_turn_counter % 10 == 0:
        # 检查是否已经请求过总结
        if os.path.exists(SUMMARY_REQUESTED_FLAG):
            print("总结请求已发送，不再重复发送")
            return
        # 发送总结指令
        summary_response = await call_memory_api("【【开始总结】】")

        if summary_response:
            # 使用锁来确保发送总结结果时，不会处理新的用户消息
            async with api_call_lock:
              # 将总结结果发送给 ocworkshop
              await call_api(f"【【总结】】{summary_response}")
              print(f"已发送总结内容给 ocworkshop: {summary_response}")

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
    """将段落中的情绪词替换为对应的 base64 图片"""
    _log.info(f"开始处理段落: {paragraph}")
    parts = []
    last_match_end = 0
    for emotion, base64_str in emotion_mapping.items():
        _log.info(f"正在查找表情: {emotion}")
        for match in re.finditer(re.escape(emotion), paragraph):
            start, end = match.span()
            _log.info(f"找到表情: {emotion}，位置: {start}-{end}")

            # 添加匹配之前的文本
            if start > last_match_end:
                text_part = paragraph[last_match_end:start]
                _log.info(f"添加文本部分: {text_part}")
                parts.append(("text", text_part))

            # 添加图片标签
            _log.info(f"添加图片部分: {base64_str[:20]}... (Base64 编码前20个字符)")
            parts.append(("image", base64_str))
            last_match_end = end

    # 添加匹配后的剩余文本
    if last_match_end < len(paragraph):
        text_part = paragraph[last_match_end:]
        _log.info(f"添加剩余文本部分: {text_part}")
        parts.append(("text", text_part))

    _log.info(f"段落处理完成，共生成 {len(parts)} 部分")
    return parts


async def upload_and_build_media_message(base64_str: str, message: GroupMessage):
    """上传图片并构建媒体消息"""
    _log.info(f"开始上传图片: {base64_str[:20]}... (Base64 编码前20个字符)")
    try:
        uploadMedia = await message._api.post_group_file(
            group_openid=message.group_openid,
            file_type=1,  # 1 表示图片
            file_data=base64_str
        )
        _log.info(f"图片上传响应: {uploadMedia}")

        file_uuid = uploadMedia.get('file_uuid')
        file_info = uploadMedia.get('file_info')
        ttl = uploadMedia.get('ttl')

        if file_uuid and file_info and ttl:
            _log.info(f"图片上传成功: file_uuid={file_uuid}, file_info={file_info}, ttl={ttl}")
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
