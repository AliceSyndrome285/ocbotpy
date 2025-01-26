import os
import base64
import glob
import yaml  # 导入 PyYAML 库

def gif_to_base64(gif_path):
    """将 GIF 文件转换为 base64 编码"""
    try:
        with open(gif_path, "rb") as image_file:
            base64_bytes = base64.b64encode(image_file.read())
            base64_string = base64_bytes.decode("utf-8")
            return base64_string
    except FileNotFoundError:
        print(f"文件未找到: {gif_path}")
        return None
    except Exception as e:
        print(f"转换 {gif_path} 时发生错误: {e}")
        return None

def update_config_with_base64(config_path):
    """
    遍历当前目录下的 GIF 文件，转换为 base64 编码，并更新到 config.yaml 文件中
    """
    # 读取现有的 config.yaml
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)  # 使用 yaml.safe_load 读取文件
    except FileNotFoundError:
        print(f"配置文件 {config_path} 未找到，将创建一个新的配置文件。")
        config = {}
    except Exception as e:
        print(f"读取配置文件 {config_path} 时发生错误: {e}")
        return

    if config is None:
        config = {}

    # 获取当前目录下的所有 GIF 文件
    gif_files = glob.glob("*.png")

    if not gif_files:
        print("当前目录下没有找到 GIF 文件。")
        return

    # 如果 emotion_mapping 不存在，则创建一个
    if "emotion_mapping" not in config:
        config["emotion_mapping"] = {}

    for gif_file in gif_files:
        # 获取不带扩展名的文件名作为键（例如 [疑惑]）
        emotion_key = os.path.splitext(gif_file)[0]

        # 检查是否已存在同名的 key
        if emotion_key in config["emotion_mapping"]:
            print(f"已存在 {emotion_key}, 跳过 {gif_file}。")
            continue  # 跳过当前循环，继续处理下一个文件

        # 转换为 base64
        base64_string = gif_to_base64(gif_file)

        if base64_string:
            # 更新到 emotion_mapping
            config["emotion_mapping"][emotion_key] = base64_string
            print(f"已将 {gif_file} 转换为 base64 并添加到 emotion_mapping。")

    # 将更新后的配置写回 emotion_config.yaml
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)  # 使用 yaml.dump 写入文件
        print("emotion_config.yaml 文件已更新。")
    except Exception as e:
        print(f"写入 emotion_config.yaml 文件时发生错误: {e}")

if __name__ == "__main__":
    # 获取 emotion_config.yaml.yaml 的路径
    config_path = os.path.join(os.path.dirname(__file__), "emotion_config.yaml")
    update_config_with_base64(config_path)
