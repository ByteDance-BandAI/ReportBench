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
from urllib.parse import urlparse
from datetime import datetime

def extract_reference_structured(json_file_path=None, reference_html=None, log=None):
    """
    从JSON文件或直接从HTML字符串中提取并结构化reference字段的信息
    
    Args:
        json_file_path (str, optional): JSON文件路径
        reference_html (str, optional): 直接传入的HTML字符串
    """
    
    if reference_html is not None:
        # 直接使用传入的HTML字符串
        pass
    elif json_file_path is not None:
        # 从JSON文件中读取
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        reference_html = data.get('reference', '')
    else:
        raise ValueError("必须提供 json_file_path 或 reference_html 参数之一")
    
    if not reference_html:
        if log:
            log("❌ 未找到reference字段")
        return None
    
    # 使用BeautifulSoup解析HTML
    soup = BeautifulSoup(reference_html, 'html.parser')
    
    # 查找所有链接
    all_links = soup.find_all('a', href=True)
    if log:
        log(f"🔍 总共找到 {len(all_links)} 个链接")
    
    # 查找"全部来源"或"All Sources"文本来定位分界点
    source_element = soup.find(string=re.compile(r'全部来源|All Sources'))
    if not source_element:
        if log:
            log("❌ 未找到'全部来源'或'All Sources'标识，无法分割详细引用和域名汇总")
        return None
    
    # 确定找到的是哪种分界符
    source_text = source_element.strip()
    if log:
        log(f"✅ 找到分界点: '{source_text}'")
    
    # 找到分界符在HTML中的位置，以此为分界点
    html_str = str(soup)
    source_position = html_str.find('全部来源')
    if source_position == -1:
        source_position = html_str.find('All Sources')
    
    # 将所有链接按位置分类
    detailed_references = []
    domain_summary = []
    
    for link in all_links:
        link_position = str(soup).find(str(link))
        if link_position < source_position:
            # 在"全部来源"之前的为详细引用
            ref_info = extract_detailed_reference_simple(link, len(detailed_references) + 1)
            if ref_info:
                detailed_references.append(ref_info)
        else:
            # 在"全部来源"之后的为域名汇总
            domain_info = extract_domain_info_simple(link, len(domain_summary) + 1)
            if domain_info:
                domain_summary.append(domain_info)
    
    if log:
        log(f"✅ 详细引用解析完成: {len(detailed_references)}个")
        log(f"✅ 域名汇总解析完成: {len(domain_summary)}个")
    
    return {
        'detailed_references': detailed_references,
        'domain_summary': domain_summary
    }

def extract_detailed_reference_simple(link, index):
    """
    简化版详细引用提取，使用div结构准确分离title和description
    """
    href = link.get('href')
    if not href:
        return None
    
    # 解析URL获取domain
    parsed_url = urlparse(href)
    domain = parsed_url.netloc
    
    # 查找内部div结构
    divs = link.find_all('div')
    
    title = ""
    description = ""
    
    if len(divs) >= 3:
        # 标准的3个div结构
        # div 1: 域名 (忽略)
        # div 2: 标题
        # div 3: 描述
        title = divs[1].get_text(strip=True)
        description = divs[2].get_text(strip=True)
    elif len(divs) == 2:
        # 2个div的情况
        title = divs[0].get_text(strip=True)
        description = divs[1].get_text(strip=True)
    else:
        # 回退方案：使用全部文本
        display_text = link.get_text(strip=True)
        title = display_text[:100] + "..." if len(display_text) > 100 else display_text
        description = display_text
    
    return {
        'index': index,
        'domain': domain,
        'url': href,
        'title': title,
        'description': description
    }

def extract_domain_info_simple(link, index):
    """
    简化版域名信息提取
    """
    href = link.get('href')
    if not href:
        return None
    
    display_text = link.get_text(strip=True)
    
    # 从display_text中提取域名和计数
    domain = display_text
    count = 1
    
    # 检查是否有数字后缀（如"sohu2"表示2次）
    count_match = re.search(r'(\d+)$', display_text)
    if count_match:
        count = int(count_match.group(1))
        domain = re.sub(r'\d+$', '', display_text)
    
    return {
        'index': index,
        'domain': domain,
        'href': href,
        'count': count
    }

def classify_url_type(url):
    """
    根据URL分类网站类型（保留此函数以防需要）
    """
    domain = urlparse(url).netloc.lower()
    
    if any(keyword in domain for keyword in ['law', '法律', 'legal']):
        return '法律咨询'
    elif any(keyword in domain for keyword in ['news', 'daily', '新闻']):
        return '新闻媒体'
    elif any(keyword in domain for keyword in ['zhihu', 'weibo', 'sina', 'sohu', 'ifeng']):
        return '社交平台'
    elif any(keyword in domain for keyword in ['fang', 'house', 'rent', '租房', 'hexun', 'ziroom']):
        return '租房平台'
    elif any(keyword in domain for keyword in ['gov', '政府']):
        return '政府官方'
    elif any(keyword in domain for keyword in ['edu', '教育', 'libaedu']):
        return '学术教育'
    else:
        return '其他'

def main():
    import sys
    
    # 检查是否提供了文件路径参数
    if len(sys.argv) > 1:
        json_file_path = sys.argv[1]
    else:
        json_file_path = 'temp/openai-01.json'  # 默认文件
    
    print(f"📁 处理文件: {json_file_path}")
    
    try:
        result = extract_reference_structured(json_file_path)
        
        if not result:
            print("❌ 解析失败")
            return
        
        # 生成输出文件名
        import os
        base_name = os.path.splitext(os.path.basename(json_file_path))[0]
        output_file = f'reference_structured_from_{base_name}.json'
        
        # 保存结构化数据到文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print("✅ Reference字段解析完成！")
        print(f"📊 解析摘要:")
        print(f"🔗 详细引用链接: {len(result['detailed_references'])}个")
        print(f"🏷️ 域名汇总: {len(result['domain_summary'])}个")
        print(f"📁 结构化数据已保存到: {output_file}")
        
    except Exception as e:
        print(f"❌ 处理文件时出错: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 