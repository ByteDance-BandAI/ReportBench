# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
公共工具函数：链工厂、CSV 读写、重试装饰器、网页抓取等
"""
import json
import time
import requests
from pathlib import Path
from typing import Any, Iterable, Callable, Optional
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import logging
import threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import pickle
import os

import pandas as pd
import yaml
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential
from tqdm import tqdm

try:
    from firecrawl import FirecrawlApp
except ImportError:
    FirecrawlApp = None

from config import (
    OPENAI_PROVIDER,
    OPENAI_API_KEY,
    DEFAULT_MODEL,
    TEMPERATURE,
    MAX_TOKENS,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT_NAME,
    AZURE_OPENAI_API_KEY,
    WEB_LLM_KEY,
    WEB_LLM_BASE_URL
)

# 全局变量：文本块大小限制
BLOCK_SIZE = 16384  # 字符数限制

# 联网模型配置
WEB_LLM_CONFIGS = {
    "gemini-2.5-pro": {
        "api_key": WEB_LLM_KEY,
        "api_version": "",
        "base_url": WEB_LLM_BASE_URL,
        "model_name": "gemini-2.5-pro-preview-06-05",
        "max_tokens": 16384, 
        "max_workers": 8, 
    },
    "gemini-2.5-flash": {
        "api_key": WEB_LLM_KEY,
        "api_version": "",
        "base_url": WEB_LLM_BASE_URL,
        "model_name": "gemini-2.5-flash-preview-05-20",
        "max_tokens": 16384,
        "max_workers": 8,
    },
}

class WebLLMClient:
    """支持联网的LLM客户端"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.config = WEB_LLM_CONFIGS[model_name]
        self.url = self.config["base_url"] + self.config["api_key"]
    
    def generate(self, messages: list) -> str:
        """调用联网LLM生成回复，对速率限制错误无限重试"""
        max_retries = 3  # 普通错误的最大重试次数
        retry_count = 0
        base_wait_time = 1.0  # 基础等待时间
        
        while True:  # 速率限制错误时无限循环
            try:
                response = requests.post(
                    url=self.url,
                    json={
                        "model": self.config["model_name"],
                        "messages": messages,
                        "tools": [{"type": "google_search"}]
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=300
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("choices", [{}])[0].get("message", {}).get("content", "")
                elif response.status_code == 429:
                    # HTTP 429是速率限制错误码
                    raise Exception(f"Rate limit exceeded: {response.text}")
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
            except Exception as e:
                error_msg = str(e)
                is_rate_limit = 'reach token limit' in error_msg
                
                if is_rate_limit:
                    # 速率限制错误：无限重试，指数退避
                    retry_count += 1
                    wait_time = min(base_wait_time * (2 ** min(retry_count-1, 6)), 300)  # 最大等待5分钟
                    print(f"{self.model_name}速率限制 (第{retry_count}次重试): {e}, 等待{wait_time:.1f}秒...")
                    time.sleep(wait_time)
                    continue
                else:
                    # 其他错误：有限重试
                    retry_count += 1
                    if retry_count <= max_retries:
                        wait_time = base_wait_time * retry_count
                        print(f"调用{self.model_name}失败 (尝试{retry_count}/{max_retries}): {e}, 等待{wait_time:.1f}秒重试")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"{self.model_name}客户端调用最终失败: {e}")

def build_web_llms():
    """返回两个支持联网的LLM客户端"""
    return [
        WebLLMClient("gemini-2.5-pro"),
        WebLLMClient("gemini-2.5-flash")
    ]

def build_llm(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
):
    """
    根据 OPENAI_PROVIDER 返回 ChatOpenAI 或 AzureChatOpenAI。

    - model:   可覆盖默认模型 / deployment 名
    - temperature: 覆盖默认温度
    """
    _temp = TEMPERATURE if temperature is None else temperature
    _model = model or DEFAULT_MODEL

    if OPENAI_PROVIDER == "azure":
        return AzureChatOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            openai_api_version=AZURE_OPENAI_API_VERSION,
            openai_api_key=AZURE_OPENAI_API_KEY,
            openai_api_type="azure",
            model=AZURE_OPENAI_DEPLOYMENT_NAME or _model,
            max_tokens=MAX_TOKENS,
            temperature=_temp,
        )
    # fall back to官方 OpenAI
    return ChatOpenAI(
        model=_model,
        openai_api_key=OPENAI_API_KEY,
        max_tokens=MAX_TOKENS,
        temperature=_temp,
    )


