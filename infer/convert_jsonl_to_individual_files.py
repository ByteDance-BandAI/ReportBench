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

#!/usr/bin/env python3
"""
将JSONL文件的每一行转换为独立的JSON文件
按model_name分组到不同的子目录中
"""

import json
import os
import argparse
from pathlib import Path
from typing import Dict, Any


def create_individual_json(data: Dict[str, Any], output_dir: Path, model_name: str, arxiv_id: str) -> None:
    """
    创建独立的JSON文件
    
    Args:
        data: 原始数据字典
        output_dir: 输出目录
        model_name: 模型名称
        arxiv_id: arxiv ID
    """
    # 创建模型子目录
    model_dir = output_dir / model_name
    model_dir.mkdir(parents=True, exist_ok=True)
    
    # 提取需要的字段
    output_data = {
        "title": data.get("title", ""),
        "prompt": data.get("prompt", ""),
        "response": data.get("response", "")
    }
    
    # 创建JSON文件路径
    json_file_path = model_dir / f"{arxiv_id}.json"
    
    # 写入JSON文件
    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"创建文件: {json_file_path}")


def process_jsonl_file(input_path: str, output_dir: str) -> None:
    """
    处理JSONL文件
    
    Args:
        input_path: 输入JSONL文件路径
        output_dir: 输出目录路径
    """
    input_path = Path(input_path)
    output_path = Path(output_dir)
    
    # 检查输入文件是否存在
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")
    
    # 创建输出目录
    output_path.mkdir(parents=True, exist_ok=True)
    
    processed_count = 0
    error_count = 0
    
    # 逐行读取JSONL文件
    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
                
            try:
                # 解析JSON
                data = json.loads(line)
                
                # 提取必要字段
                model_name = data.get("model_name", "unknown_model")
                arxiv_id = data.get("arxiv_id", f"unknown_{line_num}")
                
                # 清理model_name中的特殊字符，确保可以作为目录名
                model_name = "".join(c for c in model_name if c.isalnum() or c in ('-', '_', '.'))
                if not model_name:
                    model_name = "unknown_model"
                
                # 创建独立JSON文件
                create_individual_json(data, output_path, model_name, str(arxiv_id))
                processed_count += 1
                
            except json.JSONDecodeError as e:
                print(f"错误: 第{line_num}行JSON解析失败: {e}")
                error_count += 1
            except Exception as e:
                print(f"错误: 处理第{line_num}行时发生错误: {e}")
                error_count += 1
    
    print(f"\n处理完成:")
    print(f"成功处理: {processed_count} 行")
    print(f"错误: {error_count} 行")
    print(f"输出目录: {output_path.absolute()}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="将JSONL文件的每一行转换为独立的JSON文件，按model_name分组"
    )
    
    parser.add_argument(
        "--input",
        required=True,
        help="输入JSONL文件路径"
    )
    
    parser.add_argument(
        "--output",
        required=True,
        help="输出目录路径"
    )
    
    args = parser.parse_args()
    
    try:
        process_jsonl_file(args.input, args.output)
    except Exception as e:
        print(f"处理失败: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 