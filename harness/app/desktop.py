"""Persistent, local desktop workspace services. No generated/demo records."""
from __future__ import annotations

import json
import os
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from harness.state.models import Conversation, Run, RuntimeEvent, utc_now
from harness.durable.serialization import execution_from_dict
from harness.durable.models import ExecutionPhase

SCHEMA = """
CREATE TABLE IF NOT EXISTS desktop_workspaces (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL UNIQUE,
 knowledge_path TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS desktop_sessions (
 id TEXT PRIMARY KEY REFERENCES conversations(id), workspace_id TEXT NOT NULL
 REFERENCES desktop_workspaces(id), title TEXT NOT NULL, created_at TEXT NOT NULL,
 archived INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS desktop_documents (
 id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES desktop_workspaces(id),
 name TEXT NOT NULL, source TEXT NOT NULL, stored_path TEXT NOT NULL,
 content TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS desktop_controls (
 run_id TEXT PRIMARY KEY REFERENCES runs(id), paused INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS desktop_instructions (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), text TEXT NOT NULL,
 created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS desktop_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS desktop_chats (
 id TEXT PRIMARY KEY REFERENCES conversations(id), title TEXT NOT NULL,
 created_at TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS desktop_run_links (
 run_id TEXT PRIMARY KEY REFERENCES runs(id), parent_id TEXT NOT NULL REFERENCES runs(id), step_id TEXT);
"""

# 终态之外的 Durable 状态都算「仍在执行」：删除会话必须拒绝，否则会掏空 Worker 正在写的记录。
ACTIVE_DURABLE_STATUSES = ("pending", "running", "waiting")


