import logging
import sqlite3
from typing import List, Dict, Any
from asyncio import timeout

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

# 日志相关配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sqlite_mcp_server")

# 初始化 FastMCP 服务器，指定服务名称为 "sqlite"
mcp = FastMCP("sqlite")


# 定义数据库连接管理类
class SQLiteManager:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path

    def connect(self):
        # SQLite会自动创建不存在的数据库文件
        return sqlite3.connect(self.db_path)

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        conn = self.connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute(query, params)
            conn.commit()

            if query.strip().upper().startswith("SELECT"):
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            else:
                return [{"affected_rows": cursor.rowcount}]
        except sqlite3.Error as e:
            conn.rollback()
            raise ValueError(f"SQLite error: {e}")
        finally:
            conn.close()


# 定义执行SQL查询的工具函数
@mcp.tool()
async def execute_sql(db_path: str, query: str, params: List[Any] = None) -> List[TextContent]:
    """执行SQL查询
    
    Args:
        db_path: SQLite数据库文件路径
        query: SQL查询语句
        params: 查询参数列表（可选）
    """
    logger.info(f"Executing SQL on {db_path}: {query}")
    logger.info(f"With params: {params}")

    try:
        # 每次调用创建新的SQLiteManager实例，支持动态指定数据库
        sqlite_manager = SQLiteManager(db_path)
        result = sqlite_manager.execute_query(query, tuple(params) if params else ())
        return [TextContent(type="text", text=str(result))]
    except Exception as e:
        logger.error(f"Error executing SQL: {e}")
        raise


# 定义创建表的工具函数
@mcp.tool()
async def create_table(db_path: str, table_name: str, columns: Dict[str, str]) -> List[TextContent]:
    """创建SQLite表
    
    Args:
        db_path: SQLite数据库文件路径
        table_name: 表名
        columns: 列定义字典，格式为 {"列名": "数据类型"}
    """
    logger.info(f"Creating table {table_name} on {db_path}")
    logger.info(f"With columns: {columns}")

    # 构建CREATE TABLE语句
    columns_def = ", ".join([f"{name} {type_}" for name, type_ in columns.items()])
    query = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_def})"

    try:
        sqlite_manager = SQLiteManager(db_path)
        result = sqlite_manager.execute_query(query)
        return [TextContent(type="text", text=f"Table {table_name} created successfully on {db_path}")]
    except Exception as e:
        logger.error(f"Error creating table: {e}")
        raise


# 定义插入数据的工具函数
@mcp.tool()
async def insert_data(db_path: str, table_name: str, data: Dict[str, Any]) -> List[TextContent]:
    """向SQLite表插入数据
    
    Args:
        db_path: SQLite数据库文件路径
        table_name: 表名
        data: 要插入的数据字典，格式为 {"列名": "值"}
    """
    logger.info(f"Inserting data into table {table_name} on {db_path}")
    logger.info(f"With data: {data}")

    # 构建INSERT语句
    columns = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    values = tuple(data.values())
    query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

    try:
        sqlite_manager = SQLiteManager(db_path)
        result = sqlite_manager.execute_query(query, values)
        return [TextContent(type="text",
                            text=f"Data inserted successfully into {table_name} on {db_path}, affected rows: {result[0]['affected_rows']}")]
    except Exception as e:
        logger.error(f"Error inserting data: {e}")
        raise


# 定义获取数据库列表的工具函数（用于提示用户）
@mcp.tool()
async def list_databases() -> List[TextContent]:
    """列出当前目录下的SQLite数据库文件
    
    Returns:
        包含数据库文件列表的文本内容
    """
    import os

    try:
        # 获取当前目录下的.db文件
        db_files = [f for f in os.listdir('.') if f.endswith('.db')]
        if not db_files:
            return [TextContent(type="text",
                                text="No SQLite database files found in current directory. Please specify a database path.")]
        return [TextContent(type="text", text=f"Available SQLite databases: {', '.join(db_files)}")]
    except Exception as e:
        logger.error(f"Error listing databases: {e}")
        raise


# 主程序入口
if __name__ == "__main__":
    # 初始化并运行 FastMCP 服务器，使用标准输入输出作为传输方式
    mcp.run(transport='stdio')
