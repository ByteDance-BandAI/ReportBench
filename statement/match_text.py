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
步骤 3：从原文中找到与表述最相近的句子
输出—— matched.csv : ID, statement, source_sentence, url
"""
import re
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
from langchain_core.prompts import PromptTemplate
from tqdm import tqdm

from statement.prompts import PROMPT_MATCH_SENTENCE
from utils import build_llm, save_csv

MAX_SOURCE_LEN = 262144

def _split_sentences(text: str) -> list[str]:
    """简易句子切分（中英文混合）"""
    return re.split(r"(?<=[。？！.!?])\s*", text)


def find_best_sentence(statement: str, source_text: str, llm) -> str:
    """调用 LLM 选最匹配的句子"""
    prompt = PromptTemplate.from_template(PROMPT_MATCH_SENTENCE)
    chain = prompt | llm
    resp = chain.invoke({"statement": statement, "source_text": source_text[:MAX_SOURCE_LEN]})
    return resp.content.strip()


def match_sentences(
    df_citations: pd.DataFrame,
    raw_dir: str | Path = "raw_texts",
    out_csv: str | Path = "matched.csv",
) -> pd.DataFrame:
    llm = build_llm()
    rows = []

    for _, row in tqdm(df_citations.iterrows(), total=len(df_citations), desc="Matching"):
        random_id = row.ID
        source_path = Path(raw_dir) / f"{random_id}.txt"
        
        if not source_path.exists():
            print(f"警告：文件 {source_path} 不存在，跳过")
            continue
            
        source_text = source_path.read_text(encoding="utf-8")

        retry = True
        fail = False
        while retry:
            try:
                best = find_best_sentence(row.statement, source_text, llm)
                retry = False
            except Exception as e:
                if "reach token limit" in str(e):
                    print(f"[!] 速率墙，重试... {e}")
                    retry = True
                else:
                    print(f"[!] 其他错误，不重试... {e}")
                    retry = False
                    fail = True

        if fail:
            continue

        rows.append(
            {
                "ID": row.ID,
                "statement": row.statement,
                "source_sentence": best,
                "url": row.url,
            }
        )

    df_match = pd.DataFrame(rows)
    save_csv(df_match, out_csv)
    return df_match