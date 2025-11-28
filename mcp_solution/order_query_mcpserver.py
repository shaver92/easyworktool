import logging
import sqlite3
from typing import List, Dict, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

# 日志相关配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("order_query_mcp_server")

# 初始化 FastMCP 服务器，指定服务名称为 "order_query"
mcp = FastMCP("order_query")

# 定义数据库连接管理类
class SQLiteManager:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
    
    def connect(self):
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

# 创建全局SQLite管理器实例
sqlite_manager = SQLiteManager("mcp_solution.db")

# 初始化示例数据
logger.info("Initializing sample data...")

# 创建示例表
init_queries = [
    # 创建customers表
    """
    CREATE TABLE IF NOT EXISTS customers (
        customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        email TEXT,
        phone TEXT
    )
    """,
    
    # 创建products表
    """
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        category TEXT,
        price REAL
    )
    """,
    
    # 创建orders表
    """
    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        order_date DATE,
        status TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
    )
    """,
    
    # 创建order_items表
    """
    CREATE TABLE IF NOT EXISTS order_items (
        order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        product_id INTEGER,
        quantity INTEGER,
        price REAL,
        FOREIGN KEY (order_id) REFERENCES orders(order_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    )
    """,
    
    # 插入示例数据 - customers
    "INSERT OR IGNORE INTO customers (customer_name, email, phone) VALUES ('Alice', 'alice@example.com', '123-456-7890')",
    "INSERT OR IGNORE INTO customers (customer_name, email, phone) VALUES ('Bob', 'bob@example.com', '987-654-3210')",
    "INSERT OR IGNORE INTO customers (customer_name, email, phone) VALUES ('Charlie', 'charlie@example.com', '555-555-5555')",
    
    # 插入示例数据 - products
    "INSERT OR IGNORE INTO products (product_name, category, price) VALUES ('Laptop', 'Electronics', 999.99)",
    "INSERT OR IGNORE INTO products (product_name, category, price) VALUES ('Smartphone', 'Electronics', 699.99)",
    "INSERT OR IGNORE INTO products (product_name, category, price) VALUES ('Headphones', 'Electronics', 199.99)",
    
    # 插入示例数据 - orders
    "INSERT OR IGNORE INTO orders (customer_id, order_date, status) VALUES (1, '2023-01-15', 'completed')",
    "INSERT OR IGNORE INTO orders (customer_id, order_date, status) VALUES (2, '2023-02-20', 'completed')",
    "INSERT OR IGNORE INTO orders (customer_id, order_date, status) VALUES (1, '2023-03-10', 'pending')",
    
    # 插入示例数据 - order_items
    "INSERT OR IGNORE INTO order_items (order_id, product_id, quantity, price) VALUES (1, 1, 1, 999.99)",
    "INSERT OR IGNORE INTO order_items (order_id, product_id, quantity, price) VALUES (1, 3, 2, 199.99)",
    "INSERT OR IGNORE INTO order_items (order_id, product_id, quantity, price) VALUES (2, 2, 1, 699.99)",
    "INSERT OR IGNORE INTO order_items (order_id, product_id, quantity, price) VALUES (3, 1, 1, 999.99)"
]

# 执行初始化查询
for query in init_queries:
    try:
        sqlite_manager.execute_query(query)
        logger.info(f"Executed init query: {query[:50]}...")
    except Exception as e:
        logger.error(f"Error executing init query: {e}")

logger.info("Sample data initialized successfully")