class DesktopService:
    def __init__(self, database, config):
        self.database, self.config = database, config
        with closing(database.connect()) as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)

    @staticmethod
    def _migrate(conn) -> None:
        """CREATE TABLE IF NOT EXISTS 不会给旧库补列，因此显式做一次向后兼容迁移。"""
        columns = {row[1] for row in conn.execute("PRAGMA table_info(desktop_sessions)")}
        if columns and "archived" not in columns:
            with conn:
                conn.execute("ALTER TABLE desktop_sessions ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")


    def rows(self, sql, args=()):
        with closing(self.database.connect()) as conn:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]

    def execute(self, sql, args=()):
        with closing(self.database.connect()) as conn:
            with conn:
                conn.execute(sql, args)

    def workspace(self, workspace_id):
        rows = self.rows("SELECT * FROM desktop_workspaces WHERE id=?", (workspace_id,))
        if not rows:
            raise LookupError("工作区不存在")
        return rows[0]

    def add_workspace(self, path, name="", create=False, knowledge_path=None):
        root = Path(path).expanduser().resolve()
        if create:
            root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir():
            raise ValueError("目录不存在，请选择现有目录或勾选创建目录")
        knowledge = str(Path(knowledge_path).expanduser().resolve()) if knowledge_path else str(root / ".harness" / "knowledge")
        existing = self.rows("SELECT * FROM desktop_workspaces WHERE path=?", (str(root),))
        if existing:
            return existing[0]
        wid = f"ws_{uuid4().hex}"
        self.execute("INSERT INTO desktop_workspaces VALUES (?,?,?,?,?)", (wid, name.strip() or root.name or str(root), str(root), knowledge, utc_now().isoformat()))
        return self.workspace(wid)

    def browse(self, path=None):
        root = Path(path).expanduser().resolve() if path else Path.home()
        if not root.is_dir():
            raise ValueError("所选路径不是目录")
        entries = []
        for child in root.iterdir():
            try:
                if child.is_dir():
                    entries.append({"name": child.name, "path": str(child)})
            except OSError:
                continue
        drives = [f"{letter}:\\" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if Path(f"{letter}:\\").is_dir()] if os.name == "nt" else ["/"]
        return {"path": str(root), "parent": str(root.parent), "directories": sorted(entries, key=lambda x: x["name"].lower()), "roots": drives}

    def resolve_file(self, workspace_id, relative):
        root = Path(self.workspace(workspace_id)["path"]).resolve()
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError("文件路径必须位于所选工作区内")
        return candidate

    def files(self, workspace_id, path="."):
        folder = self.resolve_file(workspace_id, path)
        root = Path(self.workspace(workspace_id)["path"]).resolve()
        if not folder.is_dir():
            raise ValueError("目录不存在")
        entries = []
        for item in folder.iterdir():
            if item.name == ".git":
                continue
            try:
                resolved = item.resolve()
                if resolved.is_relative_to(root):
                    entries.append({"name": item.name, "path": str(item.relative_to(root)).replace("\\", "/"), "directory": item.is_dir()})
            except OSError:
                continue
        return {"path": str(folder.relative_to(root)).replace("\\", "/"), "entries": sorted(entries, key=lambda x: (not x["directory"], x["name"].lower()))}

    def read_file(self, workspace_id, path):
        file = self.resolve_file(workspace_id, path)
        if not file.is_file():
            raise ValueError("文件不存在")
        if file.stat().st_size > 2_000_000:
            raise ValueError("预览支持 2 MB 以内的文本文件，请使用本地编辑器查看此文件")
        return {"path": path, "content": file.read_text(encoding="utf-8-sig")}

    def new_session(self, workspace_id, title="新任务"):
        if workspace_id:
            self.workspace(workspace_id)
        conversation = Conversation(id=f"conv_{uuid4().hex}", user_id=self.config.app.local_user_id, tenant_id=self.config.app.local_tenant_id)
        with self.database.uow() as uow:
            uow.conversations.add(conversation)
            uow.commit()
        if workspace_id:
            self.execute(
                "INSERT INTO desktop_sessions (id,workspace_id,title,created_at,archived) VALUES (?,?,?,?,0)",
                (conversation.id, workspace_id, title.strip() or "新任务", utc_now().isoformat()),
            )
        else:
            self.execute("INSERT INTO desktop_chats VALUES(?,?,?,0)", (conversation.id, title.strip() or "新对话", utc_now().isoformat()))
        return self.session(conversation.id)

    def session(self, session_id):
        rows = self.rows("SELECT * FROM desktop_sessions WHERE id=?", (session_id,))
        if not rows:
            rows = self.rows("SELECT *,'' AS workspace_id FROM desktop_chats WHERE id=?", (session_id,))
        if not rows:
            raise LookupError("会话不存在")
        return rows[0]

    def update_session(self, session_id, *, title=None, archived=None):
        session = self.session(session_id)
        table = 'desktop_sessions' if session['workspace_id'] else 'desktop_chats'
        if title is not None:
            self.execute(f"UPDATE {table} SET title=? WHERE id=?", (title.strip() or "新任务", session_id))
        if archived is not None:
            self.execute(f"UPDATE {table} SET archived=? WHERE id=?", (1 if archived else 0, session_id))
        return self.session(session_id)

    def session_active_runs(self, session_id):
        """仍在执行（非终态）的 Run：删除会话前必须先把它们停下来。"""
        placeholders = ",".join("?" for _ in ACTIVE_DURABLE_STATUSES)
        return self.rows(
            f"SELECT r.id FROM runs r JOIN durable_runs d ON d.run_id=r.id"
            f" WHERE r.conversation_id=? AND d.status IN ({placeholders})",
            (session_id, *ACTIVE_DURABLE_STATUSES),
        )

    def delete_session(self, session_id):
        """彻底删除会话：对话、Run 及其所有派生日志一并清理。

        删除顺序按依赖倒序，且用 PRAGMA 找出所有带 run_id 的表，
        这样以后新增审计表也不会留下悬挂行。
        """
        self.session(session_id)
        run_ids = [row["id"] for row in self.rows("SELECT id FROM runs WHERE conversation_id=?", (session_id,))]
        tables = [row["name"] for row in self.rows("SELECT name FROM sqlite_master WHERE type='table'")]
        run_scoped = [
            table for table in tables
            if table != "runs" and any(column["name"] == "run_id" for column in self.rows(f"PRAGMA table_info({table})"))
        ]
        for run_id in run_ids:
            for table in run_scoped:
                self.execute(f"DELETE FROM {table} WHERE run_id=?", (run_id,))
            # 重跑链：其他 Run 指向被删 Run 的链接也要一起清掉。
            self.execute("DELETE FROM desktop_run_links WHERE parent_id=?", (run_id,))
        self.execute("DELETE FROM runs WHERE conversation_id=?", (session_id,))
        self.execute("DELETE FROM messages WHERE conversation_id=?", (session_id,))
        self.execute("DELETE FROM desktop_sessions WHERE id=?", (session_id,))
        self.execute("DELETE FROM desktop_chats WHERE id=?", (session_id,))
        self.execute("DELETE FROM conversations WHERE id=?", (session_id,))
        return {"removed": True, "runs": len(run_ids)}

    def ingest(self, workspace_id, name, data, source):
        workspace = self.workspace(workspace_id)
        name = Path(name.replace("\\", "/")).name
        if not name or "\x00" in name:
            raise ValueError("文件名无效")
        try:
            content = data.decode("utf-8-sig")
        except UnicodeError as exc:
            raise ValueError("当前知识库支持 UTF-8 文本、Markdown 和代码文件") from exc
        if "\x00" in content:
            raise ValueError("知识库不支持二进制文件")
        did = f"doc_{uuid4().hex}"
        destination = Path(workspace["knowledge_path"]).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / f"{did}_{name}"
        target.write_bytes(data)
        try:
            self.execute("INSERT INTO desktop_documents VALUES (?,?,?,?,?,?,?)", (did, workspace_id, name, source, str(target), content, utc_now().isoformat()))
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return {"id": did, "name": name, "source": source, "stored_path": str(target)}

    def search_knowledge(self, workspace_id, query):
        self.workspace(workspace_id)
        query = query.strip()
        if not query:
            return []
        rows = self.rows("SELECT id,name,source,content FROM desktop_documents WHERE workspace_id=? AND instr(lower(content),lower(?)) > 0", (workspace_id, query))
        result = []
        for row in rows:
            offset = row["content"].lower().find(query.lower())
            result.append({"id": row["id"], "name": row["name"], "source": row["source"], "excerpt": row["content"][max(0, offset - 200):offset + 1800]})
        return result

    def agent(self):
        saved = self.rows("SELECT value FROM desktop_settings WHERE key='agent'")
        data = json.loads(saved[0]["value"]) if saved else {"name": self.config.app.name, "instructions": self.config.app.system_instruction}
        return {"id": "default", "name": data["name"], "instructions": data["instructions"], "model": self.config.app.model or os.getenv("DEEPSEEK_MODEL" if self.config.app.provider == "deepseek" else "OPENAI_MODEL", ""), "provider": self.config.app.provider}

    def is_paused(self, run_id):
        rows = self.rows("SELECT paused FROM desktop_controls WHERE run_id=?", (run_id,))
        return bool(rows and rows[0]["paused"])

    def apply_instructions(self, state):
        for row in self.rows("SELECT * FROM desktop_instructions WHERE run_id=? ORDER BY created_at,id", (state.run_id,)):
            if row["id"] not in state.applied_instructions:
                # Added to the next model request without discarding pending tool results.
                state.instructions += "\n\n操作员追加指令：" + row["text"]
                state.applied_instructions.append(row["id"])

    def replay(self, runtime, run_id, step_id=None):
        original = self.observed_run(runtime, run_id)
        if step_id:
            step = self.rows("SELECT sequence FROM steps WHERE id=? AND run_id=?", (step_id, run_id))
            if not step and step_id == f"{run_id}-error":
                # A failed in-flight transition has no completed Step record yet.
                record = runtime.durable_store.get(run_id)
                sequence = record.execution.transition_count + 1
            elif not step:
                raise ValueError("此节点没有可重跑的执行步骤")
            else:
                sequence = step[0]["sequence"]
        else:
            sequence = 1
        checkpoints = self.rows("SELECT state_json FROM checkpoints WHERE run_id=? AND step_sequence<? ORDER BY step_sequence DESC LIMIT 1", (run_id, sequence))
        if not checkpoints:
            raise ValueError("此历史运行没有所需检查点，请新建任务")
        state = execution_from_dict(json.loads(checkpoints[0]["state_json"]))
        if state.phase in {ExecutionPhase.COMPLETED, ExecutionPhase.FAILED, ExecutionPhase.CANCELLED}:
            raise ValueError("检查点已经结束，无法从此处重跑")
        if state.phase == ExecutionPhase.WAITING_APPROVAL:
            state.phase = ExecutionPhase.TOOL
        rid = f"run_{uuid4().hex}"
        workspace_id = state.tool_context.workspace_id
        if workspace_id:
            session = self.new_session(workspace_id, "重跑 · " + original["title"])
            conversation_id = session["id"]
        else:
            conversation = Conversation(id=f"conv_{uuid4().hex}", user_id=self.config.app.local_user_id, tenant_id=self.config.app.local_tenant_id)
            with self.database.uow() as uow:
                uow.conversations.add(conversation)
                uow.commit()
            conversation_id = conversation.id
        state.run_id = rid
        state.tool_context = replace(state.tool_context, run_id=rid)
        state.transition_data = {}
        state.error_message = None
        with self.database.uow() as uow:
            uow.runs.add(Run(id=rid, conversation_id=conversation_id))
            uow.messages.add_user(conversation_id=conversation_id, content=state.user_input)
            uow.events.add(RuntimeEvent(id=f"evt_{uuid4().hex}", run_id=rid, event_type="run.replayed", payload={"parent_id": run_id, "step_id": step_id}))
            uow.commit()
        self.execute("INSERT INTO desktop_run_links VALUES (?,?,?)", (rid, run_id, step_id))
        runtime.durable_store.enqueue(run_id=rid, execution=state)
        return {"run_id": rid, "conversation_id": conversation_id, "status": "pending"}

    def observed_run(self, runtime, run_id):
        rows = self.rows("SELECT r.* FROM runs r JOIN conversations c ON c.id=r.conversation_id WHERE r.id=? AND c.user_id=? AND c.tenant_id=?", (run_id, self.config.app.local_user_id, self.config.app.local_tenant_id))
        if not rows:
            raise LookupError("Run 不存在")
        row = rows[0]
        record = runtime.durable_store.get(run_id)
        state = record.execution if record else None
        status_map = {"pending": "running", "running": "running", "waiting": "pending", "completed": "success", "failed": "failed", "blocked": "failed", "cancelled": "skipped"}
        status = status_map.get(record.status.value if record else row["status"], "failed")
        if record and record.status.value == "waiting" and self.is_paused(run_id):
            status = "paused"
        steps = self.rows("SELECT * FROM steps WHERE run_id=? ORDER BY sequence", (run_id,))
        nodes = []
        for step in steps:
            data = json.loads(step["output_json"])
            node_status = "failed" if data.get("status") in {"error", "denied", "timeout", "blocked"} or data.get("error_code") else "success"
            if step["status"] == "waiting":
                node_status = "pending" if state and state.current_tool_call and state.current_tool_call.call_id == data.get("call_id") and status == "pending" else "skipped"
            output = data.get("output", data)
            node = {"id": step["id"], "kind": "thought" if step["type"] == "model" else "tool", "name": data.get("name", "模型响应" if step["type"] == "model" else "工具执行"), "summary": json.dumps(data.get("input", {}), ensure_ascii=False) if step["type"] != "model" else (str(data.get("output") or "模型提出工具调用")), "status": node_status, "duration": data.get("duration", 0), "tokens": data.get("tokens", 0), "input": data.get("input", json.loads(step["input_json"])), "output": output}
            if step["type"] == "model" and isinstance(data.get("metrics"), dict):
                node["metrics"] = data["metrics"]
            try:
                parsed = json.loads(output) if isinstance(output, str) else output
                if isinstance(parsed, dict):
                    payload = parsed.get("data", parsed)
                    if isinstance(payload, dict) and "diff" in payload:
                        node["diff"] = payload["diff"]
            except (ValueError, TypeError):
                pass
            if node_status == "failed":
                node["error"] = {"type": data.get("error_code") or "ToolError", "message": str(output), "logs": [str(output)]}
            nodes.append(node)
        if state and status in {"running", "pending", "paused"}:
            call = state.current_tool_call
            if not nodes or nodes[-1]["status"] != "pending":
                nodes.append({"id": f"{run_id}-current-{state.transition_count}", "kind": "tool" if call else "thought", "name": call.name if call else "等待模型响应", "summary": json.dumps(call.arguments, ensure_ascii=False) if call else "服务端执行中", "status": status, "duration": 0, "tokens": 0, "input": call.arguments if call else state.current_input})
        if state and state.final_output:
            nodes.append({"id": f"{run_id}-output", "kind": "output", "name": "最终输出", "summary": state.final_output, "status": "success", "duration": 0, "tokens": 0, "output": state.final_output})
        if status == "failed":
            error = (state.error_message if state else None) or row["error_message"] or "运行失败"
            nodes.append({"id": f"{run_id}-error", "kind": "result", "name": "运行失败", "summary": error, "status": "failed", "duration": 0, "tokens": 0, "error": {"type": "RunError", "message": error, "logs": [error]}})
        agent = self.agent()
        links = self.rows("SELECT * FROM desktop_run_links WHERE run_id=?", (run_id,))
        link = links[0] if links else {}
        return {"id": run_id, "parentId": link.get("parent_id"), "replayFrom": link.get("step_id"), "title": state.user_input[:60] if state else run_id, "agent": agent["name"], "model": agent["model"], "trigger": "本地用户", "startedAt": row["created_at"], "status": status, "mode": "live", "input": state.user_input if state else "", "nodes": nodes, "cost": None, "conversationId": row["conversation_id"], "workspaceId": state.tool_context.workspace_id if state else None, "errorType": "RunError" if status == "failed" else None, "totalTokens": state.evidence.model_usage.total_tokens if state else 0}