def build_test_model(model_name: str):
    """
    从evaluation_models.yaml文件读取模型配置，构建测试模型。
    支持默认配置和模型特定配置的覆盖机制。
    
    配置要求：
    - 必需字段：api_key, max_tokens, temperature（必须在每个模型中明确指定）
    - 可选字段：azure_endpoint, api_version（可使用defaults中的默认值）
    
    Args:
        model_name: 模型名称，用于从yaml文件中查找对应配置
        
    Returns:
        AzureChatOpenAI: 配置好的模型实例
        
    Raises:
        FileNotFoundError: 当evaluation_models.yaml文件不存在时
        KeyError: 当指定的model_name在配置文件中不存在时
        yaml.YAMLError: 当yaml文件格式错误时
        ValueError: 当配置文件格式不正确或缺少必需字段时
    """
    yaml_file = Path("evaluation_models.yaml")
    
    if not yaml_file.exists():
        raise FileNotFoundError(f"配置文件 {yaml_file} 不存在")
    
    try:
        with open(yaml_file, 'r', encoding='utf-8') as f:
            full_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"解析yaml文件失败: {e}")
    
    # 验证配置文件结构
    if not isinstance(full_config, dict):
        raise ValueError("配置文件格式错误：根节点应为字典")
    
    if 'defaults' not in full_config:
        raise ValueError("配置文件缺少 'defaults' 部分")
    
    if 'models' not in full_config:
        raise ValueError("配置文件缺少 'models' 部分")
    
    defaults = full_config['defaults']
    models_config = full_config['models']
    
    if model_name not in models_config:
        available_models = list(models_config.keys())
        raise KeyError(f"模型 '{model_name}' 不存在于配置文件中。可用模型: {available_models}")
    
    model_config = models_config[model_name]
    
    # 合并默认配置和模型特定配置（模型配置覆盖默认值）
    final_config = {}
    final_config.update(defaults)  # 先设置默认值
    final_config.update(model_config)  # 模型配置覆盖默认值
    
    # 验证必需的配置项
    required_fields = ['api_key', 'max_tokens', 'temperature']  # 这些字段必须在模型配置中明确指定
    missing_fields = [field for field in required_fields if field not in final_config]
    if missing_fields:
        raise ValueError(f"模型 '{model_name}' 缺少必需的配置项: {missing_fields}")
    
    # 验证默认配置字段存在
    if 'azure_endpoint' not in final_config:
        raise ValueError("缺少 azure_endpoint 配置（请检查 defaults 部分）")
    if 'api_version' not in final_config:
        raise ValueError("缺少 api_version 配置（请检查 defaults 部分）")
    
    # 构建AzureChatOpenAI实例
    return AzureChatOpenAI(
        azure_endpoint=final_config['azure_endpoint'],
        openai_api_version=final_config['api_version'],
        openai_api_key=final_config['api_key'],
        openai_api_type="azure",
        model=model_name,  # 使用model_name作为deployment名称
        max_tokens=final_config['max_tokens'],  # 必须在模型配置中指定
        temperature=final_config['temperature'],  # 必须在模型配置中指定
    )


def save_csv(df: pd.DataFrame, out_path: str | Path) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[✓] Saved → {out_path}")

def read_csv(file_path: str | Path) -> pd.DataFrame:
    return pd.read_csv(file_path, encoding="utf-8-sig")


def load_text(file_path: str | Path) -> str:
    return Path(file_path).read_text(encoding="utf-8")


