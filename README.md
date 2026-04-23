# 🚀 Feishu-MD-Uploader: 飞书 Markdown 文档上传工具

![](docs/asset/logo.png)

## 🌟 项目简介

`Feishu-MD-Uploader` 是一个功能完善的 Python 命令行工具，用于将 Markdown 文档**高效、准确**地上传到飞书云文档（Docx）。

本项目通过飞书开放平台 API，实现了完整的 Markdown 内容解析、本地/远程图片自动上传、以及内容到 Docx JSON 结构的精确转换，确保格式完整地迁移到飞书。

## ✨ 主要特性 (Features)

### 核心功能
* **📝 丰富的文本格式：** 支持粗体、斜体、删除线、下划线、行内代码等
* **🖼️ 图片自动处理：** 自动识别并上传本地图片和远程 URL 图片
* **📊 表格支持：** 完整的 Markdown 表格转换，支持表格内格式化
* **📋 列表功能：** 支持有序、无序、嵌套列表和任务列表（Todo）
* **🔗 链接支持：** Markdown 和 HTML 链接自动转换
* **🎨 HTML 标签：** 支持常用 HTML 格式标签（`<b>`, `<i>`, `<u>`, `<s>`, `<br>`）
* **📐 文本对齐：** 支持居中、左对齐、右对齐（`<center>`, `<div align="...">`）
* **💻 代码高亮：** 支持 40+ 种编程语言的语法高亮
* **🔐 权限管理：** 自动设置文档为"组织内成员可编辑"
* **⚡ Token 自动化：** 自动获取和管理 Tenant Access Token

## 📈 版本演进

- [x] v0.1.0: 正确创建文档
- [x] v0.1.1: 正确设置权限：所有组织内成员可编辑
- [x] v0.1.2: 实现添加文本 blocks（标题、段落、列表、代码等）的支持
- [x] v0.2.0: 实现本地图片上传和图片 Blocks
- [x] v0.2.1: 实现链接支持
- [x] v0.2.2: 实现表格支持
- [x] v0.2.3: 实现外部 URL 图片支持
- [x] v0.2.4: 实现嵌套列表和 Todo 任务列表支持
- [x] v0.2.5: 实现 HTML 标签和文本对齐支持
- [ ] v0.3.0: 改善使用体验

## 🔧 技术栈与依赖

| 分类 | 名称 | 说明 |
| :--- | :--- | :--- |
| **语言环境** | Python 3.9+ (推荐 3.11.2) | |
| **飞书 SDK** | `lark-oapi` >= 1.3.0 | 飞书官方 Python SDK |
| **Markdown 解析** | `markdown-it-py` >= 3.0.0 | 强大的 Markdown 解析库，用于构建 AST |
| **配置管理** | `python-dotenv` >= 1.0.0 | 用于管理敏感配置 |
| **HTTP 请求** | `requests` >= 2.31.0 | 用于下载远程图片 |

## 📦 安装指南

### 1. 克隆仓库

```bash
git clone https://github.com/ZIYAN137/Feishu-MD-Uploader.git
cd Feishu-MD-Uploader
```

### 2. 安装依赖

```bash
# 推荐：创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

**核心依赖：**
- `lark-oapi` - 飞书官方 SDK
- `markdown-it-py` - Markdown 解析器
- `python-dotenv` - 环境变量管理
- `requests` - HTTP 请求库（用于下载远程图片）

## 🔑 配置 (Configuration)

### 1. 飞书开放平台设置

请确保您已在 [飞书开放平台](https://open.feishu.cn/) 创建应用，并获得了 **App ID** 和 **App Secret**。

**应用必须启用以下权限（tenant 级别）：**

**核心权限（必需）：**
- `docx:document` - 云文档完整权限（创建、读取、编辑文档）
- `drive:drive` - 云空间完整权限（上传文件、删除文档）

**权限管理（推荐）：**
- `docs:permission.setting:write_only` - 云文档权限管理权限（设置文档权限）

💡 如果不开通权限管理相关权限，文档仍可正常创建，但权限默认为"仅创建者"。

**权限配置步骤：**
1. 登录 [飞书开放平台控制台](https://open.feishu.cn/app/)
2. 选择或创建你的应用
3. 进入"权限管理"页面
4. 搜索并开通上述权限
5. 获取 App ID 和 App Secret（在"凭证与基础信息"页面）

### 2. 配置密钥

复制 `.env.example` 并重命名为 `.env`，然后填入您的应用凭证：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```ini
# .env 文件
APP_ID="cli_xxxxxxxxxxxxxx"
APP_SECRET="XXXXXXXXXXXXXXXXXXXXXXXXXXX"

# 可选：飞书文档域名（默认为 www.feishu.cn）
FEISHU_DOC_HOST="www.feishu.cn"

