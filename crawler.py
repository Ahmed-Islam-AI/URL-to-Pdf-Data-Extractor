# import subprocess
# import sys
# import asyncio
# import os
# from urllib.parse import urlparse, urljoin
# from crawl4ai import AsyncWebCrawler

# class DocumentationSpider:
#     def __init__(self, base_url, output_file="full_documentation.md", max_pages=50):
#         self.base_url = base_url
#         self.domain = urlparse(base_url).netloc
#         self.output_file = output_file
#         self.max_pages = max_pages
#         self.visited = set()
#         self.queue = [base_url]
#         self.crawled_count = 0

#     def is_valid_link(self, link):
#         """
#         Checks if the link is internal, not visited, and not a file/asset.
#         """
#         parsed = urlparse(link)
        
#         # Ensure it's the same domain
#         if parsed.netloc != self.domain:
#             return False
            
#         # Filter out static assets and fragments
#         exclude_ext = {'.png', '.jpg', '.jpeg', '.gif', '.css', '.js', '.pdf', '.svg', '.zip'}
#         if any(parsed.path.endswith(ext) for ext in exclude_ext):
#             return False
            
#         # Remove query params and fragments for uniqueness check
#         clean_link = link.split('#')[0].split('?')[0]
        
#         if clean_link in self.visited:
#             return False
            
#         return True

#     async def run(self):
#         # Clear existing file
#         with open(self.output_file, "w", encoding="utf-8") as f:
#             f.write(f"# Documentation for {self.base_url}\n\n")

#         print(f"🕷️  Starting crawl on: {self.base_url}")

#         # Initialize the crawler context
#         async with AsyncWebCrawler(verbose=True) as crawler:
            
#             while self.queue and self.crawled_count < self.max_pages:
#                 current_url = self.queue.pop(0)
                
#                 # Double check visited (in case duplicates entered queue)
#                 clean_url = current_url.split('#')[0].split('?')[0]
#                 if clean_url in self.visited:
#                     continue

#                 print(f"Processing [{self.crawled_count + 1}/{self.max_pages}]: {current_url}")
                
#                 # --- CRAWL ACTION ---
#                 # magic=True handles lazy loading JS and anti-bot protections
#                 result = await crawler.arun(url=current_url, magic=True)

#                 if not result.success:
#                     print(f"❌ Failed to crawl {current_url}")
#                     continue

#                 self.visited.add(clean_url)
#                 self.crawled_count += 1

#                 # --- SAVE CONTENT ---
#                 # We append to the file immediately to save progress
#                 self._append_to_file(current_url, result.markdown)

#                 # --- DISCOVER LINKS ---
#                 # result.links contains all links found on the page
#                 if result.links:
#                     internal_links = result.links.get("internal", [])
#                     for link_data in internal_links:
#                         href = link_data.get('href')
#                         full_url = urljoin(current_url, href)
                        
#                         if self.is_valid_link(full_url):
#                             # Add to queue but don't mark visited yet
#                             self.queue.append(full_url)

#         print(f"\n✅ Crawl Complete! Saved {self.crawled_count} pages to {self.output_file}")

#     def _append_to_file(self, url, content):
#         """Appends the clean markdown content to the master file"""
#         with open(self.output_file, "a", encoding="utf-8") as f:
#             f.write(f"\n\n---\n\n")
#             f.write(f"## Source: {url}\n\n")
#             f.write(content)

# # --- CONFIGURATION ---
# if __name__ == "__main__":
#     TARGET_WEBSITE = "https://www.irsolutions.tech/" 
#     OUTPUT_MD = "ir_docs.md"
#     OUTPUT_PDF = "irsolutions_docs.pdf"
    
#     # 1. Run the Spider
#     spider = DocumentationSpider(
#         base_url=TARGET_WEBSITE, 
#         output_file=OUTPUT_MD,
#         max_pages=20 
#     )
#     asyncio.run(spider.run())

#     # 2. Convert to PDF safely using Subprocess
#     print("📄 Converting to PDF...")
    
#     try:
#         # This runs the command: "python -m mdpdf -o fastapi_docs.pdf fastapi_docs.md"
#         # Using sys.executable ensures we use the same Python environment that has the library installed
#         command = [
#             sys.executable, "-m", "mdpdf", 
#             "-o", OUTPUT_PDF, 
#             OUTPUT_MD
#         ]
        
#         result = subprocess.run(command, capture_output=True, text=True)
        
