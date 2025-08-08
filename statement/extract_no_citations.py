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
步骤 1b：提取无引用表述
从报告中提取所有没有引用支撑的事实性表述
输出—— no_citations.csv : ID, statement
"""
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd

from langchain_core.prompts import PromptTemplate

from statement.prompts import PROMPT_EXTRACT_NO_CITATIONS
from utils import build_llm, save_csv, post_process_json, load_text, split_text_by_headers


def extract_no_citations_from_text(
    report_text: str,
    df_citations: pd.DataFrame,
    out_csv: str | Path = "no_citations.csv"
) -> pd.DataFrame:
    """主函数：接受文本内容 → 分块 → 调用 LLM → 提取无引用表述 → 输出 CSV"""
    
    # 将文本分块处理
    text_blocks = split_text_by_headers(report_text)
    print(f"[✓] 文本已分割为 {len(text_blocks)} 个块")
    
    llm = build_llm()

    # 准备已有引用的表述列表，供LLM排除
    cited_statements = df_citations['statement'].tolist() if not df_citations.empty else []
    cited_statements_text = "\n".join([f"- {stmt}" for stmt in cited_statements])
    
    system_prompt = PromptTemplate.from_template(PROMPT_EXTRACT_NO_CITATIONS)
    chain = system_prompt | llm

    all_rows = []
    statement_counter = 1
    
    # 对每个文本块进行处理
    for i, block in enumerate(text_blocks, 1):
        print(f"[→] 处理第 {i}/{len(text_blocks)} 块...")
        
        retry = True
        while retry:
            try:
                raw = chain.invoke({
                    "report": block,
                    "cited_statements": cited_statements_text
                })
                post_processed = post_process_json(raw.content)
                data = json.loads(post_processed)

                for item in data:
                    statement = item["statement"].strip()
                    all_rows.append({
                        "ID": f"NC_{statement_counter:03d}",  # NC = No Citation
                        "statement": statement,
                    })
                    statement_counter += 1

                retry = False
            except Exception as e:
                if "reach token limit" in str(e):
                    print(f"[!] 速率墙，重试... {e}")
                    retry = True
                else:
                    print(f"[!] 其他错误，不重试... {e}")
                    retry = False

    df = pd.DataFrame(all_rows)
    save_csv(df, out_csv)
    print(f"[✓] 从 {len(text_blocks)} 个文本块中提取到 {len(df)} 条无引用表述")
    return df


def extract_no_citations(
    report_path: str | Path, 
    df_citations: pd.DataFrame,
    out_csv: str | Path = "no_citations.csv"
) -> pd.DataFrame:
    """原有函数：读文件 → 调用extract_no_citations_from_text处理"""
    report_text = load_text(report_path)
    return extract_no_citations_from_text(report_text, df_citations, out_csv) 