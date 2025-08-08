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
步骤 4 & 5：判断是否一致 + 计算 Match Rate
输出—— final.csv : ID, statement, source_sentence, url, match, reason
终端额外打印 Match Rate (%)
"""
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
from langchain_core.prompts import PromptTemplate
from tqdm import tqdm

from statement.prompts import PROMPT_VERIFY_ALIGNMENT
from utils import build_llm, save_csv, post_process_json


def check_alignment(statement: str, source_sentence: str, llm) -> tuple[bool, str]:
    prompt = PromptTemplate.from_template(PROMPT_VERIFY_ALIGNMENT)
    resp = (prompt | llm).invoke(
        {"statement": statement, "source_sentence": source_sentence}
    )
    post_processed = post_process_json(resp.content)
    data = json.loads(post_processed)
    return bool(data["match"]), data["reason"]


def verify(df_match: pd.DataFrame, out_csv: str | Path = "final.csv") -> float:
    llm = build_llm()
    results = []

    for _, row in tqdm(df_match.iterrows(), total=len(df_match), desc="Verifying"):
        retry = True
        fail = False
        while retry:
            try:
                match, reason = check_alignment(row.statement, row.source_sentence, llm)
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

        results.append(
            {
                "ID": row.ID,
                "statement": row.statement,
                "source_sentence": row.source_sentence,
                "url": row.url,
                "match": match,
                "reason": reason,
            }
        )

    df_final = pd.DataFrame(results)
    save_csv(df_final, out_csv)

    # 计算详细统计
    if not df_final.empty:
        match_count = df_final.match.sum()
        no_match_count = len(df_final) - match_count
        total_statements = len(df_final)
        match_rate = match_count / total_statements if total_statements > 0 else 0.0
        
        print(f"\n==============================")
        print(f"文本对齐验证结果:")
        print(f"总表述数: {total_statements}")
        print(f"对齐匹配: {match_count} ({match_count/total_statements:.1%})")
        print(f"对齐不匹配: {no_match_count} ({no_match_count/total_statements:.1%})")
        print(f"匹配率 (Match Rate): {match_rate:.2%}")
        print(f"==============================\n")
    else:
        match_rate = 0.0
        print(f"\n==============================")
        print(f"文本对齐验证结果: 无数据")
        print(f"==============================\n")
    
    return match_rate