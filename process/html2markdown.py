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
HTML到Markdown转换工具
只保留核心的HTML预处理和Markdown转换提示词功能

主要功能：
1. HTML预处理 - URL标准化和HTML标签清理
2. Markdown转换提示词生成
3. Markdown格式检查和修复
"""

import re
from urllib.parse import urlparse

def create_html_to_markdown_prompt(html_content: str) -> str:
    """
    创建HTML转Markdown的提示词
    
    Args:
        html_content: 需要转换的HTML内容
        
    Returns:
        str: 完整的提示词
    """
    prompt = f"""你是一个专业的文档格式转换专家。请将以下HTML内容转换为标准的Markdown格式。

**转换要求：**

1. **保持内容结构**：
   - 保留所有文本内容和信息
   - 维护原有的层次结构和逻辑关系
   - 确保段落分隔清晰

2. **HTML标签转换规则**：
   - `<h1>`, `<h2>`, `<h3>` → `#`, `##`, `###` 
   - `<strong>` → `**粗体**`
   - `<em>` → `*斜体*`
   - `<p>` → 段落换行
   - `<ul>`, `<li>` → `-` 无序列表
   - `<ol>`, `<li>` → `1.` 有序列表
   - `<a href="url">text</a>` → `[text](url)`

3. **表格处理**：
   - 将HTML表格转换为标准Markdown表格格式
   - 确保表格对齐和分隔符正确
   - 保持表头和数据行的结构

4. **超链接处理**：
   - 将所有`<a>`标签转换为`[文本](链接)`格式
   - 确保链接URL完整且可访问
   - 如果链接文本为空，使用链接URL作为显示文本

5. **数学公式处理**：
   - 将MathML或数学标签转换为LaTeX格式：`$...$`（行内）或`$$...$$`（块级）
   - 如果无法转换，保留原始内容并添加说明

