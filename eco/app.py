# -*- coding: utf-8 -*-

# -------------------------------------------------------------------------------
# Name:         app.py
# Description:  类似Excel的数据库管理工具
# Author:       shaver
# Date:         2025/9/8
# -------------------------------------------------------------------------------
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io
import json
from typing import Dict, List, Tuple, Optional

# 页面配置
st.set_page_config(
    page_title="Eco - 数据库管理工具",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }

    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
    }

    .success-message {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
    }

    .error-message {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #f5c6cb;
    }

    .info-message {
        background: #d1ecf1;
        color: #0c5460;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #bee5eb;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-left: 20px;
        padding-right: 20px;
    }

    .stTabs [aria-selected="true"] {
        background-color: #667eea;
        color: white;
    }
</style>
""", unsafe_allow_html=True)


# 数据库操作类
class DatabaseManager:
    def __init__(self, db_path: str = 'eco_data.db'):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # 创建表格配置表
        c.execute('''
        CREATE TABLE IF NOT EXISTS table_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            column_name TEXT NOT NULL,
            column_type TEXT NOT NULL,
            is_required BOOLEAN DEFAULT FALSE,
            default_value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(table_name, column_name)
        )
        ''')

        # 创建表格元数据表
        c.execute('''
        CREATE TABLE IF NOT EXISTS table_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT UNIQUE NOT NULL,
            display_name TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        conn.commit()
        conn.close()

    def get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)

    def get_all_tables(self) -> List[str]:
        """获取所有表格名称"""
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT table_name FROM table_metadata ORDER BY table_name")
        tables = [row[0] for row in c.fetchall()]
        conn.close()
        return tables

    def get_table_columns(self, table_name: str) -> List[Tuple[str, str, bool, str]]:
        """获取表格列信息"""
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT column_name, column_type, is_required, default_value 
            FROM table_config 
            WHERE table_name = ? 
            ORDER BY id
        """, (table_name,))
        columns = c.fetchall()
        conn.close()
        return columns

    def create_table(self, table_name: str, display_name: str = None, description: str = None):
        """创建新表格"""
        conn = self.get_connection()
        c = conn.cursor()

        try:
            # 添加表格元数据
            c.execute("""
                INSERT INTO table_metadata (table_name, display_name, description) 
                VALUES (?, ?, ?)
            """, (table_name, display_name or table_name, description or ""))

            # 创建数据表
            c.execute(f"""
                CREATE TABLE {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def add_column(self, table_name: str, column_name: str, column_type: str,
                   is_required: bool = False, default_value: str = None):
        """添加列到表格"""
        conn = self.get_connection()
        c = conn.cursor()

        try:
            # 添加列配置
            c.execute("""
                INSERT INTO table_config (table_name, column_name, column_type, is_required, default_value) 
                VALUES (?, ?, ?, ?, ?)
            """, (table_name, column_name, column_type, is_required, default_value))

            # 添加列到数据表
            c.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def delete_column(self, table_name: str, column_name: str):
        """删除列（仅删除配置，SQLite不支持直接删除列）"""
        conn = self.get_connection()
        c = conn.cursor()

        try:
            c.execute("""
                DELETE FROM table_config 
                WHERE table_name = ? AND column_name = ?
            """, (table_name, column_name))

            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_table_data(self, table_name: str, limit: int = 1000) -> pd.DataFrame:
        """获取表格数据"""
        conn = self.get_connection()
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT {limit}", conn)
            return df
        finally:
            conn.close()

    def insert_record(self, table_name: str, data: Dict):
        """插入记录"""
        conn = self.get_connection()
        c = conn.cursor()

        try:
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?'] * len(data))
            values = list(data.values())

            c.execute(f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})", values)
            conn.commit()
            return c.lastrowid
        except sqlite3.Error as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def update_record(self, table_name: str, record_id: int, data: Dict):
        """更新记录"""
        conn = self.get_connection()
        c = conn.cursor()

        try:
            update_fields = ', '.join([f"{k} = ?" for k in data.keys()])
            values = list(data.values()) + [record_id]

            c.execute(f"UPDATE {table_name} SET {update_fields}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)
            conn.commit()
            return c.rowcount > 0
        except sqlite3.Error as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def delete_record(self, table_name: str, record_id: int):
        """删除记录"""
        conn = self.get_connection()
        c = conn.cursor()

        try:
            c.execute(f"DELETE FROM {table_name} WHERE id = ?", (record_id,))
            conn.commit()
            return c.rowcount > 0
        except sqlite3.Error as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def bulk_insert_records(self, table_name: str, records: List[Dict]):
        """批量插入记录"""
        conn = self.get_connection()
        c = conn.cursor()

        try:
            if not records:
                return 0

            columns = ', '.join(records[0].keys())
            placeholders = ', '.join(['?'] * len(records[0]))

            values_list = [list(record.values()) for record in records]

            c.executemany(f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})", values_list)
            conn.commit()
            return c.rowcount
        except sqlite3.Error as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def bulk_delete_records(self, table_name: str, record_ids: List[int]):
        """批量删除记录"""
        conn = self.get_connection()
        c = conn.cursor()

        try:
            placeholders = ', '.join(['?'] * len(record_ids))
            c.execute(f"DELETE FROM {table_name} WHERE id IN ({placeholders})", record_ids)
            conn.commit()
            return c.rowcount
        except sqlite3.Error as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def search_records(self, table_name: str, search_term: str, limit: int = 1000) -> pd.DataFrame:
        """搜索记录"""
        conn = self.get_connection()
        try:
            # 获取所有列名
            columns_info = self.get_table_columns(table_name)
            if not columns_info:
                return pd.DataFrame()

            # 构建搜索条件
            search_conditions = []
            for col_name, col_type, _, _ in columns_info:
                if col_type in ['TEXT', 'DATETIME']:
                    search_conditions.append(f"{col_name} LIKE ?")
                else:
                    search_conditions.append(f"CAST({col_name} AS TEXT) LIKE ?")

            where_clause = " OR ".join(search_conditions)
            search_param = f"%{search_term}%"
            search_params = [search_param] * len(search_conditions)

            query = f"""
                SELECT * FROM {table_name} 
                WHERE {where_clause} 
                ORDER BY id DESC 
                LIMIT {limit}
            """

            df = pd.read_sql_query(query, conn, params=search_params)
            return df
        finally:
            conn.close()


# 初始化数据库管理器
db_manager = DatabaseManager()


# 缓存机制
@st.cache_data(ttl=60)  # 缓存1分钟
def get_cached_table_data(table_name: str, limit: int = 1000):
    """缓存表格数据"""
    return db_manager.get_table_data(table_name, limit)


@st.cache_data(ttl=300)  # 缓存5分钟
def get_cached_table_columns(table_name: str):
    """缓存表格列信息"""
    return db_manager.get_table_columns(table_name)


@st.cache_data(ttl=300)  # 缓存5分钟
def get_cached_all_tables():
    """缓存所有表格列表"""
    return db_manager.get_all_tables()


def clear_cache():
    """清除所有缓存"""
    get_cached_table_data.clear()
    get_cached_table_columns.clear()
    get_cached_all_tables.clear()


# 主标题
st.markdown("""
<div class="main-header">
    <h1>📊 Eco - 数据库管理工具</h1>
    <p>类似Excel的数据库操作界面，支持表格管理、数据增删改查</p>
</div>
""", unsafe_allow_html=True)

# 侧边栏 - 表格选择
st.sidebar.markdown("### 📋 表格管理")
all_tables = get_cached_all_tables()

if not all_tables:
    st.sidebar.info("暂无表格，请先创建表格")
    selected_table = None
else:
    selected_table = st.sidebar.selectbox("选择表格", all_tables, key="table_selector")

# 主内容区域
if selected_table:
    # 获取表格信息
    columns_info = get_cached_table_columns(selected_table)

    # 显示表格统计信息
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("表格名称", selected_table)
    with col2:
        st.metric("列数", len(columns_info))
    with col3:
        df = get_cached_table_data(selected_table)
        st.metric("记录数", len(df))
    with col4:
        if not df.empty:
            st.metric("最新记录", df.iloc[0]['created_at'][:10] if 'created_at' in df.columns else "N/A")
        else:
            st.metric("最新记录", "无")

    # 使用标签页组织功能
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 数据查看", "➕ 添加数据", "✏️ 编辑数据", "📥 数据导入", "⚙️ 表格设置"])

    with tab1:
        st.markdown("### 📊 数据查看")

        # 搜索和过滤
        col1, col2 = st.columns([3, 1])
        with col1:
            search_term = st.text_input("🔍 搜索数据", placeholder="输入关键词搜索...")
        with col2:
            limit = st.selectbox("显示条数", [50, 100, 500, 1000], index=1)

        # 获取并显示数据
        if search_term:
            df = db_manager.search_records(selected_table, search_term, limit)
        else:
            df = get_cached_table_data(selected_table, limit)

        if not df.empty:
            # 批量操作
            st.markdown("**批量操作：**")
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                # 选择要删除的记录
                selected_indices = st.multiselect(
                    "选择要删除的记录（ID）",
                    options=df['id'].tolist(),
                    format_func=lambda x: f"ID: {x}",
                    key="bulk_delete_select"
                )

            with col2:
                if st.button("🗑️ 批量删除", type="secondary", disabled=not selected_indices):
                    if selected_indices:
                        try:
                            deleted_count = db_manager.bulk_delete_records(selected_table, selected_indices)
                            st.success(f"✅ 成功删除 {deleted_count} 条记录！")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ 批量删除失败：{str(e)}")

            with col3:
                if st.button("🔄 刷新数据"):
                    st.rerun()

            # 显示数据表格
            st.dataframe(
                df,
                use_container_width=True,
                height=400,
                hide_index=True
            )

            # 数据导出
            col1, col2, col3 = st.columns(3)
            with col1:
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 导出CSV",
                    data=csv,
                    file_name=f"{selected_table}_data.csv",
                    mime="text/csv"
                )
            with col2:
                json_data = df.to_json(orient='records', force_ascii=False, indent=2)
                st.download_button(
                    label="📥 导出JSON",
                    data=json_data,
                    file_name=f"{selected_table}_data.json",
                    mime="application/json"
                )
            with col3:
                # 显示记录统计
                st.metric("显示记录数", len(df))
        else:
            st.info("📭 暂无数据记录")

    with tab2:
        st.markdown("### ➕ 添加新记录")

        if columns_info:
            new_record = {}

            # 创建表单
            with st.form("add_record_form"):
                st.markdown("**填写新记录信息：**")

                for col_name, col_type, is_required, default_value in columns_info:
                    label = f"{col_name} {'*' if is_required else ''}"

                    if col_type == "INTEGER":
                        new_record[col_name] = st.number_input(
                            label,
                            step=1,
                            value=int(default_value) if default_value and default_value.isdigit() else 0,
                            key=f"add_{col_name}"
                        )
                    elif col_type == "REAL":
                        new_record[col_name] = st.number_input(
                            label,
                            value=float(default_value) if default_value else 0.0,
                            key=f"add_{col_name}"
                        )
                    elif col_type == "DATETIME":
                        new_record[col_name] = st.date_input(
                            label,
                            value=datetime.now().date() if default_value == "CURRENT_DATE" else None,
                            key=f"add_{col_name}"
                        )
                    else:  # TEXT
                        new_record[col_name] = st.text_input(
                            label,
                            value=default_value or "",
                            key=f"add_{col_name}"
                        )

                submitted = st.form_submit_button("💾 保存记录", type="primary")

                if submitted:
                    try:
                        # 验证必填字段
                        missing_fields = []
                        for col_name, col_type, is_required, default_value in columns_info:
                            if is_required and (not new_record[col_name] or str(new_record[col_name]).strip() == ""):
                                missing_fields.append(col_name)

                        if missing_fields:
                            st.error(f"❌ 以下必填字段不能为空：{', '.join(missing_fields)}")
                        else:
                            record_id = db_manager.insert_record(selected_table, new_record)
                            st.success(f"✅ 记录添加成功！记录ID：{record_id}")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ 添加记录失败：{str(e)}")
        else:
            st.warning("⚠️ 请先在表格设置中添加列")

    with tab3:
        st.markdown("### ✏️ 编辑/删除记录")

        df = get_cached_table_data(selected_table)

        if not df.empty:
            # 选择要编辑的记录
            record_options = [f"ID: {row['id']} - {row.get(columns_info[0][0] if columns_info else 'id', 'N/A')}"
                              for _, row in df.iterrows()]

            selected_option = st.selectbox("选择要编辑的记录", record_options)
            selected_id = int(selected_option.split(" - ")[0].split(": ")[1])
            selected_record = df[df['id'] == selected_id].iloc[0]

            # 编辑表单
            with st.form("edit_record_form"):
                st.markdown(f"**编辑记录 ID: {selected_id}**")

                edited_record = {}
                for col_name, col_type, is_required, default_value in columns_info:
                    current_value = selected_record[col_name]
                    label = f"{col_name} {'*' if is_required else ''}"

                    if col_type == "INTEGER":
                        edited_record[col_name] = st.number_input(
                            label,
                            value=int(current_value) if not pd.isna(current_value) else 0,
                            step=1,
                            key=f"edit_{col_name}_{selected_id}"
                        )
                    elif col_type == "REAL":
                        edited_record[col_name] = st.number_input(
                            label,
                            value=float(current_value) if not pd.isna(current_value) else 0.0,
                            key=f"edit_{col_name}_{selected_id}"
                        )
                    elif col_type == "DATETIME":
                        try:
                            datetime_value = pd.to_datetime(current_value).date() if not pd.isna(
                                current_value) else datetime.now().date()
                            edited_record[col_name] = st.date_input(
                                label,
                                value=datetime_value,
                                key=f"edit_{col_name}_{selected_id}"
                            )
                        except:
                            edited_record[col_name] = st.date_input(
                                label,
                                value=datetime.now().date(),
                                key=f"edit_{col_name}_{selected_id}"
                            )
                    else:  # TEXT
                        edited_record[col_name] = st.text_input(
                            label,
                            value=str(current_value) if not pd.isna(current_value) else "",
                            key=f"edit_{col_name}_{selected_id}"
                        )

                col1, col2 = st.columns(2)
                with col1:
                    update_submitted = st.form_submit_button("💾 更新记录", type="primary")
                with col2:
                    delete_submitted = st.form_submit_button("🗑️ 删除记录", type="secondary")

                if update_submitted:
                    try:
                        success = db_manager.update_record(selected_table, selected_id, edited_record)
                        if success:
                            st.success("✅ 记录更新成功！")
                            st.rerun()
                        else:
                            st.error("❌ 记录更新失败")
                    except Exception as e:
                        st.error(f"❌ 更新记录失败：{str(e)}")

                if delete_submitted:
                    if st.checkbox("确认删除此记录", key=f"confirm_delete_{selected_id}"):
                        try:
                            success = db_manager.delete_record(selected_table, selected_id)
                            if success:
                                st.success("✅ 记录删除成功！")
                                st.rerun()
                            else:
                                st.error("❌ 记录删除失败")
                        except Exception as e:
                            st.error(f"❌ 删除记录失败：{str(e)}")
        else:
            st.info("📭 暂无数据记录")

    with tab4:
        st.markdown("### 📥 数据导入")

        if columns_info:
            # 文件上传
            uploaded_file = st.file_uploader(
                "选择要导入的文件",
                type=['csv', 'xlsx', 'json'],
                help="支持CSV、Excel和JSON格式"
            )

            if uploaded_file is not None:
                try:
                    # 根据文件类型读取数据
                    if uploaded_file.name.endswith('.csv'):
                        df_import = pd.read_csv(uploaded_file)
                    elif uploaded_file.name.endswith('.xlsx'):
                        df_import = pd.read_excel(uploaded_file)
                    elif uploaded_file.name.endswith('.json'):
                        df_import = pd.read_json(uploaded_file)

                    st.success(f"✅ 文件读取成功！共 {len(df_import)} 行数据")

                    # 显示预览
                    st.markdown("**数据预览：**")
                    st.dataframe(df_import.head(10), use_container_width=True)

                    # 列映射
                    st.markdown("**列映射配置：**")
                    column_mapping = {}

                    for col_name, col_type, is_required, default_value in columns_info:
                        available_columns = ['不导入'] + list(df_import.columns)
                        selected_col = st.selectbox(
                            f"映射到列: {col_name} ({col_type})",
                            available_columns,
                            key=f"mapping_{col_name}"
                        )
                        if selected_col != '不导入':
                            column_mapping[col_name] = selected_col

                    # 导入选项
                    col1, col2 = st.columns(2)
                    with col1:
                        skip_errors = st.checkbox("跳过错误行", value=True, help="如果某行数据有问题，跳过该行继续导入")
                    with col2:
                        update_existing = st.checkbox("更新已存在记录", value=False, help="如果ID已存在，更新该记录")

                    # 执行导入
                    if st.button("📥 开始导入", type="primary"):
                        if not column_mapping:
                            st.error("❌ 请至少映射一个列")
                        else:
                            try:
                                # 准备导入数据
                                import_records = []
                                error_count = 0

                                for index, row in df_import.iterrows():
                                    try:
                                        record = {}
                                        for db_col, file_col in column_mapping.items():
                                            value = row[file_col]

                                            # 数据类型转换
                                            col_type = next((col[1] for col in columns_info if col[0] == db_col),
                                                            'TEXT')

                                            if col_type == "INTEGER":
                                                record[db_col] = int(value) if pd.notna(value) else None
                                            elif col_type == "REAL":
                                                record[db_col] = float(value) if pd.notna(value) else None
                                            elif col_type == "DATETIME":
                                                if pd.notna(value):
                                                    if isinstance(value, str):
                                                        record[db_col] = pd.to_datetime(value).date()
                                                    else:
                                                        record[db_col] = value
                                                else:
                                                    record[db_col] = None
                                            else:  # TEXT
                                                record[db_col] = str(value) if pd.notna(value) else None

                                        import_records.append(record)

                                    except Exception as e:
                                        if skip_errors:
                                            error_count += 1
                                            continue
                                        else:
                                            raise e

                                # 批量插入
                                if import_records:
                                    inserted_count = db_manager.bulk_insert_records(selected_table, import_records)
                                    st.success(f"✅ 导入成功！共导入 {inserted_count} 条记录")
                                    if error_count > 0:
                                        st.warning(f"⚠️ 跳过了 {error_count} 行有问题的数据")
                                    st.rerun()
                                else:
                                    st.error("❌ 没有有效数据可导入")

                            except Exception as e:
                                st.error(f"❌ 导入失败：{str(e)}")
                except Exception as e:
                    st.error(f"❌ 文件读取失败：{str(e)}")
        else:
            st.warning("⚠️ 请先在表格设置中添加列")

    with tab5:
        st.markdown("### ⚙️ 表格设置")

        # 显示现有列
        if columns_info:
            st.markdown("**现有列配置：**")
            for i, (col_name, col_type, is_required, default_value) in enumerate(columns_info):
                with st.expander(f"列: {col_name} ({col_type})"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**类型：** {col_type}")
                        st.write(f"**必填：** {'是' if is_required else '否'}")
                        st.write(f"**默认值：** {default_value or '无'}")
                    with col2:
                        if st.button("🗑️ 删除列", key=f"delete_col_{col_name}"):
                            try:
                                db_manager.delete_column(selected_table, col_name)
                                st.success(f"✅ 列 '{col_name}' 删除成功！")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ 删除列失败：{str(e)}")

        # 添加新列
        st.markdown("**添加新列：**")
        with st.form("add_column_form"):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                new_col_name = st.text_input("列名", key="new_col_name")
            with col2:
                new_col_type = st.selectbox("数据类型", ["TEXT", "INTEGER", "REAL", "DATETIME"], key="new_col_type")
            with col3:
                is_required = st.checkbox("必填", key="new_col_required")

            default_value = st.text_input("默认值（可选）", key="new_col_default")

            if st.form_submit_button("➕ 添加列", type="primary"):
                if new_col_name:
                    try:
                        db_manager.add_column(selected_table, new_col_name, new_col_type, is_required, default_value)
                        st.success(f"✅ 列 '{new_col_name}' 添加成功！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 添加列失败：{str(e)}")
                else:
                    st.error("❌ 列名不能为空")

else:

    st.markdown("### 🆕 创建新表格")

with st.form("create_table_form"):
    col1, col2 = st.columns(2)
    with col1:
        table_name = st.text_input("表格名称", placeholder="例如：products, users, orders")
    with col2:
        display_name = st.text_input("显示名称（可选）", placeholder="例如：产品表")

    description = st.text_area("表格描述（可选）", placeholder="描述这个表格的用途...")

    if st.form_submit_button("🆕 创建表格", type="primary"):
        if table_name:
            try:
                db_manager.create_table(table_name, display_name, description)
                st.success(f"✅ 表格 '{table_name}' 创建成功！")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 创建表格失败：{str(e)}")
        else:
            st.error("❌ 表格名称不能为空")

# 侧边栏 - 快速操作
st.sidebar.markdown("### 🚀 快速操作")

if selected_table:
    if st.sidebar.button("🔄 刷新数据"):
        clear_cache()
        st.rerun()

    if st.sidebar.button("📊 查看统计"):
        df = get_cached_table_data(selected_table)
        if not df.empty:
            st.sidebar.markdown("**数据统计：**")
            for col in df.select_dtypes(include=['number']).columns:
                if col not in ['id']:
                    st.sidebar.metric(col, f"{df[col].mean():.2f}", f"总计: {df[col].sum()}")

# 全局操作
st.sidebar.markdown("### 🔧 系统操作")
if st.sidebar.button("🗑️ 清除缓存"):
    clear_cache()
    st.sidebar.success("✅ 缓存已清除")

# 页脚
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 1rem;">
    <p>📊 Eco - 数据库管理工具 | 类似Excel的数据库操作界面</p>
</div>
""", unsafe_allow_html=True)