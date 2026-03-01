# 🛠️ 最佳实践与问题排查指南 (Best Practices & Troubleshooting)

本文档记录了在开发 **theNPC** 系统过程中遇到的关键问题、解决方案以及架构设计的最佳实践，供后续开发参考。

---

## 1. LLM 交互与 Prompt 工程

### 🚨 问题：Prompt 中的 JSON 格式化冲突
**现象**：
在使用 `str.format()` 填充 Prompt 模板时，抛出 `KeyError`。
**原因**：
Prompt 模板中包含了大量的 JSON 示例（使用了 `{` 和 `}`）。Python 的 `format()` 方法会将所有 `{}` 视为占位符，导致解析 JSON 结构时出错。
**解决方案**：
*   **方法 A (推荐)**：使用 `.replace("{placeholder}", value)` 代替 `.format()`。虽然不够优雅，但最安全，无需对 JSON 进行转义。
*   **方法 B**：将 Prompt 中的所有字面量 `{` 和 `}` 转义为 `{{` 和 `}}`。这会使 Prompt 难以阅读和维护。

### 🚨 问题：LLM 输出解析不稳定
**现象**：
LLM 返回的内容可能包含 Markdown 代码块标记（```json ... ```）、注释或多余的对话文本，导致 `json.loads()` 失败。
**最佳实践**：
使用多重回退（Fallback）机制提取 JSON：
1.  **Regex 1**: 匹配 ````json ... ````` 代码块。
2.  **Regex 2**: 匹配任意 ```` ... ````` 代码块。
3.  **Regex 3**: 匹配最外层的 `[...]` 或 `{...}`（贪婪匹配）。
4.  **Fallback**: 尝试直接解析原始文本。

---

## 2. 后端开发 (FastAPI)

### 🚨 问题：500 Internal Server Error 无 Traceback
**现象**：
前端收到 500 错误，但在 Backend CMD 窗口中看不到任何 Python 报错堆栈，只有 Access Log。
**原因**：
FastAPI/Uvicorn 在某些配置下可能吞掉了未捕获异常的详细日志，或者异常发生在异步任务的深处。
**解决方案**：
在 `main.py` 中显式添加全局异常处理器：
```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global Exception: {exc}")
    traceback.print_exc()  # 关键：打印堆栈到控制台
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": traceback.format_exc()},
    )
```

### 💡 调试技巧：分段埋点 (Bisect Logging)
当出现“静默失败”时，不要猜测。在 Router 入口、Service 入口、关键逻辑前后（如 LLM 调用）添加 `print("DEBUG: ...")`。这能迅速定位代码是在哪一行“死掉”的。

---

## 3. 系统启动与环境

### 📂 路径问题
**现象**：
使用 `start_system.bat` 启动多服务时，子进程找不到文件（`File not found`）。
**最佳实践**：
*   不要依赖相对路径。
*   在批处理脚本中，使用 `cd /d %~dp0` 获取脚本所在目录的绝对路径。
*   在启动子进程前，显式 `cd` 到目标子目录。

### 🔑 环境变量与鉴权
**现象**：
LLM 服务报 403 Forbidden。
**排查**：
1.  检查 `.env` 是否被正确加载。
2.  **关键**：检查 URL 是否被重复拼接。例如 Base URL 是 `.../v1`，代码里又拼了 `/v1/messages`，导致 `.../v1/v1/messages`。
3.  **原则**：代码应尽量少做假设，信任配置文件中的 URL，或者使用标准的 SDK。

---

## 4. 架构设计

### 💾 数据持久化 (The Archivist)
*   **结构**: `data/worlds/{world_id}/` 目录存储所有相关文件。
*   **索引**: 维护 `index.json` 或元数据文件，避免遍历文件系统带来的性能开销。
*   **分离**: 将静态设定 (Bible) 与 动态状态 (NPC State, Chat History) 分离存储。
