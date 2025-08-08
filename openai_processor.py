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

import json
import os
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from tqdm import tqdm

class FileLogger:
    """为每个文件创建独立的日志记录器"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self._loggers = {}
        self._lock = threading.Lock()
    
    def get_logger(self, file_path: str):
        """获取指定文件的日志记录器"""
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        log_file = os.path.join(self.log_dir, f"{base_name}.log")
        
        with self._lock:
            if log_file not in self._loggers:
                self._loggers[log_file] = open(log_file, 'w', encoding='utf-8')
                # 写入日志头部信息
                self._loggers[log_file].write(f"Processing log for: {os.path.basename(file_path)}\n")
                self._loggers[log_file].write(f"Started at: {datetime.now().isoformat()}\n")
                self._loggers[log_file].write("=" * 60 + "\n\n")
                self._loggers[log_file].flush()
            
            return self._loggers[log_file]
    
    def log(self, file_path: str, message: str):
        """记录日志消息"""
        logger = self.get_logger(file_path)
        timestamp = datetime.now().strftime("%H:%M:%S")
        logger.write(f"[{timestamp}] {message}\n")
        logger.flush()
    
    def close_all(self):
        """关闭所有日志文件"""
        with self._lock:
            for logger in self._loggers.values():
                logger.close()
            self._loggers.clear()

# 全局日志记录器
file_logger = FileLogger()

def clean_markdown_block(content: str) -> str:
    """清理markdown内容中的代码块标记"""
    if not content:
        return content
    
    # 去掉前面的markdown代码块标记
    content = re.sub(r'^```(?:markdown|md)?\s*\n?', '', content, flags=re.IGNORECASE | re.MULTILINE)
    
    # 去掉后面的代码块结束标记
    content = re.sub(r'\n?```\s*$', '', content, flags=re.MULTILINE)
    
    # 清理前后多余的空格和换行
    content = content.strip()
    
    return content

def split_html_by_headers(html_content: str, max_chunk_size: int, log=None) -> list:
    """
    按HTML标题（h1, h2, h3）分块，确保每个块都以标题开头
    
    Args:
        html_content: 原始HTML内容
        max_chunk_size: 最大块大小
        log: 日志函数
        
    Returns:
        list: 分块后的HTML列表
    """
    if not html_content or len(html_content) <= max_chunk_size:
        return [html_content]
    
    # 查找所有的h1, h2, h3标题标签位置
    header_pattern = r'(<h[123][^>]*>)'
    header_matches = list(re.finditer(header_pattern, html_content, re.IGNORECASE))
    
    if not header_matches:
        # 如果没有找到标题，回退到单块
        if log:
            log("    ⚠️ 未找到标题标签，回退到单块处理")
        return [html_content]
    
    chunks = []
    start_pos = 0
    current_chunk = ""
    
    for i, match in enumerate(header_matches):
        header_pos = match.start()
        
        # 如果这是第一个标题，且前面有内容，先处理前面的内容
        if i == 0 and header_pos > 0:
            prefix_content = html_content[start_pos:header_pos]
            if prefix_content.strip():
                # 如果前缀内容很长，单独成块
                if len(prefix_content) > max_chunk_size:
                    chunks.append(prefix_content)
                else:
                    current_chunk = prefix_content
            start_pos = header_pos
        
        # 计算到下一个标题的内容
        if i < len(header_matches) - 1:
            next_header_pos = header_matches[i + 1].start()
            section_content = html_content[start_pos:next_header_pos]
        else:
            # 最后一个标题，取到文件结尾
            section_content = html_content[start_pos:]
        
        # 检查当前块加上这个section是否超出大小限制
        if current_chunk and len(current_chunk + section_content) > max_chunk_size:
            # 当前块已经满了，先保存，然后开始新块
            chunks.append(current_chunk)
            current_chunk = section_content
        else:
            # 添加到当前块
            current_chunk += section_content
        
        # 如果当前section本身就超过大小限制，强制分块
        if len(current_chunk) > max_chunk_size:
            chunks.append(current_chunk)
            current_chunk = ""
        
        # 更新下一次的起始位置
        if i < len(header_matches) - 1:
            start_pos = header_matches[i + 1].start()
    
    # 添加最后一个块（如果有内容）
    if current_chunk.strip():
        chunks.append(current_chunk)
    
    # 确保所有块都有内容
    chunks = [chunk for chunk in chunks if chunk.strip()]
    
    if log:
        log(f"    📊 按标题分块统计:")
        for i, chunk in enumerate(chunks, 1):
            chunk_headers = re.findall(r'<h[123][^>]*>', chunk, re.IGNORECASE)
            log(f"      块 {i}: {len(chunk)} 字符, {len(chunk_headers)} 个标题")
    
    return chunks

def extract_activity_from_html(activity_html: str, log=None) -> Dict[str, Any]:
    """从HTML字符串中提取结构化的activity数据"""
    if not activity_html:
        return {
            'total_activities': 0,
            'activity_summary': {'思考': 0, '搜索': 0, '读取网站': 0},
            'activities': []
        }
    
    from process.extract_activity_structured import extract_activity_structured
    result = extract_activity_structured(activity_html=activity_html, log=log)
    return result

def extract_reference_from_html(reference_html: str, log=None) -> Dict[str, Any]:
    """从HTML字符串中提取结构化的reference数据"""
    if not reference_html:
        return {
            'detailed_references': [],
            'domain_summary': []
        }
    
    from process.extract_reference_structured import extract_reference_structured
    result = extract_reference_structured(reference_html=reference_html, log=log)
    return result

def convert_html_to_markdown_string(html_content: str, log) -> str:
    """将HTML字符串转换为Markdown字符串"""
    if not html_content or not html_content.strip():
        return ""
    
    try:
        from process.html2markdown import process_html_content, create_html_to_markdown_prompt
        from utils import build_llm
        from langchain.schema import HumanMessage
        
        log("    🔄 预处理HTML内容...")
        # 预处理HTML内容（URL标准化和标签清理）
        processed_html = process_html_content(html_content)
        
        # 如果内容太短，直接返回
        if len(processed_html) < 100:
            return processed_html
        
        log(f"    📏 HTML内容长度: {len(processed_html)} 字符")
        
        # 分块处理（如果内容太长）
        max_chunk_size = 10240
        
        if len(processed_html) <= max_chunk_size:
            chunks = [processed_html]
        else:
            log("    ✂️ 按标题分块处理长内容...")
            chunks = split_html_by_headers(processed_html, max_chunk_size, log)
            
            # 校验：确保切块合并后等于原始内容
            merged_content = ''.join(chunks)
            if merged_content != processed_html:
                log("    ⚠️ 警告：切块合并后与原始内容不一致！")
                log(f"      原始长度: {len(processed_html)}")
                log(f"      合并长度: {len(merged_content)}")
                # 如果校验失败，回退到单块处理
                chunks = [processed_html]
            else:
                log("    ✅ 切块校验通过")
        
        log(f"    📦 分为 {len(chunks)} 个块进行处理")
        
        # 初始化LLM
        log("    🤖 初始化LLM...")
        llm = build_llm(temperature=0.1)
        
        # 并行转换所有块
        log("    🔄 开始并行处理所有块...")
        
        def process_chunk(chunk_data):
            i, chunk = chunk_data
            prompt = create_html_to_markdown_prompt(chunk)
            try:
                response = llm.invoke([HumanMessage(content=prompt)])
                markdown_chunk = response.content.strip()
                
                # 清理markdown代码块标记
                markdown_chunk = clean_markdown_block(markdown_chunk)
                
                log(f"    ✅ 第 {i} 块转换完成")
                return i, markdown_chunk
            except Exception as e:
                log(f"    ⚠️ 第 {i} 块转换失败: {e}")
                # 如果转换失败，保留原始内容
                return i, chunk
        
        # 使用并行处理
        chunk_data_list = [(i+1, chunk) for i, chunk in enumerate(chunks)]
        markdown_chunks = [None] * len(chunks)  # 预分配列表保持顺序
        
        with ThreadPoolExecutor(max_workers=min(len(chunks), 5)) as executor:
            # 提交所有任务
            future_to_index = {executor.submit(process_chunk, chunk_data): chunk_data[0] for chunk_data in chunk_data_list}
            
            # 收集结果
            for future in as_completed(future_to_index):
                try:
                    i, result = future.result()
                    markdown_chunks[i-1] = result  # i是从1开始的，所以要减1
                except Exception as e:
                    i = future_to_index[future]
                    log(f"    ❌ 第 {i} 块处理异常: {e}")
                    markdown_chunks[i-1] = chunks[i-1]  # 使用原始chunk
        
        # 合并所有块，再次清理空格
        cleaned_chunks = [chunk.strip() for chunk in markdown_chunks if chunk and chunk.strip()]
        markdown_content = '\n\n'.join(cleaned_chunks)
        
        # 后处理修复和检查
        log("    🔧 修复常见的Markdown格式问题...")
        from process.html2markdown import fix_common_markdown_issues, check_markdown_links, check_markdown_tables
        markdown_content = fix_common_markdown_issues(markdown_content)
        
        # 检查链接正确性
        log("    🔍 检查Markdown超链接...")
        links_ok, link_errors = check_markdown_links(markdown_content)
        if not links_ok:
            log(f"    ⚠️ 发现 {len(link_errors)} 个链接问题")
            for error in link_errors[:3]:  # 只显示前3个错误
                log(f"      - {error}")
            if len(link_errors) > 3:
                log(f"      ... 还有 {len(link_errors) - 3} 个链接问题")
        else:
            log("    ✅ 所有链接格式正确")
        
        # 检查表格正确性
        log("    🔍 检查Markdown表格...")
        tables_ok, table_errors = check_markdown_tables(markdown_content)
        if not tables_ok:
            log(f"    ⚠️ 发现 {len(table_errors)} 个表格问题")
            for error in table_errors[:3]:  # 只显示前3个错误
                log(f"      - {error}")
            if len(table_errors) > 3:
                log(f"      ... 还有 {len(table_errors) - 3} 个表格问题")
        else:
            log("    ✅ 所有表格格式正确")
        
        log(f"    📄 最终Markdown长度: {len(markdown_content)} 字符")
        
        return markdown_content
        
    except Exception as e:
        log(f"    ❌ HTML转换出错: {e}")
        # 如果转换失败，进行简单的HTML到文本转换
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            # 简单的文本提取，保留基本结构
            text = soup.get_text()
            # 清理多余的空行
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            markdown_content = '\n\n'.join(lines)
            
            # 对简单转换的内容也进行基本修复
            log("    🔧 对简单转换结果进行基本修复...")
            from process.html2markdown import fix_common_markdown_issues
            markdown_content = fix_common_markdown_issues(markdown_content)
            
            return markdown_content
        except:
            return "HTML转换失败，无法提取内容"

def generate_output_filename(input_file_path: str, output_dir: str = "result") -> str:
    """根据输入文件路径生成输出文件路径"""
    # 提取文件名（不含扩展名）
    base_name = os.path.splitext(os.path.basename(input_file_path))[0]
    
    # 生成输出文件名：parsed_原文件名.json
    output_filename = f"parsed_{base_name}.json"
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    return os.path.join(output_dir, output_filename)

def process_single_file(file_path: str, output_dir: str = "result", include_markdown: bool = True) -> Dict[str, Any]:
    """处理单个JSON文件的完整流程，并保存到独立文件"""
    def log(message: str):
        """内部日志函数"""
        file_logger.log(file_path, message)
    
    log(f"开始处理文件: {os.path.basename(file_path)}")
    log("-" * 50)
    
    try:
        # 第1步：处理messages，提取prompt和response
        log("🔍 第1步: 提取prompt和response...")
        from process.process_json import process_openai_json
        basic_data = process_openai_json(file_path)
        if not basic_data:
            log(f"❌ 无法处理文件: {file_path}")
            return None
        
        log(f"  ✓ Prompt长度: {len(basic_data.get('prompt', ''))} 字符")
        log(f"  ✓ Response长度: {len(basic_data.get('answer', ''))} 字符")
        log(f"  ✓ Activity长度: {len(basic_data.get('activity', ''))} 字符")
        log(f"  ✓ Reference长度: {len(basic_data.get('reference', ''))} 字符")
        
        # 第2步：将response转换为markdown（可选）
        markdown_report = ""
        if include_markdown and basic_data.get('answer'):
            log("📝 第2步: 转换response为markdown...")
            try:
                markdown_report = convert_html_to_markdown_string(basic_data['answer'], log)
                log("  ✅ Markdown转换完成")
            except Exception as e:
                log(f"  ⚠️ Markdown转换失败: {e}")
                # 进行简单的HTML到文本转换作为降级方案
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(basic_data['answer'], 'html.parser')
                    text = soup.get_text()
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    markdown_report = '\n\n'.join(lines)
                    
                    # 对降级处理的内容也进行修复
                    log("  🔧 对降级处理结果进行修复...")
                    from process.html2markdown import fix_common_markdown_issues
                    markdown_report = fix_common_markdown_issues(markdown_report)
                except:
                    markdown_report = "HTML转换失败，无法提取内容"
        else:
            log("📝 第2步: 简单HTML转换")
            # 进行简单的HTML到文本转换
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(basic_data['answer'], 'html.parser')
                text = soup.get_text()
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                markdown_report = '\n\n'.join(lines)
                
                # 对简单转换的内容也进行修复和检查
                log("  🔧 修复常见格式问题...")
                from process.html2markdown import fix_common_markdown_issues, check_markdown_links, check_markdown_tables
                markdown_report = fix_common_markdown_issues(markdown_report)
                
                # 检查链接（虽然简单转换通常没有链接，但保持一致性）
                links_ok, link_errors = check_markdown_links(markdown_report)
                if not links_ok:
                    log(f"  ⚠️ 发现 {len(link_errors)} 个链接问题")
                
                # 检查表格
                tables_ok, table_errors = check_markdown_tables(markdown_report)
                if not tables_ok:
                    log(f"  ⚠️ 发现 {len(table_errors)} 个表格问题")
                
                log(f"  ✓ 简单转换完成，长度: {len(markdown_report)} 字符")
            except:
                markdown_report = "HTML转换失败，无法提取内容"
                log("  ⚠️ 简单转换失败")
        
        # 第3步：处理activity
        log("⚡ 第3步: 处理activity数据...")
        activity_data = extract_activity_from_html(basic_data.get('activity', ''), log)
        log(f"  ✓ 提取到 {activity_data['total_activities']} 个活动")
        log(f"    思考: {activity_data['activity_summary'].get('思考', 0)} 个")
        log(f"    搜索: {activity_data['activity_summary'].get('搜索', 0)} 个") 
        log(f"    读取网站: {activity_data['activity_summary'].get('读取网站', 0)} 个")
        
        # 第4步：处理reference
        log("🔗 第4步: 处理reference数据...")
        reference_data = extract_reference_from_html(basic_data.get('reference', ''), log)
        log(f"  ✓ 提取到 {len(reference_data['detailed_references'])} 个详细引用")
        log(f"  ✓ 提取到 {len(reference_data['domain_summary'])} 个域名汇总")
        
        # 整合所有结果
        result = {
            'file_info': {
                'source_file': os.path.basename(file_path),
                'source_path': file_path,
                'processed_at': datetime.now().isoformat()
            },
            'prompt': basic_data.get('prompt', ''),
            'response': markdown_report,
            'activity': activity_data,
            'reference': reference_data
        }
        
        # 第5步：保存到独立文件
        output_file = generate_output_filename(file_path, output_dir)
        log(f"💾 保存到: {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        log(f"✅ 文件 {os.path.basename(file_path)} 处理完成")
        
        # 返回处理结果摘要（用于汇总统计）
        return {
            'input_file': file_path,
            'output_file': output_file,
            'stats': {
                'prompt_length': len(result['prompt']),
                'response_length': len(result['response']),
                'total_activities': result['activity']['total_activities'],
                'activity_breakdown': result['activity']['activity_summary'],
                'detailed_references': len(result['reference']['detailed_references']),
                'domain_summary': len(result['reference']['domain_summary'])
            }
        }
        
    except Exception as e:
        log(f"❌ 处理文件 {file_path} 时出错: {e}")
        import traceback
        log(traceback.format_exc())
        return None

def create_index_file(processed_results: list, output_dir: str = "result") -> str:
    """创建索引文件，记录所有处理过的文件信息"""
    index_data = {
        'summary': {
            'total_files_processed': len(processed_results),
            'processing_completed_at': datetime.now().isoformat(),
            'total_activities': sum(r['stats']['total_activities'] for r in processed_results),
            'total_detailed_references': sum(r['stats']['detailed_references'] for r in processed_results),
            'total_domain_summary': sum(r['stats']['domain_summary'] for r in processed_results)
        },
        'files': []
    }
    
    for result in processed_results:
        file_info = {
            'input_file': os.path.basename(result['input_file']),
            'output_file': os.path.basename(result['output_file']),
            'stats': result['stats']
        }
        index_data['files'].append(file_info)
    
    # 保存索引文件
    index_file = os.path.join(output_dir, "processing_index.json")
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    
    return index_file

def process_all_files(input_dir: str = "openai", output_dir: str = "result", include_markdown: bool = False, max_workers: int = 4) -> None:
    """批量并行处理目录下的所有JSON文件，每个文件生成独立输出"""
    print("🚀 开始统一处理流程")
    print("=" * 60)
    
    # 查找所有JSON文件
    json_files = []
    if os.path.exists(input_dir):
        for file_name in os.listdir(input_dir):
            if file_name.endswith('.json'):
                json_files.append(os.path.join(input_dir, file_name))
    
    if not json_files:
        print(f"❌ 在目录 {input_dir} 中未找到JSON文件")
        return
    
    json_files.sort()  # 按文件名排序
    print(f"📊 发现 {len(json_files)} 个JSON文件:")
    for file_path in json_files:
        print(f"  - {os.path.basename(file_path)}")
    
    print(f"\n🔧 配置选项:")
    print(f"  - 输入目录: {input_dir}")
    print(f"  - 输出目录: {output_dir}")
    print(f"  - 包含Markdown转换: {'是' if include_markdown else '否'}")
    print(f"  - 并行工作线程数: {max_workers}")
    print(f"  - 日志输出目录: logs/")
    
    # 确保输出目录和日志目录存在
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # 初始化日志记录器
    global file_logger
    file_logger = FileLogger()
    
    print(f"\n🔄 开始并行处理 {len(json_files)} 个文件...")
    
    # 使用并行处理所有文件
    processed_results = []
    failed_files = []
    
    def process_file_wrapper(file_path):
        """包装函数，用于处理单个文件并返回结果"""
        try:
            result = process_single_file(file_path, output_dir, include_markdown)
            return file_path, result, None
        except Exception as e:
            return file_path, None, str(e)
    
    # 使用ThreadPoolExecutor并行处理，配合tqdm显示进度
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        futures = {executor.submit(process_file_wrapper, file_path): file_path for file_path in json_files}
        
        # 使用tqdm显示进度条
        with tqdm(total=len(json_files), desc="📁 处理文件", unit="files") as pbar:
            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    original_path, result, error = future.result()
                    
                    if result:
                        processed_results.append(result)
                        pbar.set_postfix_str(f"✅ {os.path.basename(original_path)}")
                    else:
                        failed_files.append((original_path, error or "未知错误"))
                        pbar.set_postfix_str(f"❌ {os.path.basename(original_path)}")
                    
                except Exception as e:
                    failed_files.append((file_path, str(e)))
                    pbar.set_postfix_str(f"❌ {os.path.basename(file_path)}")
                
                pbar.update(1)
    
    # 关闭所有日志文件
    file_logger.close_all()
    
    success_count = len(processed_results)
    
    if not processed_results:
        print("\n❌ 没有成功处理任何文件")
        if failed_files:
            print("失败的文件:")
            for file_path, error in failed_files:
                print(f"  - {os.path.basename(file_path)}: {error}")
        return
    
    # 创建索引文件
    print(f"\n📋 创建处理索引文件...")
    index_file = create_index_file(processed_results, output_dir)
    print(f"  ✓ 索引文件已保存: {index_file}")
    
    # 打印汇总信息
    print("\n" + "=" * 60)
    print("🎉 处理完成! 汇总信息")
    print("=" * 60)
    print(f"📁 成功处理文件: {success_count}/{len(json_files)}")
    
    if failed_files:
        print(f"❌ 失败文件: {len(failed_files)}")
        print("失败的文件:")
        for file_path, error in failed_files[:5]:  # 最多显示5个失败文件
            print(f"  - {os.path.basename(file_path)}: {error}")
        if len(failed_files) > 5:
            print(f"  ... 还有 {len(failed_files) - 5} 个失败文件")
    
    total_activities = sum(r['stats']['total_activities'] for r in processed_results)
    total_detailed_refs = sum(r['stats']['detailed_references'] for r in processed_results)
    total_domain_summary = sum(r['stats']['domain_summary'] for r in processed_results)
    
    print(f"⚡ 总活动数量: {total_activities}")
    print(f"🔗 总详细引用数量: {total_detailed_refs}")
    print(f"🏷️ 总域名汇总数量: {total_domain_summary}")
    
    # 打印各文件的详细统计和输出文件路径
    print("\n📊 各文件详细统计和输出文件:")
    print("-" * 60)
    for result in processed_results:
        input_name = os.path.basename(result['input_file'])
        output_name = os.path.basename(result['output_file'])
        stats = result['stats']
        
        print(f"📄 {input_name} -> {output_name}")
        print(f"  📝 Prompt: {stats['prompt_length']} 字符")
        print(f"  📄 Response: {stats['response_length']} 字符")
        print(f"  ⚡ 活动: {stats['total_activities']} 个 "
              f"(思考: {stats['activity_breakdown'].get('思考', 0)}, "
              f"搜索: {stats['activity_breakdown'].get('搜索', 0)}, "
              f"读取网站: {stats['activity_breakdown'].get('读取网站', 0)})")
        print(f"  🔗 引用: {stats['detailed_references']} 个详细引用, {stats['domain_summary']} 个域名汇总")
        print()
    
    print(f"📁 所有结果文件都保存在目录: {output_dir}/")
    print(f"📋 处理索引文件: {index_file}")
    print(f"📝 详细日志文件保存在目录: logs/")

def main():
    """主函数"""
    import sys
    
    # 检查命令行参数
    include_markdown = "--markdown" in sys.argv or "-m" in sys.argv
    
    # 检查输入目录参数
    input_dir = "openai"  # 默认值
    for arg in sys.argv:
        if arg.startswith("--input="):
            input_dir = arg.split("=", 1)[1]
        elif arg.startswith("--input-dir="):
            input_dir = arg.split("=", 1)[1]
    
    # 检查输出目录参数
    output_dir = "result"  # 默认值
    for arg in sys.argv:
        if arg.startswith("--output="):
            output_dir = arg.split("=", 1)[1]
        elif arg.startswith("--output-dir="):
            output_dir = arg.split("=", 1)[1]
    
    # 检查并行度参数
    max_workers = 4  # 默认值
    for arg in sys.argv:
        if arg.startswith("--workers="):
            try:
                max_workers = int(arg.split("=")[1])
                max_workers = max(1, min(max_workers, 16))  # 限制在1-16之间
            except ValueError:
                print("⚠️ 无效的workers参数，使用默认值4")
        elif arg.startswith("-j"):
            try:
                max_workers = int(arg[2:])
                max_workers = max(1, min(max_workers, 16))
            except ValueError:
                print("⚠️ 无效的并行度参数，使用默认值4")
    
    # 显示帮助信息
    if "--help" in sys.argv or "-h" in sys.argv:
        print("🔧 统一处理器 v2 - 批量处理JSON文件")
        print("=" * 50)
        print("用法:")
        print("  python unified_processor_v2.py [选项]")
        print("\n选项:")
        print("  --input=<目录>           指定输入目录 (默认: openai)")
        print("  --input-dir=<目录>       同上")
        print("  --output=<目录>          指定输出目录 (默认: result)")
        print("  --output-dir=<目录>      同上")
        print("  --markdown, -m           启用Markdown转换 (需要LLM)")
        print("  --workers=<数量>         并行工作线程数 (默认: 4)")
        print("  -j<数量>                 同上")
        print("  --help, -h               显示此帮助信息")
        print("\n示例:")
        print("  python unified_processor_v2.py")
        print("  python unified_processor_v2.py --input=data --output=results")
        print("  python unified_processor_v2.py --markdown --workers=8")
        print("  python unified_processor_v2.py --input-dir=raw_data --output-dir=processed_data -m -j8")
        return
    
    if include_markdown:
        print("🔧 启用Markdown转换模式（需要LLM调用）")
    else:
        print("⚡ 快速模式（跳过Markdown转换）")
    
    print(f"📁 输入目录: {input_dir}")
    print(f"📁 输出目录: {output_dir}")
    print(f"🔧 并行工作线程数: {max_workers}")
    print("📝 详细处理日志将保存到 logs/ 目录")
    
    try:
        process_all_files(input_dir=input_dir, output_dir=output_dir, include_markdown=include_markdown, max_workers=max_workers)
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断处理")
        file_logger.close_all()
    except Exception as e:
        print(f"\n\n❌ 处理过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        file_logger.close_all()

if __name__ == "__main__":
    main() 