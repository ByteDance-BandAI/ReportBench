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
# -*- coding: utf-8 -*-
"""
脚本用于处理ReportBench数据，使用eval.txt模板生成新的prompt_new列
"""

import json
import os
from pathlib import Path

def read_template(template_path):
    """读取模板文件"""
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()

def apply_template(template, prompt, title):
    """应用模板，替换prompt和title占位符"""
    # 先替换{prompt}占位符
    result = template.replace("{prompt}", prompt)
    # 再替换{title}占位符
    result = result.replace("{title}", title)
    return result

def process_jsonl_file(input_file, output_file, template_path):
    """处理JSONL文件，添加prompt_new列"""
    
    # 读取模板
    template = read_template(template_path)
    
    processed_count = 0
    
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8') as outfile:
        
        for line_num, line in enumerate(infile, 1):
            try:
                # 解析JSON行
                data = json.loads(line.strip())
                
                # 获取prompt和title
                prompt = data.get('prompt', '')
                title = data.get('title', '')
                
                # 应用模板生成新的prompt
                prompt_new = apply_template(template, prompt, title)
                
                # 添加新的prompt_new字段
                data['prompt_new'] = prompt_new
                
                # 写入处理后的数据
                outfile.write(json.dumps(data, ensure_ascii=False) + '\n')
                
                processed_count += 1
                
                if processed_count % 10 == 0:
                    print(f"已处理 {processed_count} 条记录...")
                
            except json.JSONDecodeError as e:
                print(f"第{line_num}行JSON解析错误: {e}")
                continue
            except Exception as e:
                print(f"第{line_num}行处理错误: {e}")
                continue
    
    print(f"处理完成！总共处理了 {processed_count} 条记录")
    print(f"输出文件: {output_file}")

def main():
    """主函数"""
    # 定义文件路径
    input_file = "ReportBench_v1.0_en.jsonl"
    output_file = "ReportBench_v1.0_en_processed.jsonl"
    template_path = "prompt_template/eval.txt"
    
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        print(f"错误: 输入文件 {input_file} 不存在")
        return
    
    # 检查模板文件是否存在
    if not os.path.exists(template_path):
        print(f"错误: 模板文件 {template_path} 不存在")
        return
    
    print("开始处理数据...")
    print(f"输入文件: {input_file}")
    print(f"模板文件: {template_path}")
    print(f"输出文件: {output_file}")
    print("-" * 50)
    
    # 处理文件
    process_jsonl_file(input_file, output_file, template_path)
    
    # 显示处理前后的示例
    print("\n" + "="*50)
    print("处理示例对比:")
    print("="*50)
    
    # 读取第一条记录显示效果
    with open(input_file, 'r', encoding='utf-8') as f:
        first_line = f.readline()
        original_data = json.loads(first_line)
    
    with open(output_file, 'r', encoding='utf-8') as f:
        first_line = f.readline()
        processed_data = json.loads(first_line)
    
    print("原始prompt:")
    print(original_data.get('prompt', ''))
    print("\n处理后的prompt_new:")
    print(processed_data.get('prompt_new', ''))

if __name__ == "__main__":
    main() 