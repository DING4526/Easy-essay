import os

from unstructured.partition.pdf import partition_pdf

from configs import DATA_DIR

elements = partition_pdf(
    filename="TEST_PDF.pdf",  # 替换为你的 PDF 文件路径
    strategy="hi_res",  # 高质量图文解析
    infer_table_structure=True,  # 表格结构识别
    extract_images_in_pdf=True,
    extract_image_block_types=["Image", "Table"],
    extract_image_block_output_dir=os.path.join(DATA_DIR,"figs"),
    extract_image_block_to_payload=False,
)

for el in elements:
    op = 1 if hasattr(el, 'text') else 0
    print(f"[{op}]{type(el).__name__}: {getattr(el, 'text', '')}")
    if type(el).__name__ == "Table":
        print(el.metadata.to_dict() if hasattr(el, 'metadata') else {})
    if type(el).__name__ == "Image":
        print(el.metadata.to_dict() if hasattr(el, 'metadata') else {})

# import shutil
# print("Tesseract path:", shutil.which("tesseract"))
#
# try:
#     import pytesseract
#     print("pytesseract OK")
# except ImportError:
#     print("pytesseract NOT FOUND")
#
# import sys, os, shutil
#
# print("Python executable:", sys.executable)
# print("sys.path:", sys.path)
# print("PATH env:", os.environ.get("PATH", ""))
# print("Tesseract path:", shutil.which("tesseract"))