# 可选：指定文档创建的目标文件夹（留空则创建在根目录）
FOLDER_TOKEN=""
```

## 🚀 使用方法 (Usage)

### 1. 准备 Markdown 文件

确保您的 Markdown 文件中的图片引用是**本地有效路径**或**可访问的 URL**，例如：

````markdown
# 我的文档标题

这是一段正文内容，支持**粗体**、*斜体*、~~删除线~~和`行内代码`。

## 图片示例

### 本地图片
![本地图表](images/data_chart.png)

### 远程图片
![远程图片](https://picsum.photos/400/300)

## 列表示例

### 任务列表
- [x] 已完成的任务
- [ ] 未完成的任务
  - [ ] 嵌套的子任务

### 嵌套列表
1. 第一项
   - 子项 1.1
   - 子项 1.2
2. 第二项

## 表格示例

| 姓名 | 年龄 | 职位 |
|------|------|------|
| 张三 | 28 | **工程师** |
| 李四 | 32 | *设计师* |

## 代码块

```python
def hello_feishu():
    print("Upload complete!")
```

## 文本对齐

<center>这段文字居中对齐</center>

<div align="right">这段文字右对齐</div>

## HTML 标签

这是<b>HTML粗体</b>和<i>HTML斜体</i>和<u>下划线</u>。

换行测试：第一行<br>第二行
````

### 2. 执行上传命令

**基本用法：**

```bash
# 上传 Markdown 文件（标题自动使用文件名）
python src/uploader.py path/to/your/my_article.md

# 指定文档标题
python src/uploader.py --title "我的技术文档" my_article.md

# 启用调试模式（显示详细日志）
python src/uploader.py --debug my_article.md
```

**输出模式：**

1. **普通模式（默认）**：
   - 显示简洁的进度信息
   - 使用 tqdm 进度条显示上传进度
   - 适合日常使用
   
   ```plain
   🚀 Starting upload for 'My Document'...
   🔗 URL: https://www.feishu.cn/docx/xxxxxxxxxxxxx
   📤 Uploading content blocks...
   Blocks: 100%|████████████████| 2/2 [00:01<00:00,  1.23chunk/s]
   ✅ Content uploaded.
   🖼️  Uploading 3 images...
   Images: 100%|████████████████| 3/3 [00:02<00:00,  1.45img/s]
   ✅ Images processed.
   
   🎉 Upload complete!
   ```

2. **调试模式（`--debug`）**：
   - 显示所有详细日志
   - 包含 API 调用详情
   - 适合排查问题
   
   ```plain
   🚀 Starting upload for 'My Document'...
   Creating document...
   [DEBUG] POST https://open.feishu.cn/open-apis/docx/v1/documents...
   ✅ Document created. Token: xxxxxxxxxxxxx
   🔗 URL: https://www.feishu.cn/docx/xxxxxxxxxxxxx
   Parsing Markdown...
   ✅ Parsed 42 blocks.
   Uploading content blocks...
      - Uploaded blocks 1 to 42
   ✅ Content uploaded.
   ...
   ```

**完整参数说明：**

```bash
python src/uploader.py [-h] [-t TITLE] [--debug] [--env-file ENV_FILE] markdown_file

positional arguments:
  markdown_file         Path to the Markdown file to upload

options:
  -h, --help            Show this help message and exit
  -t TITLE, --title TITLE
                        Document title (default: filename without extension)
  --debug               Enable debug mode (show all logs including API calls)
  --env-file ENV_FILE   Path to .env file (default: .env)
```

### 3. 查看结果

程序执行成功后，将显示详细的上传过程和结果：

```plain
🚀 Starting upload for 'My Document'...
Creating document...
✅ Document created. Token: xxxxxxxxxxxxx
🔗 URL: https://www.feishu.cn/docx/xxxxxxxxxxxxx
Parsing Markdown...
✅ Parsed 42 blocks.
Uploading content blocks...
   - Uploaded blocks 1 to 42
✅ Content uploaded.
Uploading 3 images...
   - Uploading image: example.png to block
     ✅ Image uploaded and set
✅ Images processed.
Setting permissions...
✅ Permissions set to 'Organization members can edit'.

🎉 Upload complete!
```

### 4. 删除文档

项目提供了两个删除脚本，分别用于单文档删除和批量删除。

#### 单个删除（`delete_doc.py`）

已知文档 token 时，可直接删除单个文档：

```bash
python delete_doc.py <doc_token>
```

示例：

```bash
python delete_doc.py doxcnxxxxxxxxxxxx
```

#### 批量删除（`batch_delete.py`）

先查看文档列表，再按 token / 关键字 / 全量删除：

```bash
# 查看当前可删除的 docx 文档（含 token 和 URL）
python batch_delete.py --list

# 按 token 批量删除
python batch_delete.py token1 token2 token3

# 按标题关键字删除（不区分大小写）
python batch_delete.py --pattern "Test"

