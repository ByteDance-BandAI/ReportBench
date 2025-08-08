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

import json
import re
import os
import glob
import argparse
from bs4 import BeautifulSoup, NavigableString


def extract_superscript_prev_and_next_text(soup):
    results = []

    # 递归收集所有文本节点和sup节点到一个list
    node_list = []

    def traverse(node):
        for child in node.children:
            if isinstance(child, NavigableString):
                stripped = child.strip()
                if stripped:
                    node_list.append(('text', stripped, child))
            elif getattr(child, 'name', None):
                if child.name == 'sup' and child.get('class') and 'superscript' in child.get('class'):
                    node_list.append(('sup', child, child))
                traverse(child)

    traverse(soup)

    # 找每个 sup 的前后文本
    for i, (kind, content, node) in enumerate(node_list):
        if kind == 'sup':
            # 向前找最近文本
            prev_text = ''
            for j in range(i-1, -1, -1):
                if node_list[j][0] == 'text':
                    prev_text = node_list[j][1]
                    break
            # 向后找最近文本
            next_text = ''
            for j in range(i+1, len(node_list)):
                if node_list[j][0] == 'text':
                    next_text = node_list[j][1]
                    break

            data_index = node.get('data-turn-source-index', '')
            results.append({
                'data-turn-source-index': data_index,
                'prev_text': prev_text,
                'next_text': next_text
            })

    return results


def replace_superscripts_in_markdown(md_text, data):
    ignore_chars = ['#', '*', '|', '-', '+', '>', '`', '=', '[', ']', '(', ')', '!', '~', ' ', '\n', '\t']
    for _ in range(10):
        ignore_chars.append(str(_))
    no_find_url_count = 0
    start = 0
    for item in data:
        sub_index = item['data-turn-source-index']
        prev_text = item['prev_text']
        next_text = item['next_text']
        potential_index = -1
        while True:
            index = md_text.find(sub_index, start)
            start = index + len(sub_index)
            mismatch_prev, mismatch_next = False, False
            if index == -1:
                if potential_index == -1:
                    item["matched_index"] = -1
                    print(f"[DEBUG] 未找到匹配字段: '{prev_text}' 后面")
                    print(f"[DEBUG] 未找到匹配字段: '{next_text}' 前面")
                    no_find_url_count += 1
                else:
                    item["matched_index"] = potential_index
                start = 0
                break
            # 往前模糊匹配 prev_text
            # print(index)
            i, j = index - 1, len(prev_text) - 1
            while i >= 0 and j >= 0:
                if md_text[i] in ignore_chars:
                    i -= 1
                    continue
                if prev_text[j] in ignore_chars:
                    j -= 1
                    continue
                if md_text[i] != prev_text[j]:
                    break
                i -= 1
                j -= 1
            if j >= 0:
                mismatch_prev = True
            # 往后模糊匹配 next_text
            i, j = index + len(sub_index), 0
            while i < len(md_text) and j < len(next_text):
                if md_text[i] in ignore_chars:
                    i += 1
                    continue
                if next_text[j] in ignore_chars:
                    j += 1
                    continue
                if md_text[i] != next_text[j]:
                    break
                i += 1
                j += 1
            if j != len(next_text):
                mismatch_next = True
            # 成功匹配
            if not mismatch_next and not mismatch_prev:
                item["matched_index"] = index
                start = index + len(sub_index)
                break
            elif mismatch_next and not mismatch_prev and len(prev_text) > 3:
                potential_index = index
            elif mismatch_prev and not mismatch_next and len(next_text) > 3:
                potential_index = index
    print(f"未找到匹配的URL数量: {no_find_url_count}")
    return data


def extract_numbered_links(text):
    results = {}
    lines = text.strip().split('\n')
    for line in lines[1:]:
        match = re.match(r'(\d+)\.', line)
        if match:
            num = match.group(1)
            start = line.rfind('(')
            end = line.rfind(')')
            if start != -1 and end != -1:
                url = line[start+1:end]
                results[num] = f'[{num}]({url})'
    return results


def parse_gemini_article(gemini_json_str, gemini_md_text, debug=False):
    json_data = json.loads(gemini_json_str)
    
    # 检查messages字段是否存在且为列表
    if "messages" not in json_data:
        raise ValueError("JSON文件中缺少'messages'字段")
    
    messages = json_data["messages"]
    if not isinstance(messages, list):
        raise ValueError(f"'messages'字段应该是列表，但实际类型是: {type(messages).__name__}")
    
    if len(messages) == 0:
        raise ValueError("'messages'列表为空")
    
    content_html = messages[-1]["content"]
    soup = BeautifulSoup(content_html, 'html.parser')
    superscript_list = extract_superscript_prev_and_next_text(soup)

    if debug:
        for item in superscript_list:
            print(f'data-turn-source-index: {item["data-turn-source-index"]}')
            print(f'prev_text: {item["prev_text"]}')
            print(f'next_text: {item["next_text"]}')
            # print(f'matched_index: {item["matched_index"]}')
            print("====================")

    superscript_list = replace_superscripts_in_markdown(gemini_md_text, superscript_list)
    superscript_list = sorted(superscript_list, key=lambda x: int(x["matched_index"]), reverse=True)  # 从后往前更新，index不会错乱
    
    # 提取每个引用的映射
    reference_text = gemini_md_text[gemini_md_text.rfind("####"):]
    reference_mapping = extract_numbered_links(reference_text) 
    # 更新 markdown 文本
    trans_md_text = gemini_md_text
    mismatch_count = 0
    for item in superscript_list:
        if item["matched_index"] == -1:
            continue
        formatted_url = reference_mapping.get(item["data-turn-source-index"], "")
        # print(formatted_url)
        if not trans_md_text[item["matched_index"]:].startswith(item["data-turn-source-index"]):
            mismatch_count += 1 # 没找到匹配的字段
            continue
        trans_md_text = trans_md_text[:item["matched_index"]] + formatted_url + trans_md_text[item["matched_index"] + len(item["data-turn-source-index"]):]
    print(f"未找到引用地址的数量: {mismatch_count}")
    trans_md_text = trans_md_text.strip()
    return trans_md_text, reference_mapping


