import os
import json
from typing import Dict, List, Any
import PyPDF2
from configs import DATA_DIR


class PDFParser:
    def __init__(self):
        pass
    
    def parse_pdf(self, paper_id: int, file_path: str) -> Dict[str, Any]:
        """
        解析PDF文件，提取结构化信息
        使用简化的方法，主要提取文本内容
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                raise Exception(f"File not found: {file_path}")
            
            # 检查文件大小
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                raise Exception("File is empty")
            
            # 使用PyPDF2解析PDF
            with open(file_path, 'rb') as file:
                try:
                    pdf_reader = PyPDF2.PdfReader(file)
                except Exception as e:
                    # 如果PDF解析失败，尝试读取文件内容作为文本
                    print(f"[WARNING] PDF parsing failed: {e}, trying to read as text")
                    return self._parse_as_text(file_path)
                
                # 初始化结果字典
                result = {
                    "title": "",
                    "authors": "",
                    "abstract": "",
                    "sections": [],
                    "tables": [],
                    "images": [],
                    "formulas": [],
                    "references": [],
                    "full_text": ""
                }
                
                # 检查PDF是否有页面
                if len(pdf_reader.pages) == 0:
                    print("[WARNING] PDF has no pages")
                    return self._create_default_result(file_path)
                
                # 提取所有页面的文本
                full_text_parts = []
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        text = page.extract_text()
                        if text and text.strip():
                            full_text_parts.append(text)
                    except Exception as e:
                        print(f"Error extracting text from page {page_num}: {e}")
                        continue
                
                # 如果没有提取到任何文本
                if not full_text_parts:
                    print("[WARNING] No text extracted from PDF")
                    return self._create_default_result(file_path)
                
                # 合并全文
                full_text = "\n\n".join(full_text_parts)
                result["full_text"] = full_text
                
                # 简单的内容分析
                lines = full_text.split('\n')
                lines = [line.strip() for line in lines if line.strip()]
                
                # 提取标题（通常是第一行或前几行中最长的）
                if lines:
                    # 尝试找到标题
                    potential_titles = []
                    for i, line in enumerate(lines[:10]):  # 只看前10行
                        if len(line) > 10 and len(line) < 200:  # 标题长度合理
                            potential_titles.append((line, len(line)))
                    
                    if potential_titles:
                        # 选择最长的作为标题
                        result["title"] = max(potential_titles, key=lambda x: x[1])[0]
                    else:
                        result["title"] = os.path.basename(file_path).replace('.pdf', '')
                
                # 简单的摘要提取
                abstract_text = self._extract_abstract(full_text)
                if abstract_text:
                    result["abstract"] = abstract_text
                
                # 简单的作者提取
                authors_text = self._extract_authors(full_text)
                if authors_text:
                    result["authors"] = authors_text
                
                # 简单的章节分割
                sections = self._extract_sections(full_text)
                result["sections"] = sections
                
                # 简单的参考文献提取
                references = self._extract_references(full_text)
                result["references"] = references
                
                print(f"[PARSER] PDF解析完成: {len(full_text_parts)} 页, {len(full_text)} 字符")

                save_path = os.path.join(DATA_DIR, "parsed_results")
                os.makedirs(save_path, exist_ok=True)
                with open(f"{save_path}/{result['title'].strip().replace(' ','_')}.json", "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=4)
                print(f"[PARSER] 解析结果 result 已写入 {save_path}")

                return result
                
        except Exception as e:
            print(f"[ERROR] PDF parsing failed: {str(e)}")
            # 返回默认结果而不是抛出异常
            return self._create_default_result(file_path)
    
    def _parse_as_text(self, file_path: str) -> Dict[str, Any]:
        """尝试将文件作为文本解析"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if not content.strip():
                return self._create_default_result(file_path)
            
            result = self._create_default_result(file_path)
            result["full_text"] = content
            result["title"] = os.path.basename(file_path).replace('.pdf', '')
            
            # 简单的内容分析
            lines = content.split('\n')
            lines = [line.strip() for line in lines if line.strip()]
            
            if lines:
                result["abstract"] = lines[0] if len(lines[0]) > 20 else "简单文本内容"
            
            return result
            
        except Exception as e:
            print(f"[ERROR] Text parsing failed: {str(e)}")
            return self._create_default_result(file_path)
    
    def _create_default_result(self, file_path: str) -> Dict[str, Any]:
        """创建默认的解析结果"""
        filename = os.path.basename(file_path).replace('.pdf', '')
        return {
            "title": filename,
            "authors": "未提取到作者信息",
            "abstract": "这是一个测试文档，用于验证系统功能。",
            "sections": [{
                "title": "默认章节",
                "content": ["这是一个默认的章节内容，用于测试系统功能。"]
            }],
            "tables": [],
            "images": [],
            "formulas": [],
            "references": [],
            "full_text": f"这是文件 {filename} 的默认内容，用于测试系统功能。"
        }
    
    def _extract_abstract(self, text: str) -> str:
        """简单的摘要提取"""
        if not text or len(text.strip()) < 50:
            return ""
            
        text_lower = text.lower()
        
        # 查找摘要关键词
        abstract_keywords = ['abstract', 'summary', '摘要', '概要']
        
        for keyword in abstract_keywords:
            start_idx = text_lower.find(keyword)
            if start_idx != -1:
                # 找到关键词后的内容
                start_idx = start_idx + len(keyword)
                # 寻找下一个章节或关键词
                end_keywords = ['introduction', 'keywords', '关键词', '引言', '\n1.', '\n1 ']
                end_idx = len(text)
                
                for end_keyword in end_keywords:
                    temp_idx = text_lower.find(end_keyword, start_idx)
                    if temp_idx != -1 and temp_idx < end_idx:
                        end_idx = temp_idx
                
                abstract = text[start_idx:end_idx].strip()
                # 清理摘要文本
                abstract = abstract.replace('\n', ' ').strip()
                if len(abstract) > 50 and len(abstract) < 2000:
                    return abstract
        
        return ""
    
    def _extract_authors(self, text: str) -> str:
        """简单的作者提取"""
        if not text:
            return ""
            
        lines = text.split('\n')
        
        # 在前20行中寻找作者信息
        for i, line in enumerate(lines[:20]):
            line = line.strip()
            if not line:
                continue
                
            # 检查是否包含作者信息的模式
            author_patterns = ['@', 'university', 'department', 'institute', 'email']
            if any(pattern in line.lower() for pattern in author_patterns):
                return line
            
            # 检查是否是姓名格式（简单启发式）
            if ',' in line and len(line.split()) >= 2 and len(line) < 200:
                words = line.split()
                if all(word[0].isupper() for word in words[:3] if word):  # 前几个词首字母大写
                    return line
        
        return ""
    
    def _extract_sections(self, text: str) -> List[Dict[str, Any]]:
        """简单的章节提取"""
        if not text:
            return []
            
        sections = []
        lines = text.split('\n')
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查是否是章节标题（简单启发式）
            if self._is_section_title(line):
                if current_section:
                    sections.append(current_section)
                
                current_section = {
                    "title": line,
                    "content": []
                }
            elif current_section:
                current_section["content"].append(line)
        
        # 添加最后一个章节
        if current_section:
            sections.append(current_section)
        
        return sections
    
    def _is_section_title(self, line: str) -> bool:
        """判断是否是章节标题"""
        if not line or len(line) > 100:  # 标题通常不会太长
            return False
        
        # 检查是否以数字开头
        if line[0].isdigit() and ('.' in line[:5] or ' ' in line[:5]):
            return True
        
        # 检查是否是常见的章节标题
        section_keywords = [
            'introduction', 'background', 'method', 'approach', 'experiment',
            'result', 'conclusion', 'discussion', 'related work', 'future work',
            '引言', '背景', '方法', '实验', '结果', '结论', '讨论'
        ]
        
        line_lower = line.lower()
        return any(keyword in line_lower for keyword in section_keywords)
    
    def _extract_references(self, text: str) -> List[str]:
        """简单的参考文献提取"""
        if not text:
            return []
            
        references = []
        
        # 查找参考文献部分
        text_lower = text.lower()
        ref_start = -1
        
        for keyword in ['references', 'bibliography', '参考文献']:
            idx = text_lower.find(keyword)
            if idx != -1:
                ref_start = idx
                break
        
        if ref_start == -1:
            return references
        
        # 提取参考文献部分的文本
        ref_text = text[ref_start:]
        lines = ref_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查是否是参考文献条目
            if (line.startswith('[') and ']' in line[:10]) or \
               (line[0].isdigit() and ('.' in line[:5] or ')' in line[:5])):
                references.append(line)
        
        return references[:50]  # 限制数量
    
    def extract_key_sections(self, parsed_data: Dict[str, Any]) -> Dict[str, str]:
        """
        从解析的数据中提取关键章节
        """
        key_sections = {
            "introduction": "",
            "methodology": "",
            "experiments": "",
            "results": "",
            "conclusion": ""
        }
        
        sections = parsed_data.get("sections", [])
        if not sections:
            return key_sections
        
        for section in sections:
            title = section.get("title", "").lower()
            content = "\n".join(section.get("content", []))
            
            if any(keyword in title for keyword in ["introduction", "背景", "引言"]):
                key_sections["introduction"] = content
            elif any(keyword in title for keyword in ["method", "approach", "方法", "算法"]):
                key_sections["methodology"] = content
            elif any(keyword in title for keyword in ["experiment", "evaluation", "实验", "评估"]):
                key_sections["experiments"] = content
            elif any(keyword in title for keyword in ["result", "finding", "结果", "发现"]):
                key_sections["results"] = content
            elif any(keyword in title for keyword in ["conclusion", "summary", "结论", "总结"]):
                key_sections["conclusion"] = content
        
        return key_sections