def retry_async(
    attempts: int = 3, min_wait: float = 1.0, max_wait: float = 6.0
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """十分快速的重试装饰器"""
    return retry(
        stop=stop_after_attempt(attempts),
        wait=wait_random_exponential(min=min_wait, max=max_wait),
    )

def post_process_json(raw: str) -> str:
    """
    处理 JSON 字符串，确保符合 JSON 格式
    """
    if raw.startswith("```json") and raw.endswith("```"):
        raw = raw[len("```json"):-len("```")]
    return raw



def split_text_by_headers(text: str, max_size: int = BLOCK_SIZE) -> list[str]:
    """
    将markdown文本按标题拆分成不超过max_size的块
    1. 首先检索出所有一级、二级、三级标题的index
    2. 根据这些index进行组装block
    3. 如果超过block_size则回退到上一个index
    4. 验证所有block拼接后等于原文本
    """
    lines = text.split('\n')
    
    # 第一步：找到所有标题行的index
    header_indices = []
    for i, line in enumerate(lines):
        # 检查是否是标题行（一级、二级、三级标题）
        if line.startswith('#') and (
            line.startswith('# ') or 
            line.startswith('## ') or 
            line.startswith('### ')
        ):
            header_indices.append(i)
    
    # 如果没有标题，直接按大小分割
    if not header_indices:
        blocks = []
        current_block = []
        current_size = 0
        
        for line in lines:
            line_size = len(line) + 1  # +1 for newline
            if current_size + line_size > max_size and current_block:
                blocks.append('\n'.join(current_block))
                current_block = [line]
                current_size = line_size
            else:
                current_block.append(line)
                current_size += line_size
        
        if current_block:
            blocks.append('\n'.join(current_block))
        
        # 验证
        reconstructed_text = '\n'.join(blocks)
        assert reconstructed_text == text, "分块后重构的文本与原文本不一致"
        return blocks
    
    # 添加文档开始和结束的虚拟index，方便处理
    all_indices = [0] + header_indices + [len(lines)]
    
    blocks = []
    current_start = 0
    
    # 第二步：根据标题index组装block
    for i in range(1, len(all_indices)):
        current_end = all_indices[i]
        
        # 尝试构建从current_start到current_end的block
        candidate_lines = lines[current_start:current_end]
        candidate_text = '\n'.join(candidate_lines)
        
        # 如果超过大小限制
        if len(candidate_text) > max_size:
            # 如果current_start就是前一个分割点，说明单个段落太大，强制分割
            if current_start == all_indices[i-1]:
                blocks.append(candidate_text)
                current_start = current_end
            else:
                # 回退到上一个标题，先保存之前的内容
                prev_lines = lines[current_start:all_indices[i-1]]
                if prev_lines:  # 确保不为空
                    blocks.append('\n'.join(prev_lines))
                current_start = all_indices[i-1]
                
                # 重新处理当前段落
                current_lines = lines[current_start:current_end]
                current_text = '\n'.join(current_lines)
                blocks.append(current_text)
                current_start = current_end
        else:
            # 如果是最后一个，直接添加并更新current_start
            if i == len(all_indices) - 1:
                if candidate_lines:  # 确保不为空
                    blocks.append(candidate_text)
                current_start = current_end  # 重要：更新current_start，避免重复处理
            # 否则继续累积，在下一轮检查
    
    # 只有当还有未处理的内容时才添加
    if current_start < len(lines):
        remaining_lines = lines[current_start:]
        if remaining_lines:  # 确保不为空
            blocks.append('\n'.join(remaining_lines))
    
    # 过滤掉空的blocks
    blocks = [block for block in blocks if block.strip()]
    
    # 第三步：验证所有block拼接后等于原文本
    reconstructed_text = '\n'.join(blocks)
    assert reconstructed_text == text, f"分块后重构的文本与原文本不一致\n原文长度: {len(text)}\n重构长度: {len(reconstructed_text)}"
    
    return blocks