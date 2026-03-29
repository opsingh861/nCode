"""Database node handlers: PostgreSQL, MySQL, MongoDB, Redis, SQLite."""

from __future__ import annotations

import re

from backend.core.ir import IRNode, IRNodeKind
from backend.handlers.base import GenerationContext
from backend.handlers.registry import register
from backend.models.workflow import N8nNode


def _safe_var(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower())
    s = re.sub(r"_+", "_", s).strip("_") or "node"
    return f"n_{s}" if s[0].isdigit() else s


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

@register("n8n-nodes-base.postgres")
class PostgresHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        operation = str(params.get("operation", "executeQuery")).lower()
        ctx.add_import("import psycopg2", "from psycopg2 import sql as _pg_sql", "import os")
        ctx.add_package("psycopg2-binary")

        conn_lines = [
            f"_pg_conn = psycopg2.connect(",
            f'    host=os.environ.get("POSTGRES_HOST", "localhost"),',
            f'    port=int(os.environ.get("POSTGRES_PORT", "5432")),',
            f'    dbname=os.environ.get("POSTGRES_DB", ""),',
            f'    user=os.environ.get("POSTGRES_USER", ""),',
            f'    password=os.environ.get("POSTGRES_PASSWORD", ""),',
            f")",
            f"_pg_cur = _pg_conn.cursor()",
        ]

        if operation == "executequery":
            query = ctx.resolve_expr(str(params.get("query", "")))
            code_lines = conn_lines + [
                f"_pg_cur.execute({query})",
                f"try:",
                f"    _pg_rows = _pg_cur.fetchall()",
                f"    _pg_cols = [d[0] for d in _pg_cur.description] if _pg_cur.description else []",
                f"    {var}_output = [{{'json': dict(zip(_pg_cols, row))}} for row in _pg_rows]",
                f"except psycopg2.ProgrammingError:",
                f"    _pg_conn.commit()",
                f"    {var}_output = [{{'json': {{'success': True}}}}]",
                f"_pg_conn.close()",
            ]
        elif operation in ("insert", "upsert"):
            table = str(params.get("table", ""))
            op_label = "Upsert" if operation == "upsert" else "Insert"
            code_lines = conn_lines + [
                f"# {op_label} into table (uses psycopg2.sql.Identifier for safe table/column quoting)",
                f"_pg_table = _pg_sql.Identifier({table!r})",
                f"_pg_inserts = []",
                f"for _item in {prev_var}:",
                f"    _row = _item.get('json', {{}})",
                f"    if _row: _pg_inserts.append(_row)",
                f"if _pg_inserts:",
                f"    _pg_col_names = list(_pg_inserts[0].keys())",
                f"    _pg_col_idents = [_pg_sql.Identifier(c) for c in _pg_col_names]",
                f"    _pg_placeholders = _pg_sql.SQL(', ').join([_pg_sql.Placeholder()] * len(_pg_col_names))",
                f"    _pg_stmt = _pg_sql.SQL('INSERT INTO {{}} ({{}}) VALUES ({{}})').format(",
                f"        _pg_table,",
                f"        _pg_sql.SQL(', ').join(_pg_col_idents),",
                f"        _pg_placeholders,",
                f"    )",
                f"    for _row in _pg_inserts:",
                f"        _pg_cur.execute(_pg_stmt, [_row.get(c) for c in _pg_col_names])",
                f"    _pg_conn.commit()",
                f"{var}_output = {prev_var}",
                f"_pg_conn.close()",
            ]
        elif operation == "update":
            table = str(params.get("table", ""))
            update_key = str(params.get("updateKey", "id"))
            code_lines = conn_lines + [
                f"# Update table (uses psycopg2.sql.Identifier for safe quoting)",
                f"_pg_table = _pg_sql.Identifier({table!r})",
                f"_pg_key_col = _pg_sql.Identifier({update_key!r})",
                f"for _item in {prev_var}:",
                f"    _row = _item.get('json', {{}})",
                f"    _key_val = _row.get({update_key!r})",
                f"    _set_cols = [k for k in _row if k != {update_key!r}]",
                f"    _set_vals = [_row[k] for k in _set_cols]",
                f"    if _set_cols and _key_val is not None:",
                f"        _pg_set = _pg_sql.SQL(', ').join(",
                f"            _pg_sql.SQL('{{}} = %s').format(_pg_sql.Identifier(c)) for c in _set_cols",
                f"        )",
                f"        _pg_stmt = _pg_sql.SQL('UPDATE {{}} SET {{}} WHERE {{}} = %s').format(",
                f"            _pg_table, _pg_set, _pg_key_col",
                f"        )",
                f"        _pg_cur.execute(_pg_stmt, _set_vals + [_key_val])",
                f"_pg_conn.commit()",
                f"{var}_output = {prev_var}",
                f"_pg_conn.close()",
            ]
        elif operation == "select":
            table = str(params.get("table", ""))
            limit = params.get("limit", 100)
            code_lines = conn_lines + [
                f"# Select from table (uses psycopg2.sql.Identifier for safe table quoting)",
                f"_pg_table = _pg_sql.Identifier({table!r})",
                f"_pg_cur.execute(",
                f"    _pg_sql.SQL('SELECT * FROM {{}} LIMIT %s').format(_pg_table),",
                f"    [{limit}],",
                f")",
                f"_pg_rows = _pg_cur.fetchall()",
                f"_pg_cols = [d[0] for d in _pg_cur.description] if _pg_cur.description else []",
                f"{var}_output = [{{'json': dict(zip(_pg_cols, row))}} for row in _pg_rows]",
                f"_pg_conn.close()",
            ]
        elif operation == "delete":
            table = str(params.get("table", ""))
            delete_key = str(params.get("deleteKey", "id"))
            code_lines = conn_lines + [
                f"# Delete from table (uses psycopg2.sql.Identifier for safe quoting)",
                f"_pg_table = _pg_sql.Identifier({table!r})",
                f"_pg_key_col = _pg_sql.Identifier({delete_key!r})",
                f"_pg_del_stmt = _pg_sql.SQL('DELETE FROM {{}} WHERE {{}} = %s').format(",
                f"    _pg_table, _pg_key_col",
                f")",
                f"for _item in {prev_var}:",
                f"    _row = _item.get('json', {{}})",
                f"    _key_val = _row.get({delete_key!r})",
                f"    if _key_val is not None:",
                f"        _pg_cur.execute(_pg_del_stmt, [_key_val])",
                f"_pg_conn.commit()",
                f"{var}_output = {prev_var}",
                f"_pg_conn.close()",
            ]
        else:
            code_lines = conn_lines + [
                f"# Postgres operation {operation!r}: pass-through",
                f"_pg_conn.close()",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id, node_name=node.name, kind=IRNodeKind.STATEMENT,
            python_var=var,
            imports=["import psycopg2", "from psycopg2 import sql as _pg_sql", "import os"],
            pip_packages=["psycopg2-binary"], code_lines=code_lines,
            comment=f"PostgreSQL ({operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.postgres"]

    def required_packages(self) -> list[str]:
        return ["psycopg2-binary"]