6. **特殊处理**：
   - 移除所有HTML注释
   - 清理多余的空行（最多保留一个空行）
   - 确保代码块使用```包围
   - 移除无用的HTML属性和样式

**输出要求：**
- 输出纯Markdown格式，不包含任何HTML标签
- 确保Markdown语法正确
- 保持良好的可读性和格式

**待转换的HTML内容：**

```html
{html_content}
```

请直接输出转换后的Markdown内容，不要添加任何解释或额外说明。"""

    return prompt

def check_markdown_links(markdown_content: str) -> tuple[bool, list[str]]:
    """
    检查Markdown超链接的正确性
    
    Args:
        markdown_content: Markdown内容
        
    Returns:
        tuple: (是否全部正确, 错误信息列表)
    """
    errors = []
    
    # 匹配Markdown链接格式 [text](url)
    link_pattern = r'\[([^\]]*)\]\(([^)]+)\)'
    links = re.findall(link_pattern, markdown_content)
    
    for i, (text, url) in enumerate(links, 1):
        # 检查链接文本是否为空
        if not text.strip():
            errors.append(f"链接 {i}: 链接文本为空 - [{text}]({url})")
        
        # 检查URL格式
        if not url.strip():
            errors.append(f"链接 {i}: URL为空 - [{text}]({url})")
        elif not (url.startswith('http://') or url.startswith('https://') or url.startswith('/')):
            errors.append(f"链接 {i}: URL格式可能不正确 - [{text}]({url})")
        
        # 检查URL中是否有未编码的空格
        if ' ' in url:
            errors.append(f"链接 {i}: URL包含未编码的空格 - [{text}]({url})")
    
    # 检查是否有未完整的链接格式
    incomplete_links = re.findall(r'\[[^\]]*\]\([^)]*$', markdown_content)
    if incomplete_links:
        errors.extend([f"发现不完整的链接格式: {link}" for link in incomplete_links])
    
    return len(errors) == 0, errors

def check_markdown_tables(markdown_content: str) -> tuple[bool, list[str]]:
    """
    检查Markdown表格的正确性
    
    Args:
        markdown_content: Markdown内容
        
    Returns:
        tuple: (是否全部正确, 错误信息列表)
    """
    errors = []
    lines = markdown_content.split('\n')
    
    in_table = False
    table_line_count = 0
    header_columns = 0
    
    for line_num, line in enumerate(lines, 1):
        stripped_line = line.strip()
        
        # 检测表格行（包含 | 符号）
        if '|' in stripped_line and stripped_line:
            if not in_table:
                # 表格开始
                in_table = True
                table_line_count = 1
                header_columns = len([col for col in stripped_line.split('|') if col.strip()])
            else:
                table_line_count += 1
                
            # 检查表格分隔行（第二行应该是 |---|---|）
            if table_line_count == 2:
                if not re.match(r'^\s*\|[\s\-:|]*\|\s*$', stripped_line):
                    errors.append(f"行 {line_num}: 表格分隔行格式不正确 - {stripped_line}")
                else:
                    # 检查分隔行的列数是否与标题行匹配
                    separator_columns = len([col for col in stripped_line.split('|') if col.strip()])
                    if separator_columns != header_columns:
                        errors.append(f"行 {line_num}: 表格分隔行列数({separator_columns})与标题行列数({header_columns})不匹配")
            
            # 检查表格行的列数一致性
            current_columns = len([col for col in stripped_line.split('|') if col.strip()])
            if table_line_count > 2 and current_columns != header_columns:
                errors.append(f"行 {line_num}: 表格行列数({current_columns})与标题行列数({header_columns})不匹配")
                
        else:
            if in_table:
                # 表格结束
                in_table = False
                if table_line_count < 2:
                    errors.append(f"行 {line_num-1}: 表格至少需要标题行和分隔行")
                table_line_count = 0
                header_columns = 0
    
    return len(errors) == 0, errors

def fix_common_markdown_issues(markdown_content: str) -> str:
    """
    修复常见的Markdown格式问题
    
    Args:
        markdown_content: 原始Markdown内容
        
    Returns:
        str: 修复后的Markdown内容
    """
    # 修复多余的空行（超过2个连续空行改为2个）
    markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content)
    
    # 修复链接中的未编码空格
    def fix_link_spaces(match):
        text, url = match.groups()
        fixed_url = url.replace(' ', '%20')
        return f'[{text}]({fixed_url})'
    
    markdown_content = re.sub(r'\[([^\]]*)\]\(([^)]*)\)', fix_link_spaces, markdown_content)
    
    # 修复表格前后的空行
    lines = markdown_content.split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines):
        fixed_lines.append(line)
        
        # 在表格前添加空行
        if '|' in line and line.strip():
            if i > 0 and lines[i-1].strip() and '|' not in lines[i-1]:
                fixed_lines.insert(-1, '')
        
        # 在表格后添加空行
        if i < len(lines) - 1:
            if '|' in line and line.strip() and '|' not in lines[i+1] and lines[i+1].strip():
                fixed_lines.append('')
    
    return '\n'.join(fixed_lines)

def normalize_url(url: str) -> str:
    """标准化URL，移除锚点等，用于重复检测"""
    parsed = urlparse(url)
    # 移除fragment（锚点）和query参数中的特定部分
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

def preprocess_urls_in_text(text: str) -> str:
    """预处理文本中的URL链接，将href中的URL标准化"""
    def replace_url(match):
        full_match = match.group(0)
        url = match.group(1)
        # 对URL进行标准化处理
        normalized_url = normalize_url(url)
        # 替换原始URL
        return full_match.replace(url, normalized_url)
    
    # 匹配 <a href=\"...\"> 格式的链接
    pattern = r'<a href=\\"([^"]+)\\">'
    processed_text = re.sub(pattern, replace_url, text)
    
    return processed_text

def post_process_report(raw: str) -> str:
    """
    后处理报告内容，移除所有的 div 和 span HTML 标签
    独立处理开始标签和结束标签，保留标签中间的内容
    
    Args:
        raw: 原始字符串，可能包含 div 和 span 标签
        
    Returns:
        str: 移除 div 和 span 标签后的字符串
    """
    # 移除 div 开始标签（包括带属性的）
    # 匹配 <div> 或 <div 任何属性>
    raw = re.sub(r'<div[^>]*>', '', raw)
    
    # 移除 div 结束标签
    raw = re.sub(r'</div>', '', raw)
    
    # 移除 span 开始标签（包括带属性的）
    # 匹配 <span> 或 <span 任何属性>
    raw = re.sub(r'<span[^>]*>', '', raw)
    
    # 移除 span 结束标签
    raw = re.sub(r'</span>', '', raw)
    
    return raw

def process_html_content(html_content: str) -> str:
    """
    处理HTML内容的完整流程：URL标准化 + HTML标签清理
    
    Args:
        html_content: 原始HTML内容
        
    Returns:
        str: 处理后的HTML内容
    """
    # 步骤1: 预处理URL链接
    html_content = preprocess_urls_in_text(html_content)
    
    # 步骤2: 移除div和span标签
    html_content = post_process_report(html_content)
    
    return html_content 