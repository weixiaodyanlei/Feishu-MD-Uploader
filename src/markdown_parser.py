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
    TABLE = 31
    TABLE_CELL = 32
    TODO = 17

class MarkdownParser:
    def __init__(self, image_uploader=None, document_id=None):
        self.md = MarkdownIt('commonmark', {'html': True}).enable(['table', 'strikethrough'])
        self.image_uploader = image_uploader
        self.document_id = document_id

    def _elements_text_len(self, elements) -> int:
        if not elements:
            return 0
        total = 0
        for el in elements:
            tr = getattr(el, "text_run", None)
            if tr and getattr(tr, "content", None):
                total += len(tr.content)
        return total

    def _make_text_block(self, text_elements, align: int = None):
        """Create a TEXT block only when it has non-empty content."""
        if self._elements_text_len(text_elements) == 0:
            return None
        text_builder = Text.builder().elements(text_elements)
        if align is not None:
            text_builder.style(TextStyle.builder().align(align).build())
        return Block.builder() \
            .block_type(BlockType.TEXT) \
            .text(text_builder.build()) \
            .build()

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

                # Feishu API rejects empty headings; skip if no actual text.
                if self._elements_text_len(text_elements) == 0:
                    i += 2  # Skip inline and heading_close
                    continue
                
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
                        # Create empty Image block
                        src = image_token.attrs.get('src', '')
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
                        # Regular Text Block
                        text_elements = self._parse_inline(inline_token)
                        block = self._make_text_block(text_elements)
                        if block:
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
                list_blocks, new_index = self._parse_list(tokens, i, BlockType.BULLET)
                blocks.extend(list_blocks)
                i = new_index
                continue
                
            elif token.type == 'ordered_list_open':
                list_blocks, new_index = self._parse_list(tokens, i, BlockType.ORDERED)
                blocks.extend(list_blocks)
                i = new_index
                continue
            
            elif token.type == 'html_block':
                # Handle HTML block tags like <center>, <div align="center">, etc.
                content = token.content.strip()
                
                # Check if this is an opening tag that might span multiple blocks
                if content in ['<center>', '<div align="center">', '<div align="left">', '<div align="right">']:
                    # Look ahead to find the closing tag and collect content in between
                    align_value = None
                    if 'center' in content:
                        align_value = 2
                    elif 'left' in content:
                        align_value = 1
                    elif 'right' in content:
                        align_value = 3
                    
                    if align_value:
                        # Collect blocks until we find the closing tag
                        collected_blocks = []
                        j = i + 1
                        closing_tag = '</center>' if '<center>' in content else '</div>'
                        
                        while j < len(tokens):
                            if tokens[j].type == 'html_block' and tokens[j].content.strip() == closing_tag:
                                # Found closing tag, create aligned block with collected content
                                text_elements = []
                                for idx, block in enumerate(collected_blocks):
                                    if block.text and block.text.elements:
                                        text_elements.extend(block.text.elements)
                                        # Add newline between paragraphs (but not after the last one)
                                        if idx < len(collected_blocks) - 1:
                                            newline_element = TextElement.builder() \
                                                .text_run(TextRun.builder()
                                                    .content("\n")
                                                    .text_element_style(TextElementStyle.builder().build())
                                                    .build()) \
                                                .build()
                                            text_elements.append(newline_element)
                                
                                aligned_block = self._make_text_block(text_elements, align=align_value)
                                if aligned_block:
                                    blocks.append(aligned_block)
                                
                                i = j  # Skip to closing tag
                                break
                            elif tokens[j].type == 'paragraph_open':
                                # Process paragraph content
                                if j + 1 < len(tokens) and tokens[j+1].type == 'inline':
                                    inline_elements = self._parse_inline(tokens[j+1])
                                    temp_block = self._make_text_block(inline_elements)
                                    if temp_block:
                                        collected_blocks.append(temp_block)
                            j += 1
                    continue
                
                # Handle single-line alignment tags (original logic)
                align_value = None
                text_content = None
                
                # Check for <center> tag
                if content.startswith('<center>') and content.endswith('</center>'):
                    align_value = 2  # Center
                    text_content = content[8:-9].strip()  # Remove <center> and </center>
                # Check for <div align="..."> tag
                elif content.startswith('<div align='):
                    import re
                    match = re.match(r'<div align=["\']?(center|left|right)["\']?>(.*?)</div>', content, re.DOTALL | re.IGNORECASE)
                    if match:
                        align_type = match.group(1).lower()
                        text_content = match.group(2).strip()
                        if align_type == 'center':
                            align_value = 2
                        elif align_type == 'left':
                            align_value = 1
                        elif align_type == 'right':
                            align_value = 3
                
                if align_value and text_content:
                    # Parse the text_content as Markdown to support formatting
                    inner_tokens = self.md.parse(text_content)
                    text_elements = []
                    
                    for inner_token in inner_tokens:
                        if inner_token.type == 'inline':
                            # Parse inline content (bold, italic, etc.)
                            text_elements.extend(self._parse_inline(inner_token))
                    
                    # If no inline content found, treat as plain text
                    if not text_elements:
                        text_elements = [TextElement.builder()
                            .text_run(TextRun.builder().content(text_content).build())
                            .build()]
                    
                    block = self._make_text_block(text_elements, align=align_value)
                    if block:
                        blocks.append(block)
                # If not recognized alignment tag, ignore it
            
            elif token.type == 'hr':
                block = Block.builder() \
                    .block_type(BlockType.DIVIDER) \
                    .divider(Divider.builder().build()) \
                    .build()
                blocks.append(block)

            elif token.type == 'blockquote_open':
                # Collect all inline contents inside this blockquote.
                # markdown-it tokenizes multi-paragraph quotes as multiple (paragraph_open -> inline -> paragraph_close).
                collected_elements = []
                j = i + 1
                first_inline = True
                while j < len(tokens) and tokens[j].type != 'blockquote_close':
                    if tokens[j].type == 'inline':
                        if not first_inline:
                            newline_element = TextElement.builder() \
                                .text_run(TextRun.builder()
                                    .content("\n")
                                    .text_element_style(TextElementStyle.builder().build())
                                    .build()) \
                                .build()
                            collected_elements.append(newline_element)
                        collected_elements.extend(self._parse_inline(tokens[j]))
                        first_inline = False
                    j += 1

                if collected_elements:
                    block = Block.builder() \
                        .block_type(BlockType.QUOTE) \
                        .quote(Text.builder().elements(collected_elements).build()) \
                        .build()
                    blocks.append(block)

                # Skip to the end of this blockquote; main loop will then i += 1
                i = j

            elif token.type == 'table_open':
                table_block, new_index = self._parse_table(tokens, i)
                blocks.append(table_block)
                i = new_index
                continue

            i += 1
            
        return blocks
    
    def _parse_table(self, tokens, start_index) -> tuple[Block, int]:
        """Parse table tokens and return a Table Block and the new index."""
        rows = [] # List[List[List[Block]]] (Row -> Col -> Content Blocks)
        current_row = []
        current_cell_blocks = []
        
        i = start_index + 1
        while i < len(tokens):
            token = tokens[i]
            
            if token.type == 'table_close':
                break
                
            elif token.type == 'tr_open':
                current_row = []
                
            elif token.type == 'tr_close':
                rows.append(current_row)
                
            elif token.type in ['th_open', 'td_open']:
                current_cell_blocks = []
                
            elif token.type in ['th_close', 'td_close']:
                current_row.append(current_cell_blocks)
                
            elif token.type == 'inline':
                # Parse inline content as a Text Block for the cell
                # Note: Cells can theoretically contain other blocks, but MD tables usually just have inline text
                text_elements = self._parse_inline(token)
                text_block = self._make_text_block(text_elements)
                if text_block:
                    current_cell_blocks.append(text_block)
                
            i += 1
            
        # Calculate dimensions
        row_size = len(rows)
        col_size = len(rows[0]) if rows else 0
        
        # Build Table Cell Blocks (Flat list)
        cell_blocks = []
        for row in rows:
            for cell_content_blocks in row:
                cell_block = Block.builder() \
                    .block_type(BlockType.TABLE_CELL) \
                    .table_cell(TableCell.builder().build()) \
                    .children(cell_content_blocks) \
                    .build()
                cell_blocks.append(cell_block)
                
        # Build Table Block
        table_block = Block.builder() \
            .block_type(BlockType.TABLE) \
            .table(Table.builder()
                .property(TableProperty.builder()
                    .row_size(row_size)
                    .column_size(col_size)
                    .build())
                .build()) \
            .children(cell_blocks) \
            .build()
            
        return table_block, i + 1
    
    def _parse_list(self, tokens, start_index, list_type) -> tuple[List[Block], int]:
        """Recursively parse list tokens."""
        blocks = []
        i = start_index + 1
        
        while i < len(tokens):
            token = tokens[i]
            
            if (list_type == BlockType.BULLET and token.type == 'bullet_list_close') or \
               (list_type == BlockType.ORDERED and token.type == 'ordered_list_close'):
                return blocks, i + 1
                
            elif token.type == 'list_item_open':
                # Parse content of list item
                # Content usually starts with paragraph_open -> inline -> paragraph_close
                # Or nested list
                
                current_block = None
                children = []
                
                j = i + 1
                while j < len(tokens) and tokens[j].type != 'list_item_close':
                    sub_token = tokens[j]
                    
                    if sub_token.type == 'inline':
                        # Found text content
                        text_elements = self._parse_inline(sub_token)
                        
                        # Check for Todo
                        is_todo = False
                        is_checked = False
                        
                        # Check first text element for [ ] or [x]
                        if text_elements and text_elements[0].text_run:
                            content = text_elements[0].text_run.content
                            if content.startswith('[ ] ') or content.startswith('[x] '):
                                is_todo = True
                                is_checked = content.startswith('[x] ')
                                # Remove the marker from content
                                text_elements[0].text_run.content = content[4:]
                        
                        if is_todo:
                            current_block = Block.builder() \
                                .block_type(BlockType.TODO) \
                                .todo(Text.builder()
                                    .style(TextStyle.builder().done(is_checked).build())
                                    .elements(text_elements)
                                    .build()) \
                                .build()
                        else:
                            current_block = Block.builder() \
                                .block_type(list_type) \
                                .build()
                            
                            if list_type == BlockType.BULLET:
                                current_block.bullet = Text.builder().elements(text_elements).build()
                            else:
                                current_block.ordered = Text.builder().elements(text_elements).build()
                                
                    elif sub_token.type == 'bullet_list_open':
                        nested_blocks, new_j = self._parse_list(tokens, j, BlockType.BULLET)
                        children.extend(nested_blocks)
                        j = new_j - 1 # Adjust for loop increment
                        
                    elif sub_token.type == 'ordered_list_open':
                        nested_blocks, new_j = self._parse_list(tokens, j, BlockType.ORDERED)
                        children.extend(nested_blocks)
                        j = new_j - 1
                        
                    j += 1
                
                if current_block:
                    if children:
                        current_block.children = children
                    blocks.append(current_block)
                
                i = j # Move main loop to list_item_close
                
            i += 1
            
    def get_pending_images(self):
        """Return list of images that need to be uploaded after blocks are created."""
        return getattr(self, '_pending_images', [])

    def _parse_inline(self, token):
        elements = []
        # Track active styles
        style_state = {
            'bold': False,
            'italic': False,
            'strike': False,
            'underline': False,
            'code': False
        }
        current_link_url = None
        
        for child in token.children:
            if child.type == 'text':
                text_style_builder = TextElementStyle.builder() \
                    .bold(style_state['bold']) \
                    .italic(style_state['italic']) \
                    .strikethrough(style_state['strike']) \
                    .underline(style_state['underline']) \
                    .inline_code(style_state['code'])
                
                # Add link if we're inside one
                if current_link_url:
                    from urllib.parse import quote
                    encoded_url = quote(current_link_url, safe='')
                    text_style_builder.link(Link.builder().url(encoded_url).build())
                
                text_run = TextRun.builder() \
                    .content(child.content) \
                    .text_element_style(text_style_builder.build()) \
                    .build()
                    
                element = TextElement.builder().text_run(text_run).build()
                elements.append(element)
                
            elif child.type == 'code_inline':
                text_style_builder = TextElementStyle.builder() \
                    .inline_code(True) \
                    .bold(style_state['bold']) \
                    .italic(style_state['italic']) \
                    .strikethrough(style_state['strike']) \
                    .underline(style_state['underline'])
                
                if current_link_url:
                    from urllib.parse import quote
                    encoded_url = quote(current_link_url, safe='')
                    text_style_builder.link(Link.builder().url(encoded_url).build())
                
                text_run = TextRun.builder() \
                    .content(child.content) \
                    .text_element_style(text_style_builder.build()) \
                    .build()
                    
                element = TextElement.builder().text_run(text_run).build()
                elements.append(element)
                
            elif child.type == 'strong_open':
                style_state['bold'] = True
            elif child.type == 'strong_close':
                style_state['bold'] = False
                
            elif child.type == 'em_open':
                style_state['italic'] = True
            elif child.type == 'em_close':
                style_state['italic'] = False
                
            elif child.type == 's_open':  # Markdown strikethrough ~~text~~
                style_state['strike'] = True
            elif child.type == 's_close':
                style_state['strike'] = False
                
            elif child.type == 'link_open':
                current_link_url = child.attrs.get('href', '') if hasattr(child, 'attrs') else ''
            elif child.type == 'link_close':
                current_link_url = None
                
            elif child.type == 'softbreak':
                # Add newline for soft breaks
                text_run = TextRun.builder() \
                    .content("\n") \
                    .text_element_style(TextElementStyle.builder().build()) \
                    .build()
                element = TextElement.builder().text_run(text_run).build()
                elements.append(element)
                
            elif child.type == 'html_inline':
                tag = child.content.lower()
                if tag in ['<b>', '<strong>']:
                    style_state['bold'] = True
                elif tag in ['</b>', '</strong>']:
                    style_state['bold'] = False
                elif tag in ['<i>', '<em>']:
                    style_state['italic'] = True
                elif tag in ['</i>', '</em>']:
                    style_state['italic'] = False
                elif tag in ['<s>', '<strike>', '<del>']:
                    style_state['strike'] = True
                elif tag in ['</s>', '</strike>', '</del>']:
                    style_state['strike'] = False
                elif tag == '<u>':
                    style_state['underline'] = True
                elif tag == '</u>':
                    style_state['underline'] = False
                elif tag == '<br>' or tag == '<br/>':
                    # Add newline
                    text_run = TextRun.builder() \
                        .content("\n") \
                        .text_element_style(TextElementStyle.builder().build()) \
                        .build()
                    element = TextElement.builder().text_run(text_run).build()
                    elements.append(element)
            
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
