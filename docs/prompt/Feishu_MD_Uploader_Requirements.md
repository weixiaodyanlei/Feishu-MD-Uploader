# 📝 需求文档：飞书 Markdown 文档上传工具

| 字段 | 值 |
| :--- | :--- |
| **项目名称** | Feishu-MD-Uploader |
| **目标平台** | 飞书（Feishu / Lark）开放平台 |
| **开发语言** | Python 3.9+ |
| **版本** | 1.0.0 |
| **日期** | 2025年11月22日 |

---

## 1. 项目概述 (Project Overview)

本项目旨在开发一个 Python 命令行工具，实现本地带有图片的 Markdown（.md）文档的自动化上传。该工具必须能够处理 Markdown 中的本地图片引用，将其转换为飞书云文档（Docx）中的可访问内容。

## 2. 目标与范围 (Goal and Scope)

| 方面 | 描述 |
| :--- | :--- |
| **核心目标** | 将包含文本和本地图片的 Markdown 文件，转换为符合飞书 Docx API 规范的 JSON 结构，并成功创建一篇新的飞书云文档。 |
| **范围限制** | 不涉及文档更新（仅创建）。不涉及飞书 Wiki/知识库上传（仅限飞书云文档 Docx）。 |
| **主要输出** | 命令行程序，输入文件路径，输出飞书文档 URL。 |

---

## 3. 功能需求 (Functional Requirements)

### 3.1 用户接口与输入 (R-UI)

| ID | 需求描述 | 优先级 |
| :--- | :--- | :--- |
| R-UI-1 | 程序必须通过命令行接受 **Markdown 文件路径**作为唯一的输入参数。 | 必须 |
| R-UI-2 | 程序必须能够从配置文件（如 `config.ini` 或环境变量）中读取 **App ID** 和 **App Secret**。 | 必须 |
| R-UI-3 | 程序执行成功后，必须在命令行输出**新创建的飞书文档的 URL**。 | 必须 |
| R-UI-4 | 程序执行过程中，应打印清晰的**进度信息**（如：Token 获取成功、图片上传进度、文档创建成功等）。 | 应该 |

### 3.2 飞书 API 交互 (R-API)

| ID | 需求描述 | 优先级 |
| :--- | :--- | :--- |
| R-API-1 | 必须实现 **Tenant Access Token** 的获取和管理（应考虑缓存和过期时间）。 | 必须 |
| R-API-2 | 必须使用 `POST /open-apis/drive/v1/files/upload` 接口上传本地图片。`parent_type` 必须设置为 `doc_image`。 | 必须 |
| R-API-3 | 必须使用 `POST /open-apis/docx/v1/documents` 接口创建新的飞书云文档。 | 必须 |

### 3.3 图片处理 (R-IMG)

| ID | 需求描述 | 优先级 |
| :--- | :--- | :--- |
| R-IMG-1 | 必须使用 Markdown 解析库（如 `markdown-it-py`）**精准识别**文档中的所有图片引用路径（格式如 `![alt text](path/to/image.png)`）。 | 必须 |
| R-IMG-2 | 必须将解析到的**本地相对路径**转换为**绝对路径**进行上传处理。 | 必须 |
| R-IMG-3 | 必须维护一个 **`本地路径` 到 `File Token`** 的映射表，用于后续的 Docx JSON 构造。 | 必须 |
| R-IMG-4 | 对于外部 URL 图片（如 `http://...`），应尝试下载到本地后上传，或在 Docx JSON 中以 Image URL block 形式处理（后者为次选）。 | 应该 |

### 3.4 Docx JSON 转换（核心逻辑）(R-CONV)

必须实现一个**Markdown AST 到 Docx JSON Block** 的转换器。

| ID | 需求描述 | Docx Block 类型 | 优先级 |
| :--- | :--- | :--- | :--- |
| R-CONV-1 | 必须正确处理**图片**，使用 R-IMG-3 得到的 **File Token** 构造 Docx Image Block。 | `Image` (13) | 必须 |
| R-CONV-2 | 必须正确处理 Markdown **标题**（H1, H2, H3）。 | `Heading` (1, 2, 3) | 必须 |
| R-CONV-3 | 必须正确处理**段落**。 | `Paragraph` (2) | 必须 |
| R-CONV-4 | 必须正确处理**无序列表** (`*` 或 `-`) 和**有序列表** (`1.`)。 | `Bullet` (7), `Ordered` (8) | 必须 |
| R-CONV-5 | 必须正确处理 Markdown **代码块**（多行代码）。 | `Code Block` (10) | 必须 |
| R-CONV-6 | 必须正确处理**粗体** (`**bold**`) 和**斜体** (`*italic*`) 等行内样式。 | `Text Run Style` | 必须 |
| R-CONV-7 | 必须忽略或跳过所有不被飞书 Docx 支持的 Markdown 元素。 | - | 必须 |

---

## 4. 技术栈与依赖 (Technology Stack and Dependencies)

| 分类 | 依赖项 | 说明 |
| :--- | :--- | :--- |
| **开发环境** | Python 3.9+ | 基础语言环境 |
| **HTTP 请求** | `requests` | 用于所有的 API 调用。 |
| **Markdown 解析** | `markdown-it-py` | 用于高效、准确地解析 Markdown AST。 |
| **配置管理** | `dotenv` 或 `configparser` | 用于读取应用配置和密钥。 |

---

## 5. 非功能性需求 (Non-Functional Requirements)

| 方面 | 需求描述 |
| :--- | :--- |
| **性能** | 图片上传应支持并发处理（例如使用 `concurrent.futures`），以提高批量上传速度。 |
| **错误处理** | 必须对所有 API 调用进行错误捕获（`code != 0` 或 HTTP 状态码非 200），并打印具体的飞书错误信息。 |
| **代码质量** | 代码应模块化，将 API 封装、Markdown 解析、Docx 转换逻辑分离，确保可读性和可维护性。 |