def extract_thoughts_and_browses(gemini_json_str, debug=False):
    json_data = json.loads(gemini_json_str)
    html = json_data["activity"]
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # 遍历所有节点，保持顺序处理 thought-item 与 browse-chip-list
    for node in soup.descendants:
        if isinstance(node, str):
            continue

        # 提取 <thought-item>
        if node.name == "thought-item":
            divs = node.find_all("div")
            header = divs[0].get_text(strip=True) if len(divs) > 0 else ""
            content = divs[1].get_text(strip=True) if len(divs) > 1 else ""
            results.append({
                "type": "thought",
                "header": header,
                "content": content
            })

        # 提取 <browse-chip-list>
        elif node.name == "browse-chip-list":
            links = []
            for chip in node.find_all("browse-web-chip"):
                a_tag = chip.find("a", href=True)
                if a_tag:
                    links.append(a_tag['href'])
            results.append({
                "type": "browse",
                "list": links
            })

    if debug:
        from pprint import pprint
        pprint(results)
    return results


def process_gemini_result(gemini_json_file, gemini_md_file, output_file):
    json_str = open(gemini_json_file).read()
    md_text = open(gemini_md_file).read()
    
    json_data = json.loads(json_str)
    
    # 检查messages字段是否存在且为列表
    if "messages" not in json_data:
        raise ValueError("JSON文件中缺少'messages'字段")
    
    messages = json_data["messages"]
    if not isinstance(messages, list):
        raise ValueError(f"'messages'字段应该是列表，但实际类型是: {type(messages).__name__}")
    
    if len(messages) < 2:
        raise ValueError(f"'messages'列表长度不足，期望至少2个元素，实际: {len(messages)}")
    
    parsed_thinking = extract_thoughts_and_browses(gemini_json_str=json_str, debug=False)
    parsed_md_text, parsed_reference_list = parse_gemini_article(gemini_json_str=json_str, gemini_md_text=md_text, debug=False)
    assert messages[0]["role"] == "user"
    prompt = messages[0]["content"].strip()
    result = {
        "prompt": prompt,
        "response": parsed_md_text,
        "activity": parsed_thinking,
        "initial_plan": messages[1]["content"].replace("更多分析结果生成报告只需要几分钟就可以准备好 修改方案  开始研究", "").strip(),
        "reference": parsed_reference_list
    }
    fout = open(output_file, "w")
    json.dump(result, fout, ensure_ascii=False)


if __name__ == '__main__':
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='处理Gemini结果文件')
    parser.add_argument('--input-dir', default='gemini', 
                       help='输入目录路径，包含gemini JSON和MD文件 (默认: gemini)')
    parser.add_argument('--output-dir', default='result_gemini',
                       help='输出目录路径，用于保存处理后的结果 (默认: result_gemini)')
    
    # 解析命令行参数
    args = parser.parse_args()
    input_dir = args.input_dir
    output_dir = args.output_dir
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 查找所有gemini JSON文件
    json_pattern = os.path.join(input_dir, "*.json")
    json_files = glob.glob(json_pattern)
    
    processed_count = 0
    error_count = 0
    failed_files = []  # 记录失败的文件名
    
    for json_file in json_files:
        try:
            # 获取基础文件名（不包含扩展名）
            base_name = os.path.basename(json_file).replace('.json', '')
            
            # 构造对应的md文件路径
            md_file = os.path.join(input_dir, base_name + '.md')
            
            # 检查md文件是否存在
            if not os.path.exists(md_file):
                print(f"警告：找不到对应的md文件: {md_file}")
                failed_files.append(base_name)  # 记录失败的文件名
                error_count += 1
                continue
            
            # 构造输出文件路径
            output_file = os.path.join(output_dir, base_name + '_parsed.json')
            
            print(f"正在处理: {json_file} 和 {md_file}")
            print(f"输出到: {output_file}")
            
            # 处理文件
            process_gemini_result(json_file, md_file, output_file)
            processed_count += 1
            print(f"成功处理 #{processed_count}: {base_name}")
            
        except Exception as e:
            error_count += 1
            base_name = os.path.basename(json_file).replace('.json', '')
            failed_files.append(base_name)  # 记录失败的文件名
            print(f"处理文件出错 {json_file}: {str(e)}")
            continue
    
    print(f"\n处理完成！")
    print(f"成功处理: {processed_count} 个文件")
    print(f"处理失败: {error_count} 个文件")
    print(f"结果保存在: {output_dir} 目录")
    
    # 输出所有失败的文件名
    if failed_files:
        print(f"\n处理失败的文件列表:")
        for i, failed_file in enumerate(failed_files, 1):
            print(f"{i}. {failed_file}")
    else:
        print(f"\n所有文件都处理成功！")
