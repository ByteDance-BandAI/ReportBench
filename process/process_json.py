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

def process_openai_json(file_path):
    """
    处理OpenAI对话JSON文件，提取指定信息
    
    Args:
        file_path: JSON文件路径
    
    Returns:
        dict: 包含prompt、answer、activity、reference的字典
    """
    try:
        # 读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 初始化结果字典
        result = {
            'prompt': '',
            'answer': '',
            'activity': '',
            'reference': ''
        }
        
        # 提取messages中的信息
        messages = data.get('messages', [])
        
        # 1. 提取第一个user的content作为prompt
        for message in messages:
            if message.get('role') == 'user':
                result['prompt'] = message.get('content', '')
                break
        
        # 2. 找到连续的两个assistant消息，提取第二个的content作为answer
        assistant_messages = []
        current_assistant_sequence = []
        
        for i, message in enumerate(messages):
            if message.get('role') == 'assistant':
                current_assistant_sequence.append(message)
            else:
                if len(current_assistant_sequence) >= 2:
                    assistant_messages.extend(current_assistant_sequence)
                current_assistant_sequence = []
        
        # 检查最后的序列
        if len(current_assistant_sequence) >= 2:
            assistant_messages.extend(current_assistant_sequence)
        
        # 找到连续的assistant消息中的第二个
        consecutive_assistants = []
        for i in range(len(messages) - 1):
            if (messages[i].get('role') == 'assistant' and 
                messages[i + 1].get('role') == 'assistant'):
                consecutive_assistants = [messages[i], messages[i + 1]]
                break
        
        if len(consecutive_assistants) >= 2:
            result['answer'] = consecutive_assistants[1].get('content', '')
        
        # 3. 提取activity字段
        result['activity'] = data.get('activity', '')
        
        # 4. 提取reference字段
        result['reference'] = data.get('reference', '')
        
        return result
        
    except Exception as e:
        print(f"处理文件时出错: {e}")
        return None

def save_result(result, output_file):
    """
    保存处理结果到JSON文件
    
    Args:
        result: 处理结果字典
        output_file: 输出文件路径
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"结果已保存到: {output_file}")
    except Exception as e:
        print(f"保存文件时出错: {e}")

def main():
    # 处理openai-01.json文件
    input_file = 'temp/openai-01.json'
    output_file = 'processed_data.json'
    
    print(f"开始处理文件: {input_file}")
    
    result = process_openai_json(input_file)
    
    if result:
        print("\n提取的信息:")
        print(f"Prompt (第一个user的content): {result['prompt'][:100]}...")
        print(f"Answer (连续assistant中第二个的content): {result['answer'][:100]}...")
        print(f"Activity字段长度: {len(result['activity'])}")
        print(f"Reference字段长度: {len(result['reference'])}")
        
        # 保存结果
        save_result(result, output_file)
        
        print(f"\n处理完成！结果已保存到 {output_file}")
    else:
        print("处理失败！")

if __name__ == "__main__":
    main() 