#         if result.returncode == 0:
#             print(f"✅ PDF Successfully created: {OUTPUT_PDF}")
#         else:
#             print(f"⚠️ PDF Conversion Warning:\n{result.stderr}")
            
#     except Exception as e:
#         print(f"❌ PDF Conversion Failed: {e}")
#         print("Tip: You can still use the generated Markdown file directly!")





















import asyncio
import os
import re
import logging
import hashlib
from collections import Counter
from urllib.parse import urlparse, urljoin
from crawl4ai import AsyncWebCrawler
from markdown2 import markdown
from xhtml2pdf import pisa 
from bs4 import BeautifulSoup # <--- NEW: For deep cleaning

class DocumentationSpider:
    def __init__(self, base_url, output_file="ir_docs.md", max_pages=20, max_block_repeats=1):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.output_file = output_file
        self.max_pages = max_pages
        self.visited = set()
        self.queue = [base_url]
        self.crawled_count = 0
        self.max_block_repeats = max_block_repeats
        self.block_fingerprints = Counter()

    def is_valid_link(self, link):
        parsed = urlparse(link)
        if parsed.netloc != self.domain:
            return False
        exclude_ext = {'.png', '.jpg', '.jpeg', '.gif', '.css', '.js', '.pdf', '.svg', '.zip', '.ico'}
        if any(parsed.path.endswith(ext) for ext in exclude_ext):
            return False
        clean_link = link.split('#')[0].split('?')[0]
        if clean_link in self.visited:
            return False
        return True

    async def run(self):
        # Clear existing file
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(f"# Documentation for {self.base_url}\n\n")

        print(f"🕷️  Starting crawl on: {self.base_url}")

        async with AsyncWebCrawler(verbose=True) as crawler:
            while self.queue and self.crawled_count < self.max_pages:
                current_url = self.queue.pop(0)
                clean_url = current_url.split('#')[0].split('?')[0]
                if clean_url in self.visited:
                    continue

                print(f"Processing [{self.crawled_count + 1}/{self.max_pages}]: {current_url}")
                
                result = await crawler.arun(url=current_url, magic=True)

                if not result.success:
                    print(f"❌ Failed to crawl {current_url}")
                    continue

                self.visited.add(clean_url)
                self.crawled_count += 1
                cleaned_markdown = self._clean_markdown(result.markdown)
                if not cleaned_markdown.strip():
                    print(f"⚠️  Skipping {current_url} because only layout content remained.")
                    continue

                self._append_to_file(current_url, cleaned_markdown)

                if result.links:
                    internal_links = result.links.get("internal", [])
                    for link_data in internal_links:
                        href = link_data.get('href')
                        full_url = urljoin(current_url, href)
                        if self.is_valid_link(full_url):
                            self.queue.append(full_url)

        print(f"\n✅ Crawl Complete! Saved {self.crawled_count} pages to {self.output_file}")

    def _append_to_file(self, url, content):
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(f"\n\n<hr>\n\n")
            f.write(f"# Source: {url}\n\n")
            f.write(content)

    def _clean_markdown(self, markdown_blob):
        """
        Remove repeated layout blocks (navbars, footers) across pages and
        aggressively drop boilerplate text segments.
        """
        if not markdown_blob:
            return ""

        blocks = [block.strip() for block in re.split(r'\n{2,}', markdown_blob)]
        filtered_blocks = []

        layout_candidates = []

        for block in blocks:
            if not block:
                continue

            if self._looks_like_layout(block):
                layout_candidates.append(block)
                continue

            fingerprint = self._fingerprint_block(block)
            if not fingerprint:
                filtered_blocks.append(block)
                continue

            if self.block_fingerprints[fingerprint] >= self.max_block_repeats:
                continue

            self.block_fingerprints[fingerprint] += 1
            filtered_blocks.append(block)

        if not filtered_blocks:
            fallback = self._select_fallback_block(layout_candidates or blocks)
            if fallback:
                filtered_blocks.append(fallback)

        return "\n\n".join(filtered_blocks).strip()

    def _fingerprint_block(self, block):
        normalized = re.sub(r'\s+', ' ', block).strip().lower()
        normalized = re.sub(r'[^a-z0-9 ]+', '', normalized)
        if len(normalized) < 40:
            return None
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def _looks_like_layout(self, block):
        surface = block.lower()

        layout_keywords = [
            "navigation", "nav", "footer", "copyright",
            "all rights reserved", "cookie", "privacy policy",
            "subscribe", "newsletter", "terms of service",
            "hero section", "menu", "contact us"
        ]

        if any(keyword in surface for keyword in layout_keywords):
            return True

        # Drop blocks that are mostly links or short lists
        link_like = re.findall(r'\[[^\]]+\]\([^)]+\)', block)
        if link_like and len(link_like) >= 3:
            return True

        # Drop blocks that are mostly uppercase short labels (menu items)
        tokens = surface.split()
        raw_tokens = block.split()
        uppercase_hits = sum(token.isupper() for token in raw_tokens)
        token_count = len(raw_tokens)
        if tokens and len(tokens) <= 15 and token_count and (uppercase_hits / token_count) >= 0.6:
            return True

        return False

    def _select_fallback_block(self, blocks):
        """
        Pick the most content-heavy block when everything looked like layout.
        This prevents blank pages when the heuristics are too aggressive.
        """
        if not blocks:
            return ""
        # Prefer longer blocks that contain sentences.
        scored = sorted(
            blocks,
            key=lambda b: (len(b), b.count(".") + b.count("!")),
            reverse=True,
        )
        return scored[0] if scored else ""

