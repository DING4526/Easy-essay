import os
import json
from typing import Dict, List, Any
from unstructured.partition.pdf import partition_pdf

from configs import DATA_DIR
OUTPUT_BASE_DIR = os.path.join(DATA_DIR, "parsed_results")
os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)

class PDFParser:
    def __init__(self):
        pass

    def parse_pdf(self, paper_id: int, file_path: str) -> Dict[str, Any]:
        """
        解析PDF文件，提取结构化信息
        """
        try:
            OUTPUT_DIR = os.path.join(OUTPUT_BASE_DIR, f"paper_{paper_id}")
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            # 使用unstructured解析PDF
            elements = partition_pdf(
                filename=file_path,
                strategy="hi_res",  # 高分辨率策略，更好地识别表格和图像
                infer_table_structure=True,  # 推断表格结构
                extract_images_in_pdf=True,  # 提取图像
                extract_image_block_types=["Image", "Table"],  # 提取图像和表格
                extract_image_block_output_dir=os.path.join(OUTPUT_DIR, "figures"),
                extract_image_block_to_payload=False,
            )

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

            # 分析元素
            current_section = None
            full_text_parts = []

            for element in elements:
                element_type = str(type(element).__name__)
                text = element.text if hasattr(element, 'text') else str(element)

                # 添加到全文
                full_text_parts.append(text)

                # 根据元素类型进行分类
                if element_type == "Title":
                    if not result["title"]:  # 第一个标题作为论文标题
                        result["title"] = text
                    else:
                        # 其他标题作为章节标题
                        current_section = {
                            "title": text,
                            "content": []
                        }
                        result["sections"].append(current_section)

                elif element_type == "NarrativeText":
                    # 检查是否是摘要
                    if self._is_abstract(text):
                        result["abstract"] = text
                    # 检查是否是作者信息
                    elif self._is_authors(text):
                        result["authors"] = text
                    # 检查是否是参考文献
                    elif self._is_reference(text):
                        result["references"].append(text)
                    else:
                        # 普通段落文本
                        if current_section:
                            current_section["content"].append(text)
                        else:
                            # 如果没有当前章节，创建一个默认章节
                            if not result["sections"]:
                                result["sections"].append({
                                    "title": "Introduction",
                                    "content": []
                                })
                                current_section = result["sections"][0]
                            current_section["content"].append(text)

                elif element_type == "Table":
                    result["tables"].append({
                        "content": text,
                        "metadata": element.metadata.to_dict() if hasattr(element, 'metadata') else {}
                    })

                elif element_type == "Image":
                    result["images"].append({
                        "content": text,
                        "metadata": element.metadata.to_dict() if hasattr(element, 'metadata') else {}
                    })

                elif element_type == "Formula":
                    result["formulas"].append(text)

                elif element_type == "ListItem":
                    if current_section:
                        current_section["content"].append(f"• {text}")

            # 设置全文
            result["full_text"] = "\n\n".join(full_text_parts)

            # 后处理：如果没有找到标题，使用文件名
            if not result["title"]:
                result["title"] = os.path.basename(file_path).replace('.pdf', '')

            print(f"[PARSER] PDF解析完毕: {len(full_text_parts)} 页, {len(result['full_text'])} 字符")
            save_path = os.path.join(OUTPUT_DIR, f"{result['title'].strip().replace(' ', '_')}.json")
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
            print(f"[PARSER] 解析结果 result 已写入 {save_path}")

            return result

        except Exception as e:
            raise Exception(f"PDF parsing failed: {str(e)}")

    def _is_abstract(self, text: str) -> bool:
        """判断是否是摘要"""
        text_lower = text.lower()
        abstract_keywords = ['abstract', 'summary', '摘要', '概要']
        return any(keyword in text_lower for keyword in abstract_keywords) and len(text) > 50

    def _is_authors(self, text: str) -> bool:
        """判断是否是作者信息"""
        # 简单的启发式规则
        if len(text) > 200:  # 作者信息通常不会太长
            return False

        # 检查是否包含常见的作者信息模式
        author_patterns = [
            '@', 'university', 'department', 'institute', 'college',
            '大学', '学院', '研究所', '实验室'
        ]
        text_lower = text.lower()
        return any(pattern in text_lower for pattern in author_patterns)

    def _is_reference(self, text: str) -> bool:
        """判断是否是参考文献"""
        text_lower = text.lower()
        ref_patterns = [
            'references', 'bibliography', '参考文献',
            '[1]', '[2]', '[3]', '(1)', '(2)', '(3)'
        ]
        return any(pattern in text_lower for pattern in ref_patterns)

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

        for section in parsed_data.get("sections", []):
            title = section["title"].lower()
            content = "\n".join(section["content"])

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

