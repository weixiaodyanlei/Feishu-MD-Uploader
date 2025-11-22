import sys
sys.path.insert(0, '/home/carpe/code/py_code/feishu-md-uploader')

from lark_oapi.api.docx.v1.model import *
from urllib.parse import quote

# Test creating a text element with a link
url = "https://www.feishu.cn"
encoded_url = quote(url, safe=':/@?=&')

print(f"Original URL: {url}")
print(f"Encoded URL: {encoded_url}")

# Create link
link = Link.builder().url(encoded_url).build()
print(f"\nLink object: {link}")
print(f"Link attributes: {[x for x in dir(link) if not x.startswith('_')]}")

# Create text element style with link
style = TextElementStyle.builder() \
    .bold(False) \
    .link(link) \
    .build()

print(f"\nStyle object: {style}")
print(f"Style.link: {style.link if hasattr(style, 'link') else 'NO LINK ATTR'}")

# Create text run
text_run = TextRun.builder() \
    .content("Click here") \
    .text_element_style(style) \
    .build()

print(f"\nTextRun object: {text_run}")

# Create text element
text_element = TextElement.builder().text_run(text_run).build()

print(f"\nTextElement object: {text_element}")

# Try to serialize
import json
def dump(obj):
    if hasattr(obj, '__dict__'):
        return {k: dump(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
    elif isinstance(obj, list):
        return [dump(i) for i in obj]
    else:
        return obj

print(f"\nSerialized:")
print(json.dumps(dump(text_element), indent=2, default=str))
