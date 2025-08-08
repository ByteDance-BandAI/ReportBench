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
批量推理脚本 - 对ReportBench数据进行多模型推理（并行版本）

支持功能：
1. 读取ReportBench_v0.7_sample_150_sheet1.csv文件
2. 使用四个模型进行批量推理（支持并行加速）
3. 输出结果为jsonl格式
4. 支持进度显示和错误恢复
5. 线程安全的并行处理和进度更新
6. 支持模板变量映射和多列数据组装
"""

import pandas as pd
import json
import time
import argparse
import threading
import random
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils import build_test_model
from langchain.schema import HumanMessage

# 四个可用模型
MODELS = [
    "o3-2025-04-16",
    "o4-mini-2025-04-16", 
    "gemini-2.5-pro-preview-05-06",
    "gcp-claude4-opus"
]

# 可用的prompt列
PROMPT_COLUMNS = [
    "中文prompt",
    "sentence", 
    "paragraph",
    "detail"
]

# 线程锁用于文件写入和进度更新
file_lock = threading.Lock()

def extract_template_variables(template: str) -> List[str]:
    """从模板中提取所有变量名"""
    # 使用正则表达式匹配 {变量名} 模式
    pattern = r'\{([^}]+)\}'
    variables = re.findall(pattern, template)
    unique_variables = list(set(variables))  # 去重
    print(f"📋 提取到模板变量: {unique_variables}")
    return unique_variables

def build_column_mapping(variables: List[str], csv_columns: List[str]) -> Dict[str, str]:
    """建立模板变量和CSV列的映射关系"""
    print(f"🔗 建立变量映射关系...")
    mapping = {}
    
    for var in variables:
        # 首先尝试找同名列
        if var in csv_columns:
            mapping[var] = var
            print(f"  ✅ {var} -> {var} (同名列)")
        else:
            # 找不到同名列，显示所有可用列并请求用户输入
            print(f"\n❌ 找不到变量 '{var}' 对应的同名列")
            print(f"📊 可用的CSV列:")
            for i, col in enumerate(csv_columns, 1):
                print(f"  {i:2d}. {col}")
            
            while True:
                user_input = input(f"\n请为变量 '{var}' 选择对应的列（输入列名或序号）: ").strip()
                
                if not user_input:
                    print("❌ 输入不能为空，请重新输入")
                    continue
                
                # 尝试按序号解析
                if user_input.isdigit():
                    col_index = int(user_input) - 1
                    if 0 <= col_index < len(csv_columns):
                        column_name = csv_columns[col_index]
                        mapping[var] = column_name
                        print(f"  ✅ {var} -> {column_name} (用户选择)")
                        break
                    else:
                        print(f"❌ 序号 {user_input} 超出范围，请输入1-{len(csv_columns)}之间的数字")
                        continue
                
                # 尝试按列名解析
                if user_input in csv_columns:
                    mapping[var] = user_input
                    print(f"  ✅ {var} -> {user_input} (用户选择)")
                    break
                else:
                    print(f"❌ 列名 '{user_input}' 不存在，请重新输入")
                    continue
    
    print(f"\n🎯 最终映射关系:")
    for var, col in mapping.items():
        print(f"  {var} -> {col}")
    
    return mapping

def apply_template_with_mapping(template: str, mapping: Dict[str, str], row: pd.Series) -> str:
    """使用映射关系将行数据填入模板"""
    try:
        # 准备变量值字典
        template_values = {}
        for var, col in mapping.items():
            value = row.get(col, '')
            if pd.isna(value):
                value = ''
            template_values[var] = str(value).strip()
        
        # 使用format方法填充模板
        formatted_prompt = template.format(**template_values)
        return formatted_prompt
    except Exception as e:
        print(f"❌ 模板应用失败: {e}")
        # 如果模板应用失败，返回原始模板
        return template

def is_rate_limit_error(error_message: str) -> bool:
    """判断是否为限流错误"""
    rate_limit_indicators = [
        "rate limit", "rate_limit", "ratelimit",
        "429", "too many requests", "quota exceeded",
        "throttled", "throttling", "限流", "频率限制",
        "exceed", "maximum", "limit exceeded",
        "retry after", "retry-after", "请求过于频繁",
        "concurrent requests", "请稍后重试"
    ]
    
    error_lower = error_message.lower()
    return any(indicator in error_lower for indicator in rate_limit_indicators)

def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """指数退避算法计算延迟时间"""
    # 基础延迟 * 2^重试次数 + 随机抖动
    delay = min(base_delay * (2 ** attempt), max_delay)
    # 添加10%的随机抖动，避免所有线程同时重试
    jitter = delay * 0.1 * random.random()
    return delay + jitter

def load_data(csv_path: str) -> pd.DataFrame:
    """加载CSV数据"""
    print(f"📖 加载数据文件: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"✅ 成功加载 {len(df)} 条数据")
    return df

def build_models(model_list: List[str]) -> Dict[str, Any]:
    """构建指定的模型"""
    print(f"🔧 构建模型...")
    models = {}
    
    for model_name in model_list:
        try:
            print(f"  构建模型: {model_name}")
            model = build_test_model(model_name)
            models[model_name] = model
            print(f"  ✅ {model_name} 构建成功")
        except Exception as e:
            print(f"  ❌ {model_name} 构建失败: {e}")
            models[model_name] = None
    
    successful_models = [name for name, model in models.items() if model is not None]
    print(f"✅ 成功构建 {len(successful_models)}/{len(model_list)} 个模型")
    
    if not successful_models:
        raise RuntimeError("没有可用的模型！")
    
    return models

def infer_single_with_retry(model, prompt: str, model_name: str, max_retries: int = 3, 
                           timeout: int = 60) -> Dict[str, Any]:
    """带重试机制的单次推理"""
    start_time = time.time()
    attempt = 0
    total_retry_delay = 0
    
    while True:
        try:
            attempt_start = time.time()
            response = model.invoke([HumanMessage(content=prompt)])
            attempt_end = time.time()
            
            # 成功执行
            total_time = time.time() - start_time
            return {
                "success": True,
                "response": response.content,
                "model_name": model_name,
                "response_time": round(total_time, 2),
                "timestamp": datetime.now().isoformat(),
                "error": None,
                "retry_count": attempt,
                "retry_delay": total_retry_delay
            }
            
        except Exception as e:
            error_msg = str(e)
            is_rate_limit = is_rate_limit_error(error_msg)
            
            # 判断是否需要重试
            should_retry = False
            if is_rate_limit:
                # 限流错误：无限重试
                should_retry = True
                retry_reason = "rate_limit"
            elif attempt < max_retries:
                # 其他错误：有限重试
                should_retry = True
                retry_reason = "other_error"
            
            if should_retry:
                attempt += 1
                
                # 计算退避延迟
                if is_rate_limit:
                    # 限流错误：较长的退避时间
                    base_delay = 2.0
                    max_delay = 120.0
                else:
                    # 其他错误：较短的退避时间
                    base_delay = 1.0
                    max_delay = 30.0
                
                delay = exponential_backoff(attempt - 1, base_delay, max_delay)
                total_retry_delay += delay
                
                # 等待后重试
                time.sleep(delay)
                continue
            
            # 不再重试，返回失败结果
            total_time = time.time() - start_time
            return {
                "success": False,
                "response": None,
                "model_name": model_name,
                "response_time": round(total_time, 2),
                "timestamp": datetime.now().isoformat(),
                "error": error_msg,
                "retry_count": attempt,
                "retry_delay": total_retry_delay,
                "is_rate_limit": is_rate_limit
            }

def process_single_task(task_data: Tuple[int, str, str, Dict[str, Any], Any, str, int]) -> Dict[str, Any]:
    """处理单个推理任务"""
    row_idx, model_name, prompt, base_data, model, delay, max_retries = task_data
    
    # 执行推理（带重试机制）
    result = infer_single_with_retry(model, prompt, model_name, max_retries)
    
    # 合并结果
    output_data = {**base_data, **result}
    
    # 添加短暂延迟，避免API限流
    if delay > 0:
        time.sleep(delay)
    
    return output_data

def write_result_to_file(result: Dict[str, Any], file_handle, pbar: tqdm) -> None:
    """线程安全地写入结果到文件并更新进度条"""
    with file_lock:
        file_handle.write(json.dumps(result, ensure_ascii=False) + '\n')
        file_handle.flush()
        
        # 更新进度条
        retry_count = result.get('retry_count', 0)
        retry_delay = result.get('retry_delay', 0)
        
        if result['success']:
            retry_info = f"R{retry_count}" if retry_count > 0 else ""
            pbar.set_postfix(status="✅", time=f"{result['response_time']}s", 
                           model=result['model_name'][:8], retry=retry_info)
        else:
            is_rate_limit = result.get('is_rate_limit', False)
            error_type = "限流" if is_rate_limit else "错误"
            retry_info = f"R{retry_count}" if retry_count > 0 else ""
            pbar.set_postfix(status="❌", type=error_type,
                           model=result['model_name'][:8], retry=retry_info)
        pbar.update(1)

def load_template(template_path: str) -> str:
    """加载模板文件"""
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read().strip()
        print(f"📄 加载模板: {template_path}")
        print(f"📝 模板内容预览: {template[:100]}...")
        return template
    except Exception as e:
        print(f"❌ 加载模板失败: {e}")
        raise

def apply_template(original_prompt: str, template: str) -> str:
    """应用模板到原始prompt"""
    try:
        # 使用format方法将原始prompt填入模板
        formatted_prompt = template.format(prompt=original_prompt)
        return formatted_prompt
    except Exception as e:
        print(f"❌ 模板应用失败: {e}")
        # 如果模板应用失败，返回原始prompt
        return original_prompt

def batch_infer_parallel(df: pd.DataFrame, models: Dict[str, Any], prompt_column: str, 
                        output_path: str, start_idx: int = 0, max_workers: int = 8,
                        delay_between_requests: float = 0.1, max_retries: int = 3,
                        template_path: str = None) -> None:
    """并行批量推理"""
    print(f"🚀 开始并行批量推理")
    print(f"📊 数据量: {len(df)} 条")
    print(f"🤖 模型数: {len([m for m in models.values() if m is not None])} 个")
    print(f"📝 Prompt列: {prompt_column}")
    print(f"💾 输出文件: {output_path}")
    print(f"📍 开始位置: {start_idx}")
    print(f"🔧 最大并发数: {max_workers}")
    print(f"⏱️  请求间隔: {delay_between_requests}秒")
    print(f"🔄 最大重试次数: {max_retries} (限流错误无限重试)")
    
    # 加载模板和建立映射关系（如果提供）
    template = None
    column_mapping = {}
    if template_path:
        template = load_template(template_path)
        
        # 提取模板变量
        variables = extract_template_variables(template)
        
        if variables:
            # 建立列映射关系
            csv_columns = list(df.columns)
            column_mapping = build_column_mapping(variables, csv_columns)
            print(f"📄 使用模板: 已启用，映射 {len(variables)} 个变量")
        else:
            print(f"📄 使用模板: 已启用，无需变量映射")
    else:
        print(f"📄 使用模板: 无")
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 如果是续传，先读取已有结果
    processed_items = set()
    if output_file.exists() and start_idx > 0:
        print(f"📖 检测到现有输出文件，加载已处理项目...")
        with open(output_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    processed_items.add((data['row_index'], data['model_name']))
        print(f"✅ 发现 {len(processed_items)} 个已处理项目")
    
    # 准备所有任务
    tasks = []
    available_models = [(name, model) for name, model in models.items() if model is not None]
    
    for idx, row in df.iterrows():
        if idx < start_idx:
            continue
            
        # 获取prompt
        prompt = row[prompt_column]
        if pd.isna(prompt) or not str(prompt).strip():
            print(f"⚠️  第{idx}行prompt为空，跳过")
            continue
        
        prompt = str(prompt).strip()
        
        # 应用模板（如果提供）
        original_prompt = prompt
        if template and column_mapping:
            # 使用映射关系应用模板
            prompt = apply_template_with_mapping(template, column_mapping, row)
        elif template:
            # 兼容旧版本，只有prompt变量的情况
            prompt = apply_template(original_prompt, template)
        
        # 准备基础数据
        base_data = {
            "row_index": idx,
            "arxiv_id": row.get('arxiv_id', ''),
            "title": row.get('title', ''),
            "prompt_column": prompt_column,
            "original_prompt": original_prompt,
            "prompt": prompt,
            "prompt_length": len(prompt),
            "template_used": template_path is not None,
            "template_variables": list(column_mapping.keys()) if column_mapping else []
        }
        
        # 为每个模型创建任务
        for model_name, model in available_models:
            # 检查是否已经处理过
            if (idx, model_name) in processed_items:
                continue
                
            task_data = (idx, model_name, prompt, base_data, model, delay_between_requests, max_retries)
            tasks.append(task_data)
    
    if not tasks:
        print("✅ 所有任务都已完成，无需处理")
        return
    
    print(f"📋 准备处理 {len(tasks)} 个任务")
    
    # 打开输出文件（追加模式）
    mode = 'a' if start_idx > 0 else 'w'
    with open(output_file, mode, encoding='utf-8') as f:
        
        # 创建进度条
        pbar = tqdm(total=len(tasks), desc="并行推理进度", 
                   initial=0, ncols=120)
        
        # 使用ThreadPoolExecutor进行并行处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_task = {executor.submit(process_single_task, task): task for task in tasks}
            
            # 处理完成的任务
            for future in as_completed(future_to_task):
                try:
                    result = future.result()
                    write_result_to_file(result, f, pbar)
                    
                except Exception as e:
                    # 处理任务执行异常
                    task_data = future_to_task[future]
                    row_idx, model_name = task_data[0], task_data[1]
                    
                    error_result = {
                        "row_index": row_idx,
                        "model_name": model_name,
                        "success": False,
                        "response": None,
                        "response_time": 0,
                        "timestamp": datetime.now().isoformat(),
                        "error": f"Task execution failed: {str(e)}"
                    }
                    
                    with file_lock:
                        pbar.set_postfix(status="❌", error=str(e)[:20], model=model_name[:10])
                        pbar.update(1)
                    
                    print(f"❌ 任务执行失败 [第{row_idx}行, {model_name}]: {e}")
        
        pbar.close()
    
    print(f"🎉 并行批量推理完成！")
    print(f"📊 总任务数: {len(tasks)}")
    print(f"💾 结果保存至: {output_path}")

def show_summary(output_path: str) -> None:
    """显示推理结果统计"""
    print(f"\n📈 推理结果统计")
    print("=" * 50)
    
    if not Path(output_path).exists():
        print("❌ 输出文件不存在")
        return
    
    results = []
    with open(output_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    
    if not results:
        print("❌ 没有结果数据")
        return
    
    # 按模型统计
    model_stats = {}
    total_time = 0
    total_retries = 0
    rate_limit_errors = 0
    
    for result in results:
        model_name = result['model_name']
        if model_name not in model_stats:
            model_stats[model_name] = {
                'total': 0,
                'success': 0,
                'failed': 0,
                'total_time': 0,
                'avg_time': 0,
                'total_retries': 0,
                'rate_limit_errors': 0
            }
        
        stats = model_stats[model_name]
        stats['total'] += 1
        total_time += result['response_time']
        stats['total_time'] += result['response_time']
        
        # 统计重试次数
        retry_count = result.get('retry_count', 0)
        stats['total_retries'] += retry_count
        total_retries += retry_count
        
        # 统计限流错误
        if result.get('is_rate_limit', False):
            stats['rate_limit_errors'] += 1
            rate_limit_errors += 1
        
        if result['success']:
            stats['success'] += 1
        else:
            stats['failed'] += 1
    
    # 计算平均时间
    for model_name, stats in model_stats.items():
        if stats['total'] > 0:
            stats['avg_time'] = round(stats['total_time'] / stats['total'], 2)
    
    # 检查是否使用了模板
    template_used_count = sum(1 for result in results if result.get('template_used', False))
    template_usage = template_used_count > 0
    
    # 显示统计结果
    print(f"总结果数: {len(results)}")
    print(f"总耗时: {round(total_time, 2)}秒")
    print(f"总重试次数: {total_retries}")
    print(f"限流错误数: {rate_limit_errors}")
    if template_usage:
        print(f"使用模板: ✅ ({template_used_count}/{len(results)} 条)")
    else:
        print(f"使用模板: ❌")
    print()
    
    for model_name, stats in model_stats.items():
        success_rate = round(stats['success'] / stats['total'] * 100, 1) if stats['total'] > 0 else 0
        avg_retries = round(stats['total_retries'] / stats['total'], 1) if stats['total'] > 0 else 0
        print(f"🤖 {model_name}:")
        print(f"  总数: {stats['total']}")
        print(f"  成功: {stats['success']} ({success_rate}%)")
        print(f"  失败: {stats['failed']}")
        print(f"  平均耗时: {stats['avg_time']}秒")
        print(f"  总重试: {stats['total_retries']} (平均{avg_retries}次)")
        print(f"  限流错误: {stats['rate_limit_errors']}")
        print()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="并行批量推理脚本")
    parser.add_argument("--csv", default="ReportBench_v0.7_sample_150_sheet1.csv", 
                       help="输入CSV文件路径")
    parser.add_argument("--prompt-column", choices=PROMPT_COLUMNS, default="英文prompt",
                       help="使用的prompt列名")
    parser.add_argument("--output", help="输出jsonl文件路径（默认自动生成）")
    parser.add_argument("--start-idx", type=int, default=0,
                       help="开始的行索引（用于续传）")
    parser.add_argument("--models", nargs="+", choices=MODELS, default=MODELS,
                       help="要使用的模型列表")
    parser.add_argument("--max-workers", type=int, default=8,
                       help="最大并发线程数（默认8）")
    parser.add_argument("--delay", type=float, default=0.1,
                       help="请求间隔时间（秒，默认0.1）")
    parser.add_argument("--max-retries", type=int, default=3,
                       help="非限流错误的最大重试次数（默认3，限流错误无限重试）")
    parser.add_argument("--template", type=str, default=None,
                       help="模板文件路径（如eval.txt），用于对原始prompt进行模板化处理")
    
    args = parser.parse_args()
    
    # 生成默认输出文件名
    if not args.output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        column_name = args.prompt_column.replace("文", "").replace("prompt", "")
        args.output = f"batch_infer_results_{column_name}_{timestamp}.jsonl"
    
    try:
        # 加载数据
        df = load_data(args.csv)
        
        # 检查prompt列是否存在
        if args.prompt_column not in df.columns:
            print(f"❌ 列 '{args.prompt_column}' 不存在")
            print(f"可用列: {list(df.columns)}")
            return
        
        # 过滤要使用的模型
        selected_models = [m for m in MODELS if m in args.models]
        
        # 构建模型
        models = build_models(selected_models)
        
        # 执行并行批量推理
        batch_infer_parallel(df, models, args.prompt_column, args.output, 
                           args.start_idx, args.max_workers, args.delay, args.max_retries,
                           args.template)
        
        # 显示统计结果
        show_summary(args.output)
        
    except KeyboardInterrupt:
        print(f"\n⚠️  用户中断执行")
        print(f"💡 可以使用 --start-idx 参数续传")
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        raise

if __name__ == "__main__":
    main() 