def convert_md_to_pdf(source_md, output_pdf):
    """
    Converts Markdown to PDF with aggressive HTML sanitization to prevent crashes.
    """
    # Silence warnings
    logging.getLogger("xhtml2pdf").setLevel(logging.CRITICAL)

    try:
        print("📄 Reading Markdown file...")
        with open(source_md, "r", encoding="utf-8") as f:
            md_content = f.read()
        
        # 1. Convert Markdown to HTML
        raw_html = markdown(
            md_content, 
            extras=["tables", "fenced-code-blocks", "cuddled-lists", "break-on-newline"]
        )
        
        # 2. AGGRESSIVE SANITIZATION (The Fix)
        # We use BeautifulSoup to parse the HTML and remove things that crash PDF generators
        print("🧹 Cleaning HTML content...")
        soup = BeautifulSoup(raw_html, "html.parser")
        
        # Remove all 'img' and 'svg' tags entirely
        for tag in soup(["img", "svg", "script", "style", "video", "iframe"]):
            tag.decompose()
            
        # Remove all attributes (classes, styles, ids) from ALL tags
        # This forces the HTML to be "plain" (just <b>, <p>, <table>) which prevents errors
        for tag in soup.find_all(True):
            tag.attrs = {} 

        clean_html = str(soup)
        
        # 3. Apply Safe Styling
        styled_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Helvetica, sans-serif; font-size: 10pt; }}
                h1 {{ font-size: 18pt; color: #2E3E4E; border-bottom: 1px solid #ddd; margin-top: 20pt; }}
                h2 {{ font-size: 14pt; color: #2E3E4E; margin-top: 15pt; }}
                h3 {{ font-size: 12pt; font-weight: bold; margin-top: 10pt; }}
                p {{ margin-bottom: 10pt; text-align: justify; }}
                code {{ font-family: Courier; background-color: #f4f4f4; padding: 2px; }}
                pre {{ background-color: #f4f4f4; padding: 10px; border: 1px solid #ddd; white-space: pre-wrap; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 15pt; }}
                th {{ background-color: #eee; border: 1px solid #ddd; padding: 5px; font-weight: bold; }}
                td {{ border: 1px solid #ddd; padding: 5px; }}
            </style>
        </head>
        <body>
            {clean_html}
        </body>
        </html>
        """

        print("📄 Writing PDF...")
        with open(output_pdf, "wb") as pdf_file:
            pisa_status = pisa.CreatePDF(styled_html, dest=pdf_file)
            
        if pisa_status.err:
            print("❌ PDF generation error")
        else:
            print(f"✅ PDF Successfully created: {output_pdf}")

    except Exception as e:
        print(f"❌ Conversion Failed: {e}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    TARGET_WEBSITE = "https://www.irsolutions.tech" 
    OUTPUT_MD = "ir_docs.md"
    OUTPUT_PDF = "ir_docs.pdf"
    
    # 1. Run the Spider
    spider = DocumentationSpider(
        base_url=TARGET_WEBSITE, 
        output_file=OUTPUT_MD,
        max_pages=10,
        max_block_repeats=1

    )
    asyncio.run(spider.run())

    # 2. Convert
    convert_md_to_pdf(OUTPUT_MD, OUTPUT_PDF)