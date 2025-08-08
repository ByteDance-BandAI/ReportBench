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
主入口：批量处理包含JSON文件的目录
"""

import argparse
import json
import re
from pathlib import Path

from statement.extract_citations import extract_citations_from_text
from statement.extract_no_citations import extract_no_citations_from_text
from statement.scrape_content import scrape_all
from statement.match_text import match_sentences
from statement.verify_alignment import verify

from utils import read_csv, save_csv


def extract_arxiv_id_from_filename(filename: str) -> str:
    """从文件名中提取arxiv_id"""
    # arxiv_id格式通常为 YYMM.NNNNN，如 2101.01507
    pattern = r'(\d{4}\.\d{5})'
    match = re.search(pattern, filename)
    if match:
        return match.group(1)
    else:
        # 如果没有找到标准格式，尝试更宽松的匹配
        pattern = r'(\d{4}\.\d+)'
        match = re.search(pattern, filename)
        if match:
            return match.group(1)
    return None


def process_single_json(json_file: Path, output_dir: Path, include_no_citations: bool = True):
    """处理单个JSON文件"""
    print(f"\n==> Processing JSON file: {json_file}")
    
    # 从文件名中提取arxiv_id
    arxiv_id = extract_arxiv_id_from_filename(json_file.name)
    if not arxiv_id:
        print(f"[!] 无法从文件名中提取arxiv_id: {json_file}")
        return
    
    # 读取JSON文件
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[!] 读取JSON文件失败: {e}")
        return
    
    # 灵活查找response字段
    response_text = None
    
    # 候选字段名称
    candidate_fields = ['response', 'content', 'text', 'message', 'output', 'result']
    
    # 首先尝试直接找到候选字段
    for field in candidate_fields:
        if field in data and isinstance(data[field], str) and len(data[field].strip()) > 50:
            response_text = data[field]
            print(f"[✓] 找到response字段: {field}")
            break
    
    # 如果没有找到，寻找最长的字符串字段
    if not response_text:
        longest_field = None
        longest_length = 0
        
        for key, value in data.items():
            if isinstance(value, str) and len(value.strip()) > longest_length:
                longest_length = len(value.strip())
                longest_field = key
        
        if longest_field and longest_length > 50:
            response_text = data[longest_field]
            print(f"[✓] 使用最长字段作为response: {longest_field} (长度: {longest_length})")
    
    # 如果还是没有找到合适的内容
    if not response_text:
        print(f"[!] 无法找到合适的文本内容字段: {json_file}")
        print(f"[!] 可用字段: {list(data.keys())}")
        return
    
    # 创建结果目录
    results_dir = output_dir / arxiv_id
    results_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[✓] 提取的arxiv_id: {arxiv_id}")
    print(f"[✓] 文本内容长度: {len(response_text)} 字符")
    print(f"[✓] 结果文件将保存到: {results_dir}")

    # 1) 提取带引用表述
    if Path(results_dir / "citations.csv").exists():
        print(f"[!] 跳过提取带引用表述，已存在 citations.csv 文件")
        df_citations = read_csv(results_dir / "citations.csv")
    else:
        df_citations = extract_citations_from_text(response_text, results_dir / "citations.csv")

    # 新增：无引用表述处理
    if include_no_citations:
        print(f"\n==> 开始处理无引用表述...")
        
        # 1b) 提取无引用表述
        if Path(results_dir / "no_citations.csv").exists():
            print(f"[!] 跳过提取无引用表述，已存在 no_citations.csv 文件")
            df_no_citations = read_csv(results_dir / "no_citations.csv")
        else:
            df_no_citations = extract_no_citations_from_text(
                response_text, 
                df_citations, 
                results_dir / "no_citations.csv"
            )
        
        if not df_no_citations.empty:
            # 3b) 使用联网LLM验证无引用表述
            from statement.verify_no_citations_web import verify_no_citations_web
            if Path(results_dir / "no_citations_web_final.csv").exists():
                print(f"[!] 跳过验证无引用表述，已存在 no_citations_web_final.csv 文件")
            else:
                df_verification, df_final = verify_no_citations_web(
                    df_no_citations,
                    results_dir / "no_citations_web_verification.csv",
                    results_dir / "no_citations_web_final.csv"
                )
        else:
            print("[!] 未找到无引用表述，跳过相关处理")

    # 2) 抓取网页 (cache文件保留在根目录)
    scrape_all(df_citations, "raw_texts")

    # 3) 匹配句子
    if Path(results_dir / "matched.csv").exists():
        print(f"[!] 跳过匹配，已存在 matched.csv 文件")
        df_match = read_csv(results_dir / "matched.csv")
    else:
        df_match = match_sentences(df_citations, "raw_texts", results_dir / "matched.csv")

    # 4+5) 校对并计算 Match Rate
    if Path(results_dir / "final.csv").exists():
        print(f"[!] 跳过验证，已存在 final.csv 文件")
    else:
        verify(df_match, results_dir / "final.csv")


def run_batch(input_dir: str | Path, output_dir: str | Path = "results", include_no_citations: bool = True):
    """处理目录中的所有JSON文件"""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    if not input_path.exists() or not input_path.is_dir():
        print(f"[!] 输入目录不存在或不是目录: {input_path}")
        return
    
    # 查找所有JSON文件
    json_files = list(input_path.glob("*.json"))
    
    if not json_files:
        print(f"[!] 在目录 {input_path} 中未找到任何JSON文件")
        return
    
    print(f"[✓] 找到 {len(json_files)} 个JSON文件")
    
    # 创建输出目录
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 处理每个JSON文件
    for json_file in json_files:
        try:
            process_single_json(json_file, output_path, include_no_citations)
        except Exception as e:
            print(f"[!] 处理文件 {json_file} 时出错: {e}")
            continue
    
    print(f"\n[✓] 批处理完成，结果保存在: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LangChain Citation Audit Workflow - JSON Batch Processing")
    parser.add_argument("input_dir", help="Directory containing JSON files (each with arxiv_id and response fields)")
    parser.add_argument(
        "--output-dir", 
        default="results",
        help="Output directory for results (default: results)"
    )
    parser.add_argument(
        "--skip-no-citations", 
        action="store_true", 
        help="Skip processing of non-cited statements"
    )
    args = parser.parse_args()

    # 直接调用批处理功能
    run_batch(args.input_dir, args.output_dir, include_no_citations=not args.skip_no_citations)