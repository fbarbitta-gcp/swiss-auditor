# Copyright 2026 Google LLC
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

import markdown
from weasyprint import HTML

def generate_pdf(md_text: str, output_path: str):
    """
    Converts raw Markdown text to a PDF file using WeasyPrint.
    """
    # 1. Convert Markdown to HTML
    html_content = markdown.markdown(md_text, extensions=['tables', 'fenced_code'])
    
    # 2. Add basic styling
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Helvetica', 'Arial', sans-serif; line-height: 1.6; padding: 20px; color: #333; }}
            h1, h2, h3 {{ color: #2c3e50; }}
            h1 {{ border-bottom: 2px solid #eee; padding-bottom: 10px; text-align: center; }}
            h2 {{ margin-top: 30px; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            ul {{ margin-bottom: 20px; }}
            li {{ margin-bottom: 10px; }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    # 3. Convert to PDF using WeasyPrint
    HTML(string=full_html).write_pdf(output_path)

