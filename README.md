# 🚀 Feishu-MD-Uploader: 飞书 Markdown 文档上传工具

## 🌟 项目简介

`Feishu-MD-Uploader` 是一个基于 Python 的命令行工具，用于解决将带有本地图片的 Markdown 文档**高效、准确**上传到飞书云文档（Docx）的问题。

本项目通过飞书开放平台 API，实现了 Markdown 内容解析、本地图片自动上传并获取 File Token、以及内容到 Docx JSON 结构的精确转换，确保格式完整地迁移到飞书。

## ✨ 主要特性 (Features)

  * **图片自动处理：** 自动识别 Markdown 中的本地图片路径，并调用飞书 API 上传，获取 File Token。
  * **Docx 精确转换：** 深度解析 Markdown AST，将标题 (H1-H3)、段落、列表、代码块、粗体/斜体等元素转换为符合飞书 Docx API 规范的 JSON Block 结构。
  * **Token 自动化：** 自动获取和管理 Tenant Access Token。
  * **命令行操作：** 简洁的命令行接口，一键完成上传任务。

## 🔧 技术栈与依赖

| 分类 | 名称 | 说明 |
| :--- | :--- | :--- |
| **语言环境** | Python 3.9+ | |
| **HTTP 请求** | `requests` | 负责所有 API 调用。 |
| **Markdown 解析** | `markdown-it-py` | 强大的 Markdown 解析库，用于构建 AST。 |
| **配置管理** | `python-dotenv` 或 `configparser` | 推荐用于管理敏感配置。 |

## 📦 安装指南

### 1\. 克隆仓库

```bash
git clone https://github.com/ZIYAN137/Feishu-MD-Uploader.git
cd Feishu-MD-Uploader
```

### 2\. 安装依赖

```bash
pip install -r requirements.txt
# 核心依赖：requests, markdown-it-py, (推荐安装 python-dotenv)
```

## 🔑 配置 (Configuration)

### 1\. 飞书开放平台设置

请确保您已在 [飞书开放平台](https://open.feishu.cn/) 创建应用，并获得了 **App ID** 和 **App Secret**。

应用必须启用以下权限(TODO)：
* 

### 2\. 配置密钥

在项目根目录下创建 `.env` 文件，并填入您的应用凭证。

```ini
# .env 文件
APP_ID="cli_xxxxxxxxxxxxxx"
APP_SECRET="XXXXXXXXXXXXXXXXXXXXXXXXXXX"
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
````

````

### 2. 执行上传命令

在命令行中，将 Markdown 文件路径作为参数传入：

```bash
python uploader.py path/to/your/my_article.md
````

### 3\. 查看结果

程序执行成功后，将输出文档链接：

```
[INFO] Tenant Access Token 获取成功。
[INFO] 开始处理 1 张本地图片...
[INFO] - 图片 images/data_chart.png 上传成功，Token: boxcnxxxxxxxx
[INFO] Markdown 转换为 Docx JSON 成功。
🎉 文档上传成功! 链接: https://example.feishu.cn/docx/XXXXXXXXXXXXXXXXX
```

## ⚠️ 注意事项与限制

  * **Docx JSON 转换：** 本工具的核心逻辑在于 **Markdown 到 Docx JSON** 的转换器。请确保该转换逻辑已覆盖您 Markdown 中使用的所有复杂元素（如表格、嵌套列表等）。如果遇到格式丢失，请首先检查转换器逻辑。
  * **权限问题：** 如果上传失败，请检查您的飞书应用是否正确启用了 **所有必需的权限**。
  * **图片路径：** 命令行执行时，所有相对路径都会基于 `uploader.py` 的执行目录进行解析。请确保本地图片路径是正确的。

## 📄 许可证 (License)

本项目采用 [MIT 许可证](LICENSE)。

## 🤝 贡献 (Contributing)

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题或建议，请通过 GitHub Issues 联系我们。