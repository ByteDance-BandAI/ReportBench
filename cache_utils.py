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
URL缓存和ID生成工具模块
提供URL标准化、随机ID生成、URL缓存管理等功能
"""

import pandas as pd
import string
import random
from urllib.parse import urlparse
from pathlib import Path


def generate_random_id(length=10):
    """生成随机字母数字ID"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def normalize_url(url: str) -> str:
    """标准化URL，移除锚点等，用于重复检测"""
    parsed = urlparse(url)
    # 移除fragment（锚点）和query参数中的特定部分
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def load_or_create_url_cache(cache_file: str = "url_cache.csv") -> pd.DataFrame:
    """加载或创建URL缓存表"""
    try:
        return pd.read_csv(cache_file)
    except FileNotFoundError:
        return pd.DataFrame(columns=['url', 'normalized_url', 'random_id'])


def get_or_create_id_for_url(url: str, url_cache: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    """获取或创建URL对应的随机ID"""
    normalized = normalize_url(url)
    
    # 检查是否已存在
    existing = url_cache[url_cache['normalized_url'] == normalized]
    if not existing.empty:
        return existing.iloc[0]['random_id'], url_cache
    
    # 创建新的随机ID
    random_id = generate_random_id()
    # 确保ID唯一
    while random_id in url_cache['random_id'].values:
        random_id = generate_random_id()
    
    # 添加到缓存表
    new_row = pd.DataFrame({
        'url': [url],
        'normalized_url': [normalized], 
        'random_id': [random_id]
    })
    url_cache = pd.concat([url_cache, new_row], ignore_index=True)
    
    return random_id, url_cache


def save_url_cache(url_cache: pd.DataFrame, cache_file: str = "url_cache.csv"):
    """保存URL缓存到文件"""
    url_cache.to_csv(cache_file, index=False)
    print(f"[✓] URL缓存已保存到 {cache_file}")


def get_url_id_with_cache(url: str, cache_file: str = "url_cache.csv") -> str:
    """便捷函数：获取URL的ID，自动处理缓存"""
    url_cache = load_or_create_url_cache(cache_file)
    random_id, updated_cache = get_or_create_id_for_url(url, url_cache)
    save_url_cache(updated_cache, cache_file)
    return random_id 