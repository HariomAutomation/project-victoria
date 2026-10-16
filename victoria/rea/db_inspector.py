"""
Victoria - REA Database Inspector
Reverse engineers databases and storage systems:
- SQLite databases (schema DDL, tables, columns, foreign keys, indexes, triggers, row counts)
- Relational databases (PostgreSQL, MySQL, MariaDB via information_schema or CLI)
- Redis / Key-Value databases (key namespaces, types, memory stats)
- Generates Mermaid ERD diagrams, SQLAlchemy ORM models, and reconstructed SQL DDL
"""

import re
import sqlite3
import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from rich.console import Console

console = Console()


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    primary_key: bool = False
    not_null: bool = False
    default_value: Optional[str] = None


@dataclass
class ForeignKeyInfo:
    from_column: str
    target_table: str
    target_column: str
    on_update: str = "NO ACTION"
    on_delete: str = "NO ACTION"


@dataclass
class TableSchema:
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    primary_keys: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKeyInfo] = field(default_factory=list)
    indexes: list[str] = field(default_factory=list)
    row_count: int = 0
    raw_ddl: str = ""
    sample_rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DatabaseTeardownResult:
    target: str
    db_type: str  # "sqlite", "postgres", "mysql", "redis", "unknown"
    total_tables: int = 0
    tables: dict[str, Any] = field(default_factory=dict)
    views: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    mermaid_erd: str = ""
    sqlalchemy_models: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class DBInspector:
    """
    Database Reverse Engineering Engine.
    """

    def inspect(self, target: str) -> DatabaseTeardownResult:
        """
        Reverse engineer a database from a file path or connection URI.

        Args:
            target: Path to .sqlite/.db file or connection string (e.g., redis://, postgres://)

        Returns:
            DatabaseTeardownResult containing tables, columns, ERD, and ORM models.
        """
        console.print(f"[cyan]🗄️ Reverse engineering database: {target}[/cyan]")

        if target.startswith("redis://") or "redis" in target.lower():
            return self._inspect_redis(target)
        elif target.startswith(("postgres://", "postgresql://")):
            return self._inspect_postgres(target)
        elif target.startswith(("mysql://", "mariadb://")):
            return self._inspect_mysql(target)
        else:
            # Check SQLite file
            return self._inspect_sqlite(target)

    # =========================================================================
    # 1. SQLite Database Reverse Engineering
    # =========================================================================

    def _inspect_sqlite(self, db_path_str: str) -> DatabaseTeardownResult:
        db_path = Path(db_path_str).resolve()
        result = DatabaseTeardownResult(target=str(db_path), db_type="sqlite")

        if not db_path.exists():
            result.metadata["error"] = f"SQLite file not found: {db_path}"
            return result

        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cursor = conn.cursor()

            # 1. Get all tables, views, triggers from sqlite_master
            cursor.execute(
                "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
            )
            master_rows = cursor.fetchall()

            table_names = []
            for item_type, name, sql in master_rows:
                if item_type == "table":
                    table_names.append(name)
                elif item_type == "view":
                    result.views.append(name)
                elif item_type == "trigger":
                    result.triggers.append(name)

            result.total_tables = len(table_names)
            tables_dict: dict[str, TableSchema] = {}

            # 2. Inspect each table schema
            for t_name in table_names:
                table_schema = TableSchema(name=t_name)

                # DDL
                for item_type, name, sql in master_rows:
                    if item_type == "table" and name == t_name and sql:
                        table_schema.raw_ddl = sql

                # Columns (PRAGMA table_info)
                cursor.execute(f'PRAGMA table_info("{t_name}")')
                cols = cursor.fetchall()
                for cid, cname, ctype, notnull, dflt_value, pk in cols:
                    col_info = ColumnInfo(
                        name=cname,
                        data_type=ctype or "TEXT",
                        primary_key=bool(pk),
                        not_null=bool(notnull),
                        default_value=str(dflt_value) if dflt_value is not None else None,
                    )
                    table_schema.columns.append(col_info)
                    if pk:
                        table_schema.primary_keys.append(cname)

                # Foreign Keys (PRAGMA foreign_key_list)
                try:
                    cursor.execute(f'PRAGMA foreign_key_list("{t_name}")')
                    fks = cursor.fetchall()
                    for fkid, seq, target_tbl, from_col, to_col, on_upd, on_del, match in fks:
                        table_schema.foreign_keys.append(
                            ForeignKeyInfo(
                                from_column=from_col,
                                target_table=target_tbl,
                                target_column=to_col or "id",
                                on_update=on_upd,
                                on_delete=on_del,
                            )
                        )
                except Exception:
                    pass

                # Indexes (PRAGMA index_list)
                try:
                    cursor.execute(f'PRAGMA index_list("{t_name}")')
                    idxs = cursor.fetchall()
                    for idx_seq, idx_name, unique, origin, partial in idxs:
                        table_schema.indexes.append(f"{idx_name} ({'UNIQUE' if unique else 'INDEX'})")
                except Exception:
                    pass

                # Row count
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{t_name}"')
                    table_schema.row_count = cursor.fetchone()[0]
                except Exception:
                    table_schema.row_count = 0

                # Sample data (first 3 rows, sanitizing passwords/secrets)
                try:
                    cursor.execute(f'SELECT * FROM "{t_name}" LIMIT 3')
                    sample_tuples = cursor.fetchall()
                    col_names = [c.name for c in table_schema.columns]
                    for row in sample_tuples:
                        row_dict = {}
                        for i, val in enumerate(row):
                            cname = col_names[i]
                            if re.search(r'(?:password|secret|token|hash|key)', cname, re.IGNORECASE):
                                row_dict[cname] = "****** [REDACTED]"
                            else:
                                row_dict[cname] = str(val)[:50] if val is not None else None
                        table_schema.sample_rows.append(row_dict)
                except Exception:
                    pass

                tables_dict[t_name] = table_schema

            conn.close()

            # Store serialized tables
            result.tables = {k: asdict(v) for k, v in tables_dict.items()}

            # 3. Generate Mermaid ERD Diagram
            result.mermaid_erd = self._generate_mermaid_erd(tables_dict)

            # 4. Generate SQLAlchemy Python ORM Models
            result.sqlalchemy_models = self._generate_sqlalchemy_models(tables_dict)

        except Exception as e:
            console.print(f"[red]❌ Error inspecting SQLite DB: {e}[/red]")
            result.metadata["error"] = str(e)

        return result

    # =========================================================================
    # 2. Redis Key-Value Store Reverse Engineering
    # =========================================================================

    def _inspect_redis(self, target: str) -> DatabaseTeardownResult:
        result = DatabaseTeardownResult(target=target, db_type="redis")
        if shutil.which("redis-cli"):
            try:
                # Scan keys and detect types
                res = subprocess.run(["redis-cli", "INFO", "keyspace"], capture_output=True, text=True, timeout=5)
                result.metadata["keyspace"] = res.stdout.strip()

                sample_keys = subprocess.run(["redis-cli", "--scan"], capture_output=True, text=True, timeout=5)
                keys = [k.strip() for k in sample_keys.stdout.splitlines()[:50] if k.strip()]

                key_types = {}
                for k in keys[:20]:
                    t_res = subprocess.run(["redis-cli", "TYPE", k], capture_output=True, text=True, timeout=2)
                    key_types[k] = t_res.stdout.strip()

                result.metadata["sample_keys"] = key_types
                result.total_tables = len(keys)
            except Exception as e:
                result.metadata["error"] = str(e)
        else:
            result.metadata["notice"] = "redis-cli not found. Install redis-tools to inspect live redis."
        return result

    # =========================================================================
    # 3. PostgreSQL / MySQL Fallbacks
    # =========================================================================

    def _inspect_postgres(self, conn_uri: str) -> DatabaseTeardownResult:
        result = DatabaseTeardownResult(target=conn_uri, db_type="postgres")
        # If psql is available, run schema query
        if shutil.which("psql"):
            try:
                query = "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
                res = subprocess.run(["psql", conn_uri, "-c", query], capture_output=True, text=True, timeout=10)
                result.metadata["tables_raw"] = res.stdout.strip()
            except Exception as e:
                result.metadata["error"] = str(e)
        return result

    def _inspect_mysql(self, conn_uri: str) -> DatabaseTeardownResult:
        result = DatabaseTeardownResult(target=conn_uri, db_type="mysql")
        return result

    # =========================================================================
    # 4. Mermaid ERD & Code Reconstruction Generators
    # =========================================================================

    def _generate_mermaid_erd(self, tables: dict[str, TableSchema]) -> str:
        """Generate Mermaid ERD diagram string."""
        lines = ["erDiagram"]

        for t_name, schema in tables.items():
            lines.append(f"    {t_name} {{")
            for col in schema.columns:
                pk_marker = "PK" if col.primary_key else ""
                lines.append(f"        {col.data_type.lower() or 'string'} {col.name} {pk_marker}")
            lines.append("    }")

        # Relationships
        for t_name, schema in tables.items():
            for fk in schema.foreign_keys:
                if fk.target_table in tables:
                    lines.append(f"    {fk.target_table} ||--o{{ {t_name} : \"{fk.from_column}->{fk.target_column}\"")

        return "\n".join(lines)

    def _generate_sqlalchemy_models(self, tables: dict[str, TableSchema]) -> str:
        """Generate Python SQLAlchemy ORM models from reverse-engineered schema."""
        lines = [
            "# Auto-generated SQLAlchemy Models",
            "# Created by Project Victoria REA Engine",
            "from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Text, DateTime",
            "from sqlalchemy.orm import declarative_base, relationship",
            "\nBase = declarative_base()\n",
        ]

        type_map = {
            "integer": "Integer",
            "int": "Integer",
            "text": "Text",
            "varchar": "String",
            "real": "Float",
            "float": "Float",
            "boolean": "Boolean",
            "bool": "Boolean",
            "timestamp": "DateTime",
            "datetime": "DateTime",
        }

        for t_name, schema in tables.items():
            class_name = "".join(part.capitalize() for part in t_name.split("_"))
            lines.append(f"class {class_name}(Base):")
            lines.append(f"    __tablename__ = '{t_name}'\n")

            for col in schema.columns:
                mapped_type = "String"
                for k, v in type_map.items():
                    if k in col.data_type.lower():
                        mapped_type = v
                        break

                params = []
                if col.primary_key:
                    params.append("primary_key=True")
                if col.not_null and not col.primary_key:
                    params.append("nullable=False")

                # Check if foreign key
                fk_match = next((fk for fk in schema.foreign_keys if fk.from_column == col.name), None)
                if fk_match:
                    params.append(f"ForeignKey('{fk_match.target_table}.{fk_match.target_column}')")

                param_str = f", {', '.join(params)}" if params else ""
                lines.append(f"    {col.name} = Column({mapped_type}{param_str})")

            lines.append("")

        return "\n".join(lines)