# 删除全部文档（默认会二次确认）
python batch_delete.py --all
```

可选参数：

- `-y`, `--yes`：跳过确认提示，直接执行删除（高风险，建议谨慎使用）

#### 删除功能注意事项

- 删除操作针对飞书 `docx` 文档类型。
- 默认会进行确认，输入 `yes` 或 `y` 才会继续删除（使用 `-y` 可跳过）。
- 删除前建议先执行 `python batch_delete.py --list` 做一次核对，避免误删。

## 📋 支持的 Markdown 元素

### ✅ 完全支持

#### 文本格式
- **粗体**：`**text**` 或 `<b>text</b>`
- *斜体*：`*text*` 或 `<i>text</i>`
- ~~删除线~~：`~~text~~` 或 `<s>text</s>`
- <u>下划线</u>：`<u>text</u>`
- `行内代码`：`code`

#### 结构元素
- 标题：H1-H9 (`#` 到 `#########`)
- 段落：普通文本段落
- 列表：
  - 无序列表（`-`, `*`, `+`）
  - 有序列表（`1.`, `2.`, ...）
  - 嵌套列表（任意层级）
  - 任务列表：`- [ ]` 和 `- [x]`
- 代码块：支持 40+ 种语言语法高亮
- 引用块：`> quote`
- 分割线：`---` 或 `***`
- 表格：完整的 Markdown 表格语法

#### 媒体与链接
- 本地图片：`![alt](./path/to/image.png)`
- 远程图片：`![alt](https://example.com/image.png)`
- 链接：`[text](url)`

#### HTML 标签
- 格式标签：`<b>`, `<strong>`, `<i>`, `<em>`, `<u>`, `<s>`, `<strike>`, `<del>`
- 换行：`<br>`, `<br/>`
- 对齐：`<center>`, `<div align="center/left/right">`

### ⚠️ 已知限制

1. **图片与文本冲突**：
   - 如果段落中包含图片（如 `Text ![img](url)`），整个段落会被转换为图片块，文本会丢失
   - 链接包裹的图片（`[![img](url)](link)`）会变成普通图片，链接会丢失

2. **对齐块内容**：
   - 多行居中/对齐块中的段落会被合并为单个文本块
   - 支持段落内的所有格式化（粗体、斜体等）

3. **复杂 HTML**：
   - 仅支持简单的格式化和对齐标签
   - 不支持 `<div>`, `<span>` 等复杂块级元素（对齐除外）

## ⚠️ 注意事项

### 图片处理
1. **本地图片路径**：
   - 图片路径相对于 Markdown 文件所在目录
   - 确保图片文件存在且可读
   - 支持的格式：jpg, png, gif, bmp, webp

2. **远程图片**：
   - 自动下载并上传到飞书
   - 临时文件会在上传后自动清理
   - 确保图片 URL 可访问

### 权限问题
1. **应用权限**：
   - 确认飞书应用已开通必需权限
   - 检查 Token 是否过期（SDK 会自动刷新）

2. **文档权限**：
   - 默认设置为"组织内成员可编辑"
   - 可通过飞书界面手动调整

### 常见问题

1. **上传失败**：
   - 检查网络连接
   - 确认 APP_ID 和 APP_SECRET 正确
   - 查看错误信息中的具体错误码

2. **格式不正确**：
   - 确保 Markdown 语法正确
   - 检查是否使用了不支持的元素
   - 参考 `tests/fixtures/test_document.md` 示例

3. **图片无法显示**：
   - 检查图片路径是否正确
   - 确认图片格式是否支持
   - 查看上传日志中的错误信息

## 📚 技术参考

### 项目结构
```plain
Feishu-MD-Uploader/
├── src/
│   ├── auth.py              # 飞书认证
│   ├── config.py            # 配置管理
│   ├── document.py          # 文档创建和权限管理
│   ├── markdown_parser.py   # Markdown 解析核心
│   ├── image_uploader.py    # 图片上传处理
│   └── uploader.py          # 主程序入口
├── delete_doc.py            # 单个文档删除工具
├── batch_delete.py          # 批量文档删除工具
├── tests/
│   └── fixtures/            # 测试用 Markdown 文件
├── .env.example             # 环境变量模板
├── requirements.txt         # Python 依赖
└── README.md               # 本文档
```

### 技术文档
- [飞书开放平台官方文档](https://open.feishu.cn/document/home/index)
- [Markdown-it-py 文档](https://markdown-it-py.readthedocs.io/)
- [项目实现总结](docs/implementation_summary.md)

## 📄 许可证 (License)

本项目采用 [MIT 许可证](LICENSE)。

## 🤝 贡献 (Contributing)

欢迎提交 Issue 和 Pull Request！

### 贡献指南
1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📧 联系方式

如有问题或建议，请通过 GitHub Issues 联系我们。

---

**Made with ❤️ by ZIYAN137**
