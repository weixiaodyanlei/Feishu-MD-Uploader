# 🚀 Feishu-MD-Uploader: 飞书 Markdown 文档上传工具

## 🌟 项目简介

`Feishu-MD-Uploader` 是一个基于 Python 的命令行工具，用于解决将带有本地图片的 Markdown 文档**高效、准确**上传到飞书云文档（Docx）的问题。

本项目通过飞书开放平台 API，实现了 Markdown 内容解析、本地图片自动上传并获取 File Token、以及内容到 Docx JSON 结构的精确转换，确保格式完整地迁移到飞书。

## ✨ 主要特性 (Features)

  * **图片自动处理：** 自动识别 Markdown 中的本地图片路径，并调用飞书 API 上传，获取 File Token。
  * **Docx 精确转换：** 深度解析 Markdown AST，将标题 (H1-H3)、段落、列表、代码块、粗体/斜体等元素转换为符合飞书 Docx API 规范的 JSON Block 结构。
  * **Token 自动化：** 自动获取和管理 Tenant Access Token。
  * **命令行操作：** 简洁的命令行接口，一键完成上传任务。

## 演进过程
- [X] v0.1.0: 正确创建文档
- [X] v0.1.1: 正确设置权限：所有组织内成员可编辑
- [X] v0.1.2: 实现添加文本blocks（标题、段落、列表、代码等）的支持
- [X] v0.2.0: 实现本地图片上传和图片Blocks
- [X] v0.2.1: 实现链接支持
- [X] v0.2.2: 实现表格支持
- [ ] v0.2.3: 实现外部URL图片支持
- [ ] v0.2.4: 实现嵌套列表支持
- [ ] v0.2.5: 实现HTML标签支持
- [ ] v0.3.0: 改善使用体验

## 🔧 技术栈与依赖

| 分类 | 名称 | 说明 |
| :--- | :--- | :--- |
| **语言环境** | Python 3.9+ (推荐 3.11.2) | |
| **飞书 SDK** | `lark-oapi` >= 1.3.0 | 飞书官方 Python SDK |
| **Markdown 解析** | `markdown-it-py` >= 3.0.0 | 强大的 Markdown 解析库，用于构建 AST |
| **配置管理** | `python-dotenv` >= 1.0.0 | 用于管理敏感配置 |
| **进度显示** | `tqdm` >= 4.66.0 | 可选，用于显示上传进度 |

## 📦 安装指南

### 1\. 克隆仓库

```bash
git clone https://github.com/ZIYAN137/Feishu-MD-Uploader.git
cd Feishu-MD-Uploader
```

### 2\. 安装依赖

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
- `tqdm` - 进度条显示（可选）

## 🔑 配置 (Configuration)

### 1\. 飞书开放平台设置

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

### 2\. 配置密钥

复制 `.env.example` 并重命名为 `.env`，然后填入您的应用凭证：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```ini
# .env 文件
APP_ID="cli_xxxxxxxxxxxxxx"
APP_SECRET="XXXXXXXXXXXXXXXXXXXXXXXXXXX"

# 可选：指定文档创建的目标文件夹（留空则创建在根目录）
FOLDER_TOKEN=""
```

## 🚀 使用方法 (Usage)

### 1\. 准备 Markdown 文件

确保您的 Markdown 文件 (`my_article.md`) 中的图片引用是**本地有效路径**，例如：

````markdown
# 我们的文档标题

这是一段正文内容。

## 图片示例

![图表数据](images/data_chart.png)

### 代码块

```python
def hello_feishu():
    print("Upload complete!")
```

````

### 2. 执行上传命令

**基本用法：**

```bash
# 上传 Markdown 文件（标题自动使用文件名）
python uploader.py path/to/your/my_article.md

# 指定文档标题
python uploader.py --title "我的技术文档" my_article.md

# 禁用进度条
python uploader.py --no-progress my_article.md

# 使用自定义 .env 文件
python uploader.py --env-file .env.production my_article.md
```

**完整参数说明：**

```bash
python uploader.py [-h] [-t TITLE] [--no-progress] [--env-file ENV_FILE] markdown_file

positional arguments:
  markdown_file         Path to the Markdown file to upload

options:
  -h, --help            Show this help message and exit
  -t TITLE, --title TITLE
                        Document title (default: filename without extension)
  --no-progress         Disable progress bar for image uploads
  --env-file ENV_FILE   Path to .env file (default: .env)
```

### 3\. 查看结果

程序执行成功后，将显示详细的上传过程和结果：


## ⚠️ 注意事项与限制

### 支持的 Markdown 元素

✅ **完全支持：**
- 标题 (H1-H9)
- 段落 (支持粗体、斜体、行内代码、删除线、下划线)
- 无序列表
- 有序列表
- 代码块（支持多种语言语法高亮）
- 分割线
- 引用
- 本地图片
- 链接
- 表格

❌ **暂不支持：**
- 外部 URL 图片（需要先下载）
- 嵌套列表（需要额外处理）
- 任务列表
- HTML 标签

### 常见问题

1. **图片路径问题**
   - 图片路径相对于 Markdown 文件所在目录
   - 确保图片文件存在且可读
   - 支持的格式：jpg, png, gif, bmp, webp

2. **权限错误**
   - 确认飞书应用已开通必需权限
   - 检查 Token 是否过期（SDK 会自动刷新）

3. **上传失败**
   - 检查网络连接
   - 确认 APP_ID 和 APP_SECRET 正确
   - 查看错误信息中的具体错误码

### 技术参考

更多技术细节请参考：
- 查看项目源码 `src/` 目录了解实现细节
- [飞书开放平台官方文档](https://open.feishu.cn/document/home/index) - API 完整参考

## 📄 许可证 (License)

本项目采用 [MIT 许可证](LICENSE)。

## 🤝 贡献 (Contributing)

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题或建议，请通过 GitHub Issues 联系我们。