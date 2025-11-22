from typing import List, Dict, Any
from markdown_it import MarkdownIt
from lark_oapi.api.docx.v1.model import *

class BlockType:
    PAGE = 1
    TEXT = 2
    HEADING1 = 3
    HEADING2 = 4
    HEADING3 = 5
    HEADING4 = 6
    HEADING5 = 7
    HEADING6 = 8
    HEADING7 = 9
    HEADING8 = 10
    HEADING9 = 11
    BULLET = 12
    ORDERED = 13
    CODE = 14
    QUOTE = 15
    DIVIDER = 22
    IMAGE = 27

class MarkdownParser:
    def __init__(self, image_uploader=None, document_id=None):
        self.md = MarkdownIt()
        self.image_uploader = image_uploader
        self.document_id = document_id

    def parse(self, content: str) -> List[Block]:
        tokens = self.md.parse(content)
        blocks = []
        
        i = 0
        while i < len(tokens):
            token = tokens[i]
            
            if token.type == 'heading_open':
                # Handle Heading
                level = int(token.tag[1:])
                # Get content from the next inline token
                inline_token = tokens[i + 1]
                text_elements = self._parse_inline(inline_token)
                
                # Map level to BlockType
                # HEADING1 is 3, so level 1 -> 3, level 2 -> 4...
                block_type = BlockType.HEADING1 + (level - 1)
                
                block = Block.builder() \
                    .block_type(block_type) \
                    .heading1(Text.builder().elements(text_elements).build()) \
                    .build()
                # Note: Feishu SDK might require setting specific heading field (heading1, heading2...)
                # But Block builder usually has generic 'heading' or specific fields.
                # Based on inspect_block.py, it has heading1...heading9.
                # We need to set the correct field dynamically.
                
                # Dynamic field setting
                block = Block.builder().block_type(block_type).build()
                # We need to set the specific heading attribute
                # Since builder pattern in SDK might not support dynamic attribute setting easily without reflection or if/else
                # Let's use if/else for safety or getattr on builder if possible.
                # Builder methods return self.
                
                heading_text = Text.builder().elements(text_elements).build()
                if level == 1: block.heading1 = heading_text
                elif level == 2: block.heading2 = heading_text
                elif level == 3: block.heading3 = heading_text
                elif level == 4: block.heading4 = heading_text
                elif level == 5: block.heading5 = heading_text
                elif level == 6: block.heading6 = heading_text
                elif level == 7: block.heading7 = heading_text
                elif level == 8: block.heading8 = heading_text
                elif level == 9: block.heading9 = heading_text
                
                blocks.append(block)
                i += 2 # Skip inline and heading_close
                
            elif token.type == 'paragraph_open':
                # Handle Paragraph
                if i + 1 < len(tokens) and tokens[i+1].type == 'inline':
                    inline_token = tokens[i + 1]
                    
                    # Check if this paragraph contains an image
                    has_image = False
                    image_token = None
                    for child in inline_token.children:
                        if child.type == 'image':
                            has_image = True
                            image_token = child
                            break
                    
                    if has_image and self.image_uploader and self.document_id:
                        # Step 1: Create empty Image Block
                        # We'll upload and update later
                        src = image_token.attrs.get('src', '')
                        if not src.startswith('http') and not src.startswith('//'):
                            # Create empty Image block
                            block = Block.builder() \
                                .block_type(BlockType.IMAGE) \
                                .image(Image.builder().build()) \
                                .build()
                            blocks.append(block)
                            
                            # Record image info for later upload
                            if not hasattr(self, '_pending_images'):
                                self._pending_images = []
                            self._pending_images.append({
                                'block_index': len(blocks) - 1,
                                'image_path': src,
                                'alt': image_token.content if hasattr(image_token, 'content') else ''
                            })
                        else:
                            # Remote image - treat as text for now
                            text_elements = self._parse_inline(inline_token)
                            block = Block.builder() \
                                .block_type(BlockType.TEXT) \
                                .text(Text.builder().elements(text_elements).build()) \
                                .build()
                            blocks.append(block)
                    else:
                        # Regular Text Block
                        text_elements = self._parse_inline(inline_token)
                        block = Block.builder() \
                            .block_type(BlockType.TEXT) \
                            .text(Text.builder().elements(text_elements).build()) \
                            .build()
                        blocks.append(block)
                    i += 2
                else:
                    i += 1

            elif token.type == 'fence':
                # Handle Code Block
                lang = token.info.strip()
                content = token.content.rstrip()
                
                text_element = TextElement.builder() \
                    .text_run(TextRun.builder().content(content).build()) \
                    .build()
                
                block = Block.builder() \
                    .block_type(BlockType.CODE) \
                    .code(Text.builder()
                        .style(TextStyle.builder().language(self._map_language(lang)).build())
                        .elements([text_element])
                        .build()) \
                    .build()
                blocks.append(block)
                
            elif token.type == 'bullet_list_open':
                i += 1
                continue
                
            elif token.type == 'ordered_list_open':
                i += 1
                continue
                
            elif token.type == 'list_item_open':
                j = i + 1
                while j < len(tokens) and tokens[j].type != 'inline':
                    j += 1
                
                if j < len(tokens) and tokens[j].type == 'inline':
                    text_elements = self._parse_inline(tokens[j])
                    
                    list_type = BlockType.BULLET
                    k = i - 1
                    while k >= 0:
                        if tokens[k].type == 'ordered_list_open':
                            list_type = BlockType.ORDERED
                            break
                        if tokens[k].type == 'bullet_list_open':
                            list_type = BlockType.BULLET
                            break
                        k -= 1
                    
                    block = Block.builder() \
                        .block_type(list_type) \
                        .build()
                    
                    if list_type == BlockType.BULLET:
                        block.bullet = Text.builder().elements(text_elements).build()
                    else:
                        block.ordered = Text.builder().elements(text_elements).build()
                        
                    blocks.append(block)
                    
                while i < len(tokens) and tokens[i].type != 'list_item_close':
                    i += 1
            
            elif token.type == 'hr':
                block = Block.builder() \
                    .block_type(BlockType.DIVIDER) \
                    .divider(Divider.builder().build()) \
                    .build()
                blocks.append(block)

            elif token.type == 'blockquote_open':
                j = i + 1
                while j < len(tokens) and tokens[j].type != 'inline':
                    j += 1
                
                if j < len(tokens) and tokens[j].type == 'inline':
                    text_elements = self._parse_inline(tokens[j])
                    
                    block = Block.builder() \
                        .block_type(BlockType.QUOTE) \
                        .quote(Text.builder().elements(text_elements).build()) \
                        .build()
                    blocks.append(block)
                
                while i < len(tokens) and tokens[i].type != 'blockquote_close':
                    i += 1

            i += 1
            
        return blocks
    
    def get_pending_images(self):
        """Return list of images that need to be uploaded after blocks are created."""
        return getattr(self, '_pending_images', [])

    def _parse_inline(self, token) -> List[TextElement]:
        elements = []
        if not token.children:
            return elements
            
        current_style = {
            "bold": False,
            "italic": False,
            "code_inline": False,
            "strike_through": False,
            "underline": False
        }
        
        current_link_url = None  # Track current link URL
        
        for child in token.children:
            if child.type == 'link_open':
                # Start of a link - extract URL
                current_link_url = child.attrs.get('href', '') if hasattr(child, 'attrs') else ''
                
            elif child.type == 'link_close':
                # End of link
                current_link_url = None

            elif child.type == 'text':
                # Build text run with current styles
                text_run_builder = TextRun.builder().content(child.content)
                
                # Build text element style
                style_builder = TextElementStyle.builder() \
                    .bold(current_style["bold"]) \
                    .italic(current_style["italic"]) \
                    .inline_code(current_style["code_inline"]) \
                    .strikethrough(current_style["strike_through"]) \
                    .underline(current_style["underline"])
                
                # Add link if we're inside a link
                if current_link_url:
                    from urllib.parse import quote
                    # Encode URL completely (including : and /)
                    encoded_url = quote(current_link_url, safe='')
                    style_builder.link(Link.builder().url(encoded_url).build())
                
                text_run_builder.text_element_style(style_builder.build())
                elements.append(TextElement.builder().text_run(text_run_builder.build()).build())
                
            elif child.type == 'code_inline':
                text_run = TextRun.builder() \
                    .content(child.content) \
                    .text_element_style(TextElementStyle.builder().inline_code(True).build()) \
                    .build()
                elements.append(TextElement.builder().text_run(text_run).build())
                
            elif child.type == 'strong_open':
                current_style["bold"] = True
            elif child.type == 'strong_close':
                current_style["bold"] = False
            elif child.type == 'em_open':
                current_style["italic"] = True
            elif child.type == 'em_close':
                current_style["italic"] = False
            
        return elements

    def _map_language(self, lang: str) -> int:
        # Map string language to Feishu enum integer
        # Based on provided CodeLanguage enum
        lang = lang.lower().strip()
        mapping = {
            "plaintext": 1, "text": 1, "txt": 1,
            "abap": 2,
            "ada": 3,
            "apache": 4,
            "apex": 5,
            "assembly": 6, "asm": 6,
            "bash": 7, "sh": 7, "zsh": 7,
            "csharp": 8, "c#": 8, "cs": 8,
            "cpp": 9, "c++": 9, "cc": 9,
            "c": 10,
            "cobol": 11,
            "css": 12,
            "coffeescript": 13, "coffee": 13,
            "d": 14,
            "dart": 15,
            "delphi": 16,
            "django": 17,
            "dockerfile": 18, "docker": 18,
            "erlang": 19,
            "fortran": 20,
            "foxpro": 21,
            "go": 22, "golang": 22,
            "groovy": 23,
            "html": 24,
            "htmlbars": 25,
            "http": 26,
            "haskell": 27, "hs": 27,
            "json": 28,
            "java": 29,
            "javascript": 30, "js": 30, "node": 30,
            "julia": 31,
            "kotlin": 32, "kt": 32,
            "latex": 33, "tex": 33,
            "lisp": 34,
            "logo": 35,
            "lua": 36,
            "matlab": 37,
            "makefile": 38, "make": 38,
            "markdown": 39, "md": 39,
            "nginx": 40, "conf": 40,
            "objectivec": 41, "objective-c": 41, "objc": 41, # Assuming 'Objective' means Objective-C
            "openedgeabl": 42,
            "php": 43,
            "perl": 44, "pl": 44,
            "postscript": 45,
            "powershell": 46, "ps1": 46,
            "prolog": 47,
            "protobuf": 48, "proto": 48,
            "python": 49, "py": 49,
            "r": 50,
            "rpg": 51,
            "ruby": 52, "rb": 52,
            "rust": 53, "rs": 53,
            "sas": 54,
            "scss": 55,
            "sql": 56,
            "scala": 57,
            "scheme": 58,
            "scratch": 59,
            "shell": 60, # Generic shell
            "swift": 61,
            "thrift": 62,
            "typescript": 63, "ts": 63,
            "vbscript": 64, "vbs": 64,
            "visualbasic": 65, "vb": 65, # Assuming 'Visual' means Visual Basic
            "xml": 66,
            "yaml": 67, "yml": 67,
            "cmake": 68,
            "diff": 69,
            "gherkin": 70,
            "graphql": 71,
            "glsl": 72, # OpenGL Shading Language
            "properties": 73, "ini": 73,
            "solidity": 74,
            "toml": 75,
        }
        return mapping.get(lang, 1) # Default to Plain Text
