# Feishu Markdown Uploader - 完整功能演示

这是一篇综合展示 Feishu Markdown Uploader 所有功能的示例文档。

---

## 📝 文本格式化

### 基础样式
这是**粗体文本**，这是*斜体文本*，这是`行内代码`，这是~~删除线文本~~。

### 组合样式
你可以组合使用：**粗体和*斜体***，或者**粗体和`代码`**。

### HTML 标签支持
这是<b>HTML粗体</b>和<i>HTML斜体</i>和<u>下划线</u>和<s>删除线</s>。

混合使用：<b>HTML粗体<i>嵌套斜体</i></b>和**Markdown粗体<u>嵌套下划线</u>**。

---

## 📋 列表功能

### 无序列表
- 第一项
- 第二项
  - 嵌套项 2.1
  - 嵌套项 2.2
    - 深层嵌套 2.2.1
- 第三项

### 有序列表
1. 首先做这个
2. 然后做那个
   1. 子步骤 2.1
   2. 子步骤 2.2
3. 最后完成

### 任务列表
- [x] 已完成的任务
- [ ] 未完成的任务
- [x] 另一个已完成的任务
  - [ ] 嵌套的子任务
  - [x] 已完成的子任务

---

## 💻 代码块

### Python 代码
```python
def fibonacci(n):
    """计算斐波那契数列"""
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# 测试
for i in range(10):
    print(f"F({i}) = {fibonacci(i)}")
```

### JavaScript 代码
```javascript
// 异步函数示例
async function fetchData(url) {
    try {
        const response = await fetch(url);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error:', error);
    }
}
```

### SQL 代码
```sql
SELECT 
    u.name,
    COUNT(o.id) as order_count,
    SUM(o.amount) as total_amount
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.created_at > '2024-01-01'
GROUP BY u.id
ORDER BY total_amount DESC
LIMIT 10;
```

---

## 📊 表格

### 基础表格
| 姓名 | 年龄 | 职位 |
|------|------|------|
| 张三 | 28 | 工程师 |
| 李四 | 32 | 设计师 |
| 王五 | 25 | 产品经理 |

### 带格式的表格
| 功能 | 状态 | 说明 |
|------|------|------|
| **文本格式** | ✅ | 支持*粗体*、`斜体`等 |
| **表格** | ✅ | 支持Markdown表格 |
| **代码块** | ✅ | 支持语法高亮 |

---

## 🔗 链接

### Markdown 链接
- [GitHub](https://github.com)
- [飞书开放平台](https://open.feishu.cn)
- [项目仓库](https://github.com/ZIYAN137/Feishu-MD-Uploader)

### 链接中的格式
访问 [**粗体链接**](https://example.com) 或 [*斜体链接*](https://example.com)。

---

## 🖼️ 图片

### 本地图片
![本地图片示例](./images/example.png)

### 远程图片
![Picsum随机图片](https://picsum.photos/400/300?random=1)

---

## 📐 文本对齐

<center>这段文字居中对齐</center>

<div align="center">**粗体居中文本**，支持*各种*格式！</div>

<div align="right">这段文字右对齐</div>

<div align="left">这段文字左对齐（默认）</div>

---

## 💬 引用块

> 这是一段引用文本。
> 可以跨越多行。

> **重要提示**
> 
> 引用块内也支持格式化！

---

## 🎨 混合内容

### 复杂段落
这是一个包含**粗体**、*斜体*、`代码`、[链接](https://example.com)和<u>下划线</u>的复杂段落。

### 换行测试
第一行<br>第二行<br>第三行

### 多种元素组合
1. **任务列表**：
   - [x] 完成基础功能
   - [x] 添加图片支持
   - [ ] 继续优化

2. **代码示例**：
   ```python
   print("Hello, Feishu!")
   ```

3. **表格数据**：
   | 项目 | 进度 |
   |------|------|
   | 开发 | 100% |
   | 测试 | 100% |

---

## ✨ 特殊功能

### 分割线
使用三个或更多的横线创建分割线：

---

### 嵌套结构
- 外层列表
  - 中层列表
    - 内层列表
      - 更深层
        1. 有序嵌套
        2. 第二项
  - 返回中层

---

## 🎯 总结

<center>

**Feishu Markdown Uploader**

支持的功能：

✅ 文本格式化（粗体、斜体、删除线、下划线、代码）  
✅ HTML 标签（`<b>`, `<i>`, `<u>`, `<s>`, `<br>`）  
✅ 列表（有序、无序、嵌套）  
✅ 任务列表（Todo）  
✅ 代码块（带语法高亮）  
✅ 表格（支持格式化）  
✅ 链接（Markdown 和 HTML）  
✅ 图片（本地和远程 URL）  
✅ 引用块  
✅ 文本对齐（居中、左、右）  
✅ 分割线  

**祝你使用愉快！** 🚀

</center>