# ---------------------------------------------------------------------------
# MySQL
# ---------------------------------------------------------------------------

@register("n8n-nodes-base.mySql", "n8n-nodes-base.mysql")
class MySqlHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        operation = str(params.get("operation", "executeQuery")).lower()

        conn_lines = [
            f"import pymysql",
            f"import os",
            f"_mysql_conn = pymysql.connect(",
            f'    host=os.environ.get("MYSQL_HOST", "localhost"),',
            f'    port=int(os.environ.get("MYSQL_PORT", "3306")),',
            f'    db=os.environ.get("MYSQL_DB", ""),',
            f'    user=os.environ.get("MYSQL_USER", ""),',
            f'    password=os.environ.get("MYSQL_PASSWORD", ""),',
            f"    cursorclass=pymysql.cursors.DictCursor,",
            f")",
            f"_mysql_cur = _mysql_conn.cursor()",
        ]

        def _mysql_ident(name: str) -> str:
            """Emit a backtick-quoted MySQL identifier (safe for static table/column names)."""
            safe = re.sub(r"[^a-zA-Z0-9_]", "", name)
            return f"`{safe}`"

        if operation == "executequery":
            query = ctx.resolve_expr(str(params.get("query", "")))
            code_lines = conn_lines + [
                f"_mysql_cur.execute({query})",
                f"_mysql_rows = _mysql_cur.fetchall()",
                f"{var}_output = [{{'json': dict(row)}} for row in _mysql_rows]",
                f"_mysql_conn.close()",
            ]
        elif operation == "insert":
            table = str(params.get("table", ""))
            table_ident = _mysql_ident(table)
            code_lines = conn_lines + [
                f"# Insert rows using parameterized query with backtick-quoted identifiers",
                f"for _item in {prev_var}:",
                f"    _row = _item.get('json', {{}})",
                f"    _cols = list(_row.keys())",
                f"    if not _cols:",
                f"        continue",
                f"    _safe_cols = ['`' + re.sub(r'[^a-zA-Z0-9_]', '', c) + '`' for c in _cols]",
                f"    _ph = ', '.join(['%s'] * len(_cols))",
                f"    _mysql_cur.execute(",
                f"        f'INSERT INTO {table_ident} ({{', '.join(_safe_cols)}}) VALUES ({{_ph}})',",
                f"        list(_row.values()),",
                f"    )",
                f"_mysql_conn.commit()",
                f"{var}_output = {prev_var}",
                f"_mysql_conn.close()",
            ]
        elif operation == "select":
            table = str(params.get("table", ""))
            table_ident = _mysql_ident(table)
            limit = int(params.get("limit", 100))
            code_lines = conn_lines + [
                f"# Select using backtick-quoted table name",
                f"_mysql_cur.execute('SELECT * FROM {table_ident} LIMIT %s', [{limit}])",
                f"_mysql_rows = _mysql_cur.fetchall()",
                f"{var}_output = [{{'json': dict(row)}} for row in _mysql_rows]",
                f"_mysql_conn.close()",
            ]
        else:
            code_lines = conn_lines + [
                f"# MySQL ({operation}): pass-through",
                f"_mysql_conn.close()",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id, node_name=node.name, kind=IRNodeKind.STATEMENT,
            python_var=var, imports=["import pymysql", "import os", "import re"],
            pip_packages=["pymysql"], code_lines=code_lines,
            comment=f"MySQL ({operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.mySql"]

    def required_packages(self) -> list[str]:
        return ["pymysql"]


# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------

@register("n8n-nodes-base.mongoDb", "n8n-nodes-base.mongodb")
class MongoDbHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        operation = str(params.get("operation", "find")).lower()
        collection = str(params.get("collection", ""))

        conn_lines = [
            f"import pymongo",
            f"import os",
            f"_mg_client = pymongo.MongoClient(os.environ.get('MONGODB_URI', 'mongodb://localhost:27017'))",
            f"_mg_db = _mg_client[os.environ.get('MONGODB_DB', 'mydb')]",
            f"_mg_col = _mg_db['{collection}']",
        ]

        if operation == "find":
            query_raw = ctx.resolve_expr(str(params.get("query", "{}")))
            limit = params.get("limit", 100)
            code_lines = conn_lines + [
                f"_mg_docs = list(_mg_col.find({query_raw}).limit({limit}))",
                f"for d in _mg_docs: d['_id'] = str(d.get('_id', ''))",
                f"{var}_output = [{{'json': d}} for d in _mg_docs]",
            ]
        elif operation == "insert":
            code_lines = conn_lines + [
                f"_mg_inserts = [item.get('json', {{}}) for item in {prev_var}]",
                f"if _mg_inserts:",
                f"    _mg_col.insert_many(_mg_inserts)",
                f"{var}_output = {prev_var}",
            ]
        elif operation == "insertmany":
            code_lines = conn_lines + [
                f"_mg_inserts = [item.get('json', {{}}) for item in {prev_var}]",
                f"if _mg_inserts:",
                f"    _mg_col.insert_many(_mg_inserts)",
                f"{var}_output = {prev_var}",
            ]
        elif operation == "update":
            query_raw = ctx.resolve_expr(str(params.get("query", "{}")))
            update_raw = ctx.resolve_expr(str(params.get("updateKey", "{}")))
            code_lines = conn_lines + [
                f"_mg_col.update_many({query_raw}, {{'$set': {update_raw}}})",
                f"{var}_output = {prev_var}",
            ]
        elif operation == "delete":
            query_raw = ctx.resolve_expr(str(params.get("query", "{}")))
            code_lines = conn_lines + [
                f"_mg_col.delete_many({query_raw})",
                f"{var}_output = {prev_var}",
            ]
        elif operation == "aggregate":
            pipeline_raw = ctx.resolve_expr(str(params.get("pipeline", "[]")))
            code_lines = conn_lines + [
                f"_mg_docs = list(_mg_col.aggregate({pipeline_raw}))",
                f"for d in _mg_docs: d['_id'] = str(d.get('_id', ''))",
                f"{var}_output = [{{'json': d}} for d in _mg_docs]",
            ]
        else:
            code_lines = conn_lines + [
                f"# MongoDB ({operation}): pass-through",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id, node_name=node.name, kind=IRNodeKind.STATEMENT,
            python_var=var, imports=["import pymongo", "import os"],
            pip_packages=["pymongo"], code_lines=code_lines,
            comment=f"MongoDB ({operation}) on {collection!r}",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.mongoDb"]

    def required_packages(self) -> list[str]:
        return ["pymongo"]


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------

@register("n8n-nodes-base.redis")
class RedisHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        operation = str(params.get("operation", "get")).lower()
        key_expr = ctx.resolve_expr(str(params.get("name", "")))

        conn_lines = [
            f"import redis as _redis_mod",
            f"import os",
            f"_redis = _redis_mod.Redis(",
            f"    host=os.environ.get('REDIS_HOST', 'localhost'),",
            f"    port=int(os.environ.get('REDIS_PORT', '6379')),",
            f"    db=int(os.environ.get('REDIS_DB', '0')),",
            f"    password=os.environ.get('REDIS_PASSWORD') or None,",
            f"    decode_responses=True,",
            f")",
        ]

        if operation == "get":
            code_lines = conn_lines + [
                f"_redis_val = _redis.get({key_expr})",
                f"{var}_output = [{{'json': {{'key': {key_expr}, 'value': _redis_val}}}}]",
            ]
        elif operation == "set":
            value_expr = ctx.resolve_expr(str(params.get("value", "")))
            ttl = params.get("expire", None)
            ttl_line = f", ex={ttl}" if ttl else ""
            code_lines = conn_lines + [
                f"_redis.set({key_expr}, {value_expr}{ttl_line})",
                f"{var}_output = [{{'json': {{'success': True}}}}]",
            ]
        elif operation == "delete":
            code_lines = conn_lines + [
                f"_redis.delete({key_expr})",
                f"{var}_output = [{{'json': {{'success': True}}}}]",
            ]
        elif operation == "keys":
            pattern = ctx.resolve_expr(str(params.get("keyPattern", "*")))
            code_lines = conn_lines + [
                f"_redis_keys = _redis.keys({pattern})",
                f"{var}_output = [{{'json': {{'key': k}}}} for k in _redis_keys]",
            ]
        elif operation == "publish":
            channel_expr = ctx.resolve_expr(str(params.get("channel", "")))
            message_expr = ctx.resolve_expr(str(params.get("messageData", "")))
            code_lines = conn_lines + [
                f"_redis.publish({channel_expr}, {message_expr})",
                f"{var}_output = [{{'json': {{'success': True}}}}]",
            ]
        else:
            code_lines = conn_lines + [
                f"# Redis ({operation}): pass-through",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id, node_name=node.name, kind=IRNodeKind.STATEMENT,
            python_var=var, imports=["import redis", "import os"],
            pip_packages=["redis"], code_lines=code_lines,
            comment=f"Redis ({operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.redis"]

    def required_packages(self) -> list[str]:
        return ["redis"]


# ---------------------------------------------------------------------------
# PostgreSQL Tool (AI tool node for n8n agents)
# ---------------------------------------------------------------------------

@register(
    "n8n-nodes-base.postgresTool",
    "n8n-nodes-base.postgrestool",
)
class PostgresToolHandler:
    """Handles postgresTool nodes — wraps a Postgres query as a LangChain tool."""

    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        query = str(params.get("query", "SELECT 1"))
        # Replace n8n $fromAI() expressions with a {sql_statement} placeholder
        import re as _re
        query_clean = _re.sub(r"\{\{.*?\}\}", "{sql_statement}", query)

        code_lines = [
            f"# PostgreSQL Tool: {node.name!r} — wraps Postgres query as a LangChain tool",
            f"import os, psycopg2",
            f"from langchain.tools import Tool",
            f"def _pg_tool_fn_{var}(sql: str) -> str:",
            f"    _conn = None",
            f"    _cur = None",
            f"    try:",
            f'        _conn = psycopg2.connect(',
            f'            host=os.environ.get("POSTGRES_HOST", "localhost"),',
            f'            port=int(os.environ.get("POSTGRES_PORT", "5432")),',
            f'            dbname=os.environ.get("POSTGRES_DB", ""),',
            f'            user=os.environ.get("POSTGRES_USER", ""),',
            f'            password=os.environ.get("POSTGRES_PASSWORD", ""),',
            f"        )",
            f"        _cur = _conn.cursor()",
            f"        _cur.execute(sql)",
            f"        if _cur.description:",
            f"            _rows = _cur.fetchall()",
            f"            _cols = [d[0] for d in _cur.description]",
            f"            _result = str([dict(zip(_cols, r)) for r in _rows])",
            f"            return _result",
            f"        _conn.commit()",
            f'        return "Query executed successfully"',
            f"    except Exception as _e:",
            f'        return f"DB error: {{_e}}"',
            f"    finally:",
            f"        if _cur is not None:",
            f"            _cur.close()",
            f"        if _conn is not None:",
            f"            _conn.close()",
            f'{var}_tool = Tool(',
            f'    name={node.name!r},',
            f'    func=_pg_tool_fn_{var},',
            f'    description="Execute SQL queries against a PostgreSQL database. Input should be a valid SQL statement.",',
            f")",
            f"{var}_output = {prev_var}",
        ]

        return IRNode(
            node_id=node.id, node_name=node.name, kind=IRNodeKind.STATEMENT,
            python_var=var, imports=["import os", "import psycopg2"],
            pip_packages=["psycopg2-binary", "langchain"],
            code_lines=code_lines,
            comment="PostgreSQL Tool (LangChain)",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.postgresTool"]

    def required_packages(self) -> list[str]:
        return ["psycopg2-binary", "langchain"]


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

@register("n8n-nodes-base.sqlite")
class SqliteHandler:
    def generate(self, node: N8nNode, ctx: GenerationContext) -> IRNode:
        var = _safe_var(node.name)
        prev_var = ctx.var_context.current_var()
        ctx.register_node_var(node.name, var)
        params = node.parameters

        operation = str(params.get("operation", "executeQuery")).lower()
        db_file = str(params.get("databaseFile", ":memory:"))

        conn_lines = [
            f"import sqlite3",
            f"_sqlite_conn = sqlite3.connect({db_file!r})",
            f"_sqlite_conn.row_factory = sqlite3.Row",
            f"_sqlite_cur = _sqlite_conn.cursor()",
        ]

        if operation == "executequery":
            query = str(params.get("query", ""))
            code_lines = conn_lines + [
                f"_sqlite_cur.execute({query!r})",
                f"try:",
                f"    _sqlite_rows = _sqlite_cur.fetchall()",
                f"    {var}_output = [{{'json': dict(row)}} for row in _sqlite_rows]",
                f"except Exception:",
                f"    _sqlite_conn.commit()",
                f"    {var}_output = [{{'json': {{'success': True}}}}]",
                f"_sqlite_conn.close()",
            ]
        else:
            code_lines = conn_lines + [
                f"# SQLite {operation}: pass-through",
                f"_sqlite_conn.close()",
                f"{var}_output = {prev_var}",
            ]

        return IRNode(
            node_id=node.id, node_name=node.name, kind=IRNodeKind.STATEMENT,
            python_var=var, imports=["import sqlite3"],
            pip_packages=[], code_lines=code_lines,
            comment=f"SQLite ({operation})",
        )

    def supported_operations(self) -> list[str]:
        return ["n8n-nodes-base.sqlite"]

    def required_packages(self) -> list[str]:
        return []