# 定义第一个工具函数：查询每个有效订单的客户和商品信息
@mcp.tool()
async def get_order_details(
    customer_name: str = None,
    start_date: str = None,
    end_date: str = None,
    product_name: str = None,
    min_quantity: int = None,
    max_quantity: int = None,
    min_price: float = None,
    max_price: float = None,
    order_status: str = None
) -> List[TextContent]:
    """查询每个有效订单的客户和商品信息
    
    Args:
        customer_name: 客户名称（可选）
        start_date: 开始日期，格式为YYYY-MM-DD（可选）
        end_date: 结束日期，格式为YYYY-MM-DD（可选）
        product_name: 商品名称（可选）
        min_quantity: 最小数量（可选）
        max_quantity: 最大数量（可选）
        min_price: 最小价格（可选）
        max_price: 最大价格（可选）
        order_status: 订单状态（可选）
    """
    logger.info(f"Executing get_order_details with params: customer_name={customer_name}, start_date={start_date}, end_date={end_date}, product_name={product_name}, min_quantity={min_quantity}, max_quantity={max_quantity}, min_price={min_price}, max_price={max_price}, order_status={order_status}")
    
    try:
        # 构建基础查询
        query = """
        SELECT 
            c.customer_name, 
            o.order_date, 
            o.status as order_status,
            p.product_name, 
            oi.quantity, 
            oi.price 
        FROM orders o 
        INNER JOIN customers c ON o.customer_id = c.customer_id 
        INNER JOIN order_items oi ON o.order_id = oi.order_id 
        INNER JOIN products p ON oi.product_id = p.product_id 
        WHERE 1=1
        """
        
        # 构建查询条件和参数
        conditions = []
        params = []
        
        if customer_name:
            conditions.append("c.customer_name LIKE ?")
            params.append(f"%{customer_name}%")
        
        if start_date:
            conditions.append("o.order_date >= ?")
            params.append(start_date)
        
        if end_date:
            conditions.append("o.order_date <= ?")
            params.append(end_date)
        
        if product_name:
            conditions.append("p.product_name LIKE ?")
            params.append(f"%{product_name}%")
        
        if min_quantity is not None:
            conditions.append("oi.quantity >= ?")
            params.append(min_quantity)
        
        if max_quantity is not None:
            conditions.append("oi.quantity <= ?")
            params.append(max_quantity)
        
        if min_price is not None:
            conditions.append("oi.price >= ?")
            params.append(min_price)
        
        if max_price is not None:
            conditions.append("oi.price <= ?")
            params.append(max_price)
        
        if order_status:
            conditions.append("o.status = ?")
            params.append(order_status)
        
        # 添加条件到查询
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        # 执行查询
        result = sqlite_manager.execute_query(query, tuple(params))
        return [TextContent(type="text", text=str(result))]
    except Exception as e:
        logger.error(f"Error executing get_order_details: {e}")
        raise

# 定义第二个工具函数：查询所有客户及其订单信息
@mcp.tool()
async def get_customer_orders(
    customer_name: str = None,
    start_date: str = None,
    end_date: str = None,
    order_status: str = None
) -> List[TextContent]:
    """查询所有客户及其订单信息
    
    Args:
        customer_name: 客户名称（可选）
        start_date: 开始日期，格式为YYYY-MM-DD（可选）
        end_date: 结束日期，格式为YYYY-MM-DD（可选）
        order_status: 订单状态（可选）
    """
    logger.info(f"Executing get_customer_orders with params: customer_name={customer_name}, start_date={start_date}, end_date={end_date}, order_status={order_status}")
    
    try:
        # 构建基础查询
        query = """
        SELECT 
            c.customer_name, 
            o.order_id, 
            o.order_date, 
            o.status as order_status
        FROM customers c 
        LEFT JOIN orders o ON c.customer_id = o.customer_id
        WHERE 1=1
        """
        
        # 构建查询条件和参数
        conditions = []
        params = []
        
        if customer_name:
            conditions.append("c.customer_name LIKE ?")
            params.append(f"%{customer_name}%")
        
        if start_date:
            conditions.append("o.order_date >= ?")
            params.append(start_date)
        
        if end_date:
            conditions.append("o.order_date <= ?")
            params.append(end_date)
        
        if order_status:
            conditions.append("o.status = ?")
            params.append(order_status)
        
        # 添加条件到查询
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        # 执行查询
        result = sqlite_manager.execute_query(query, tuple(params))
        return [TextContent(type="text", text=str(result))]
    except Exception as e:
        logger.error(f"Error executing get_customer_orders: {e}")
        raise

# 主程序入口
if __name__ == "__main__":
    # 初始化并运行 FastMCP 服务器，使用标准输入输出作为传输方式
    mcp.run(transport='stdio')