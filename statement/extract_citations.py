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
步骤 1：提取引用表述
从报告中提取所有引用表述及其链接，基于URL生成唯一的随机ID
输出—— citations.csv : ID, statement, url
"""
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd

from langchain_core.prompts import PromptTemplate

from statement.prompts import PROMPT_EXTRACT_CITATIONS
from utils import build_llm, save_csv, post_process_json, load_text, split_text_by_headers
from cache_utils import load_or_create_url_cache, get_or_create_id_for_url, save_url_cache


def extract_citations_from_text(report_text: str, out_csv: str | Path, cache_file: str = "url_cache.csv") -> pd.DataFrame:
    """主函数：接受文本内容 → 分块 → 调用 LLM → 基于URL生成ID → 输出 CSV"""
    # 将文本分块处理
    text_blocks = split_text_by_headers(report_text)
    print(f"[✓] 文本已分割为 {len(text_blocks)} 个块")
    
    llm = build_llm()
    system_prompt = PromptTemplate.from_template(PROMPT_EXTRACT_CITATIONS)
    chain = system_prompt | llm

    # 加载URL缓存
    url_cache = load_or_create_url_cache(cache_file)
    
    all_rows = []
    
    # 对每个文本块进行处理
    for i, block in enumerate(text_blocks, 1):
        print(f"[→] 处理第 {i}/{len(text_blocks)} 块...")
        
        retry = True
        while retry:
            try:
                raw = chain.invoke({"report": block})
                post_processed = post_process_json(raw.content)
                data = json.loads(post_processed)

                for item in data:
                    url = item["url"].strip()
                    statement = item["statement"].strip()
                    
                    # 基于URL获取或创建随机ID
                    random_id, url_cache = get_or_create_id_for_url(url, url_cache)
                    
                    all_rows.append({
                        "ID": random_id,
                        "statement": statement,
                        "url": url,
                    })
                
                retry = False
            except Exception as e:
                if "reach token limit" in str(e):
                    print(f"[!] 速率墙，重试... {e}")
                    retry = True
                else:
                    print(f"[!] 其他错误，不重试... {e}")
                    retry = False

    # 保存URL缓存
    save_url_cache(url_cache, cache_file)

    df = pd.DataFrame(all_rows)
    save_csv(df, out_csv)
    print(f"[✓] 从 {len(text_blocks)} 个文本块中提取到 {len(df)} 条引用表述")
    return df


def extract_citations(report_path: str | Path, out_csv: str | Path, cache_file: str = "url_cache.csv") -> pd.DataFrame:
    """原有函数：读文件 → 调用extract_citations_from_text处理"""
    report_text = load_text(report_path)
    return extract_citations_from_text(report_text, out_csv, cache_file)