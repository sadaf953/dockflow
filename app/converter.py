import os
import pymupdf
import pymupdf4llm

def process_pdf_to_markdown(pdf_path: str, output_dir: str, file_name: str) -> str:
    abs_output_dir = os.path.abspath(output_dir)
    image_dir = os.path.join(abs_output_dir, f"{file_name}_images")
    os.makedirs(image_dir, exist_ok=True)

    try:
        md_text = pymupdf4llm.to_markdown(
            doc=pdf_path,
            write_images=True,
            image_path=image_dir,
            image_format="png"
        )

        if not md_text or len(md_text.strip()) < 50:
            raise ValueError("Output too short")

    except Exception:
        doc = pymupdf.open(pdf_path)
        md_text = ""
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                md_text += f"## Page {page_num + 1}\n\n{text}\n\n"
            else:
                md_text += f"## Page {page_num + 1}\n\n*[Image-based page — text extraction not available]*\n\n"
        doc.close()

    # Return text directly instead of file path
    return md_text