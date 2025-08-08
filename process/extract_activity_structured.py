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
import re
from bs4 import BeautifulSoup
from datetime import datetime

def extract_activity_structured(json_file_path=None, activity_html=None, log=None):
    """
    从JSON文件或直接从HTML字符串中提取activity字段并解析出结构化的活动数据
    
    Args:
        json_file_path (str, optional): JSON文件路径
        activity_html (str, optional): 直接传入的HTML字符串
    """
    
    if activity_html is not None:
        # 直接使用传入的HTML字符串
        pass
    elif json_file_path is not None:
        # 从JSON文件中读取
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        activity_html = data.get('activity', '')
    else:
        raise ValueError("必须提供 json_file_path 或 activity_html 参数之一")
    
    # 使用BeautifulSoup解析HTML
    soup = BeautifulSoup(activity_html, 'html.parser')
    
    structured_activities = []
    activity_index = 1
    
    # 新的解析策略：寻找独立的活动文本块
    # 1. 先找到所有可能的活动文本
    all_text_blocks = []
    
    # 查找所有包含实际文本内容的div
    for div in soup.find_all('div'):
        text = div.get_text(strip=True)
        if text and len(text) > 10 and len(text) < 2000:  # 合理长度的文本
            # 检查是否是叶子节点或接近叶子节点
            child_divs = div.find_all('div')
            if len(child_divs) <= 3:  # 嵌套不深的div
                all_text_blocks.append(text)
    
    # 去重文本块
    unique_blocks = []
    seen_blocks = set()
    for block in all_text_blocks:
        # 创建去重key（取前50字符）
        key = block[:50]
        if key not in seen_blocks:
            seen_blocks.add(key)
            unique_blocks.append(block)
    
    # 2. 识别和分类每个文本块
    for text_content in unique_blocks:
        if not text_content or len(text_content) < 10:
            continue
            
        # 清理ChatGPT前缀
        cleaned_content = text_content
        if cleaned_content.startswith('ChatGPT'):
            cleaned_content = cleaned_content[7:].strip()
            
        # 跳过太短的内容
        if len(cleaned_content) < 10:
            continue
        
        # 识别搜索活动
        if 'Searched for' in text_content:
            # 提取搜索关键词
            search_pattern = r'Searched for (.+)'
            match = re.search(search_pattern, text_content)
            if match:
                search_query = match.group(1).strip()
                activity = {
                    'index': activity_index,
                    'type': '搜索',
                    'content': f"搜索关键词: {search_query}",
                    'search_query': search_query
                }
                structured_activities.append(activity)
                activity_index += 1
                
        # 识别读取网站活动
        elif any(keyword in text_content for keyword in ['读取', '读取网站', '读取来自']):
            # 提取网站URL
            url_pattern = r'(?:https?://)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            url_match = re.search(url_pattern, text_content)
            website = url_match.group(1) if url_match else "未知网站"
            
            activity = {
                'index': activity_index,
                'type': '读取网站',
                'content': cleaned_content,
                'website': website
            }
            structured_activities.append(activity)
            activity_index += 1
            
        # 识别思考活动（其他所有内容）
        else:
            activity = {
                'index': activity_index,
                'type': '思考',
                'content': cleaned_content
            }
            structured_activities.append(activity)
            activity_index += 1
    
    # 去重和清理
    cleaned_activities = []
    seen_content = set()
    
    for activity in structured_activities:
        # 创建一个简化的内容用于去重（前100字符）
        content_key = f"{activity['type']}:{activity['content'][:100]}"
        if content_key not in seen_content:
            seen_content.add(content_key)
            cleaned_activities.append(activity)
    
    # 重新分配连续的index (1-n)
    for i, activity in enumerate(cleaned_activities, 1):
        activity['index'] = i
    
    # 将第一个活动的type设定为"标题"
    if cleaned_activities and len(cleaned_activities) > 0:
        cleaned_activities[0]['type'] = '标题'
    
    result = {
        'total_activities': len(cleaned_activities),
        'activity_summary': {
            '标题': len([a for a in cleaned_activities if a['type'] == '标题']),
            '思考': len([a for a in cleaned_activities if a['type'] == '思考']),
            '搜索': len([a for a in cleaned_activities if a['type'] == '搜索']),
            '读取网站': len([a for a in cleaned_activities if a['type'] == '读取网站'])
        },
        'activities': cleaned_activities
    }
    
    # 如果有log函数，输出简化的统计信息
    if log:
        log(f"    ✅ 活动解析完成: {result['total_activities']} 个活动")
        for activity_type, count in result['activity_summary'].items():
            if count > 0:
                log(f"      {activity_type}: {count} 个")
    
    return result

def save_structured_data(structured_data, output_file):
    """保存结构化数据到文件"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(structured_data, f, ensure_ascii=False, indent=2)

def print_summary(structured_data):
    """打印活动摘要"""
    print("="*50)
    print("活动解析摘要")
    print("="*50)
    print(f"总活动数量: {structured_data['total_activities']}")
    print("\n活动类型分布:")
    for activity_type, count in structured_data['activity_summary'].items():
        print(f"  {activity_type}: {count} 次")
    
    print("\n详细活动列表:")
    print("-"*50)
    
    for activity in structured_data['activities']:
        print(f"[{activity['index']:2d}] {activity['type']}")
        if activity['type'] == '搜索' and 'search_query' in activity:
            print(f"     搜索词: {activity['search_query']}")
        elif activity['type'] == '读取网站' and 'website' in activity:
            print(f"     网站: {activity['website']}")
        else:
            # 对于思考类型，显示内容的前80个字符
            content_preview = activity['content'][:80] + "..." if len(activity['content']) > 80 else activity['content']
            print(f"     内容: {content_preview}")
        print()

if __name__ == "__main__":
    # 处理文件
    input_file = "processed_data.json"
    output_file = "activity_structured_from_json.json"
    
    try:
        print("正在解析activity字段...")
        structured_data = extract_activity_structured(input_file)
        
        print("正在保存结构化数据...")
        save_structured_data(structured_data, output_file)
        
        print_summary(structured_data)
        
        print(f"\n结构化数据已保存到: {output_file}")
        
    except FileNotFoundError:
        print(f"错误: 找不到文件 {input_file}")
    except json.JSONDecodeError:
        print(f"错误: {input_file} 不是有效的JSON文件")
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}") 