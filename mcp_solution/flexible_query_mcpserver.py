import logging
import sqlite3
import json
from typing import List, Dict, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

# 日志相关配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("flexible_query_mcp_server")

# 初始化 FastMCP 服务器，指定服务名称为 "flexible_query"
mcp = FastMCP("flexible_query")

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
sqlite_manager = SQLiteManager("shoppingmall")

# 定义订单详情查询工具函数
@mcp.tool()
async def get_order_details(
    customer_name: str = None,  # 客户名称（模糊匹配）
    customer_id: int = None,  # 客户ID
    start_date: str = None,  # 开始日期（YYYY-MM-DD）
    end_date: str = None,  # 结束日期（YYYY-MM-DD）
    product_name: str = None,  # 商品名称（模糊匹配）
    min_quantity: int = None,  # 最小数量
    max_quantity: int = None,  # 最大数量
    min_price: float = None,  # 最小价格
    max_price: float = None,  # 最大价格
    natural_language_query: str = None  # 自然语言查询语句
) -> List[TextContent]:
    """查询订单详情，包含客户信息、商品信息、数量、价格等完整订单数据
    
    Args:
        customer_name: 客户名称（模糊匹配）
        customer_id: 客户ID
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）
        product_name: 商品名称（模糊匹配）
        min_quantity: 最小数量
        max_quantity: 最大数量
        min_price: 最小价格
        max_price: 最大价格
        natural_language_query: 自然语言查询语句
    
    Returns:
        查询结果，格式为JSON字符串
    """
    logger.info(f"Executing get_order_details with parameters: customer_name={customer_name}, customer_id={customer_id}, start_date={start_date}, end_date={end_date}, product_name={product_name}, min_quantity={min_quantity}, max_quantity={max_quantity}, min_price={min_price}, max_price={max_price}, natural_language_query={natural_language_query}")
    
    try:
        # 构建查询和条件
        query = """
        SELECT 
            c.customer_name, 
            o.order_date, 
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
        
        # 客户相关条件
        if customer_id:
            conditions.append("c.customer_id = ?")
            params.append(customer_id)
        
        if customer_name:
            conditions.append("c.customer_name LIKE ?")
            params.append(f"%{customer_name}%")
        
        # 日期条件
        if start_date:
            conditions.append("o.order_date >= ?")
            params.append(start_date)
        
        if end_date:
            conditions.append("o.order_date <= ?")
            params.append(end_date)
        
        # 商品相关条件
        if product_name:
            conditions.append("p.product_name LIKE ?")
            params.append(f"%{product_name}%")
        
        # 数量和价格条件
        if min_quantity:
            conditions.append("oi.quantity >= ?")
            params.append(min_quantity)
        
        if max_quantity:
            conditions.append("oi.quantity <= ?")
            params.append(max_quantity)
        
        if min_price:
            conditions.append("oi.price >= ?")
            params.append(min_price)
        
        if max_price:
            conditions.append("oi.price <= ?")
            params.append(max_price)
        
        # 添加条件到查询
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        # 打印生成的最终SQL和参数，方便调试
        logger.info(f"Generated SQL: {query}")
        logger.info(f"SQL Parameters: {tuple(params)}")
        
        # 执行查询
        result = sqlite_manager.execute_query(query, tuple(params))
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    except Exception as e:
        logger.error(f"Error executing get_order_details: {e}")
        raise

# 定义客户详情查询工具函数
@mcp.tool()
async def get_customer_details(
    customer_name: str = None,  # 客户名称（模糊匹配）
    customer_id: int = None,  # 客户ID
    start_date: str = None,  # 开始日期（YYYY-MM-DD）
    end_date: str = None,  # 结束日期（YYYY-MM-DD）
    natural_language_query: str = None  # 自然语言查询语句
) -> List[TextContent]:
    """查询客户详情，包含客户基本信息和关联的订单信息
    
    Args:
        customer_name: 客户名称（模糊匹配）
        customer_id: 客户ID
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）
        natural_language_query: 自然语言查询语句
    
    Returns:
        查询结果，格式为JSON字符串
    """
    logger.info(f"Executing get_customer_details with parameters: customer_name={customer_name}, customer_id={customer_id}, start_date={start_date}, end_date={end_date}, natural_language_query={natural_language_query}")
    
    try:
        # 构建查询和条件
        query = """
        SELECT 
            c.customer_name, 
            o.order_id, 
            o.order_date
        FROM customers c 
        LEFT JOIN orders o ON c.customer_id = o.customer_id
        WHERE 1=1
        """
        
        # 构建查询条件和参数
        conditions = []
        params = []
        
        # 客户相关条件
        if customer_id:
            conditions.append("c.customer_id = ?")
            params.append(customer_id)
        
        if customer_name:
            conditions.append("c.customer_name LIKE ?")
            params.append(f"%{customer_name}%")
        
        # 日期条件
        if start_date:
            conditions.append("o.order_date >= ?")
            params.append(start_date)
        
        if end_date:
            conditions.append("o.order_date <= ?")
            params.append(end_date)
        
        # 添加条件到查询
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        # 打印生成的最终SQL和参数，方便调试
        logger.info(f"Generated SQL: {query}")
        logger.info(f"SQL Parameters: {tuple(params)}")
        
        # 执行查询
        result = sqlite_manager.execute_query(query, tuple(params))
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    except Exception as e:
        logger.error(f"Error executing get_customer_details: {e}")
        raise

# 主程序入口
if __name__ == "__main__":
    # 初始化并运行 FastMCP 服务器，使用标准输入输出作为传输方式
    mcp.run(transport='stdio')