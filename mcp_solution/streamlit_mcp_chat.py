import streamlit as st
import asyncio
import json
import logging
import os
import shutil
from typing import Dict, List, Optional, Any
import requests
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 自定义CSS样式
st.markdown("""
<style>
/* 整体样式 */
body {
    font-family: 'Arial', sans-serif;
    background-color: #f0f2f6;
}

/* 标题样式 */
.stTitle {
    color: #1e88e5;
    font-weight: bold;
    text-align: center;
    margin-bottom: 30px;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
}

/* 副标题样式 */
.stSubheader {
    color: #424242;
    font-weight: 600;
    margin-top: 20px;
    margin-bottom: 15px;
    border-bottom: 2px solid #e0e0e0;
    padding-bottom: 5px;
}

/* 侧边栏样式 */
.sidebar .sidebar-content {
    background-color: #fafafa;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

/* 按钮样式 */
.stButton > button {
    background-color: #1e88e5;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
    transition: all 0.3s ease;
    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
}

.stButton > button:hover {
    background-color: #1565c0;
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
}

/* 聊天容器样式 */
.stContainer {
    background-color: white;
    border-radius: 10px;
    padding: 20px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    margin-bottom: 20px;
}

/* 信息框样式 */
.stInfo {
    background-color: #e3f2fd;
    border-left: 5px solid #2196f3;
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

/* 成功框样式 */
.stSuccess {
    background-color: #e8f5e8;
    border-right: 5px solid #4caf50;
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

/* 错误框样式 */
.stError {
    background-color: #ffebee;
    border-left: 5px solid #f44336;
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

/* 输入框样式 */
.stChatInput > div > div > input {
    border-radius: 25px;
    padding: 12px 20px;
    border: 2px solid #e0e0e0;
    transition: all 0.3s ease;
}

.stChatInput > div > div > input:focus {
    border-color: #1e88e5;
    box-shadow: 0 0 0 3px rgba(30, 136, 229, 0.1);
}

/* 聊天消息样式 */
.chat-message {
    margin: 10px 0;
    padding: 15px;
    border-radius: 18px;
    max-width: 80%;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}

/* 分隔线样式 */
.divider {
    height: 2px;
    background: linear-gradient(to right, transparent, #e0e0e0, transparent);
    margin: 20px 0;
}

/* 运行状态样式 */
.running-status {
    color: #4caf50;
    font-weight: 600;
    animation: pulse 1.5s infinite;
}

/* 旋转加载动画 */
.spinner {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid rgba(76, 175, 80, 0.3);
    border-radius: 50%;
    border-top-color: #4caf50;
    animation: spin 1s ease-in-out infinite;
    margin-left: 8px;
    vertical-align: middle;
}

/* 旋转动画 */
@keyframes spin {
    to { transform: rotate(360deg); }
}

/* 脉冲动画 */
@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.7; }
    100% { opacity: 1; }
}

/* 助手消息样式 */
.assistant-message {
    background-color: #e8f5e8;
    border-right: 5px solid #4caf50;
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    font-size: 16px;
    line-height: 1.5;
}
</style>
""", unsafe_allow_html=True)

# 应用标题
st.title("MCP Client Chat")

# 添加分隔线
st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# 定义异步事件循环
if 'loop' not in st.session_state:
    st.session_state.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state.loop)

# 递归处理字典中的环境变量占位符
def resolve_env_vars(data: Any) -> Any:
    if isinstance(data, dict):
        return {key: resolve_env_vars(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [resolve_env_vars(item) for item in data]
    elif isinstance(data, str):
        return os.path.expandvars(data)
    else:
        return data

# 用于管理 MCP客户端的配置和环境变量
class Configuration:
    def __init__(self) -> None:
        self.load_env()
        self.base_url = os.getenv("LLM_BASE_URL")
        self.api_key = os.getenv("LLM_API_KEY")
        self.chat_model = os.getenv("LLM_CHAT_MODEL")

    @staticmethod
    def load_env() -> None:
        load_dotenv()

    @staticmethod
    def load_config(file_path: str) -> Dict[str, Any]:
        with open(file_path, 'r') as f:
            config = json.load(f)
            return resolve_env_vars(config)

    @property
    def llm_api_key(self) -> str:
        if not self.api_key:
            raise ValueError("LLM_API_KEY not found in environment variables")
        return self.api_key

    @property
    def llm_base_url(self) -> str:
        if not self.base_url:
            raise ValueError("LLM_BASE_URL not found in environment variables")
        return self.base_url

    @property
    def llm_chat_model(self) -> str:
        if not self.chat_model:
            raise ValueError("LLM_CHAT_MODEL not found in environment variables")
        return self.chat_model

# 代表各个资源及其属性和格式
class Resource:
    def __init__(self, uri: str, name: str, description: str, mimeType: str) -> None:
        self.uri: str = uri
        self.name: str = name
        self.description: str = description
        self.mimeType: str = mimeType

    def format_for_llm(self) -> str:
        return f"""
                URI: {self.uri}
                Name: {self.name}
                Description: {self.description}
                MimeType: {self.mimeType}
                """

# 代表各个工具及其属性和格式
class Tool:
    def __init__(self, name: str, description: str, input_schema: Dict[str, Any]) -> None:
        self.name: str = name
        self.description: str = description
        self.input_schema: Dict[str, Any] = input_schema

    def format_for_llm(self) -> str:
        args_desc = []
        if 'properties' in self.input_schema:
            for param_name, param_info in self.input_schema['properties'].items():
                arg_desc = f"- {param_name}: {param_info.get('description', 'No description')}"
                if param_name in self.input_schema.get('required', []):
                    arg_desc += " (required)"
                args_desc.append(arg_desc)

        return f"""
                Tool: {self.name}
                Description: {self.description}
                Arguments:
                {chr(10).join(args_desc)}
                """

# 处理 MCP 服务器初始化、工具发现和执行
class Server:
    def __init__(self, name: str, config: Dict[str, Any]) -> None:
        self.name: str = name
        self.config: Dict[str, Any] = config
        self.stdio_context: Optional[Any] = None
        self.session: Optional[ClientSession] = None
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self.capabilities: Optional[Dict[str, Any]] = None
        self.status = "stopped"
        self.output = []

    async def initialize(self) -> None:
        server_params = StdioServerParameters(
            command=shutil.which("npx") if self.config['command'] == "npx" else self.config['command'],
            args=self.config['args'],
            env={**os.environ, **self.config['env']} if self.config.get('env') else None
        )
        try:
            self.stdio_context = stdio_client(server_params)
            read, write = await self.stdio_context.__aenter__()
            self.session = ClientSession(read, write)
            await self.session.__aenter__()
            self.capabilities = await self.session.initialize()
            self.status = "running"
            self.output.append(f"Server {self.name} initialized successfully")
        except Exception as e:
            logging.error(f"Error initializing server {self.name}: {e}")
            await self.cleanup()
            raise

    async def list_tools(self) -> List[Any]:
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")
        tools_response = await self.session.list_tools()
        tools = []
        for item in tools_response:
            if isinstance(item, tuple) and item[0] == 'tools':
                for tool in item[1]:
                    tools.append(Tool(tool.name, tool.description, tool.inputSchema))
        return tools

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], retries: int = 2, delay: float = 1.0) -> Any:
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")
        attempt = 0
        while attempt < retries:
            try:
                logging.info(f"Executing {tool_name}...")
                result = await self.session.call_tool(tool_name, arguments)
                return result
            except Exception as e:
                attempt += 1
                logging.warning(f"Error executing tool: {e}. Attempt {attempt} of {retries}.")
                if attempt < retries:
                    logging.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logging.error("Max retries reached. Failing.")
                    raise

    async def list_resources(self) -> List[Any]:
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")
        resources_response = await self.session.list_resources()
        resources = []
        for item in resources_response:
            if isinstance(item, tuple) and item[0] == 'resources':
                for resource in item[1]:
                    resources.append(Resource(str(resource.uri), resource.name, resource.description, resource.mimeType))
        return resources

    async def read_resource(self, resource_uri: str, retries: int = 2, delay: float = 1.0) -> Any:
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")
        attempt = 0
        while attempt < retries:
            try:
                logging.info(f"Executing {resource_uri}...")
                result = await self.session.read_resource(resource_uri)
                return result
            except Exception as e:
                attempt += 1
                logging.warning(f"Error executing resource: {e}. Attempt {attempt} of {retries}.")
                if attempt < retries:
                    logging.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logging.error("Max retries reached. Failing.")
                    raise

    async def cleanup(self) -> None:
        async with self._cleanup_lock:
            try:
                if self.session:
                    try:
                        await self.session.__aexit__(None, None, None)
                    except Exception as e:
                        logging.warning(f"Warning during session cleanup for {self.name}: {e}")
                    finally:
                        self.session = None

                if self.stdio_context:
                    try:
                        await self.stdio_context.__aexit__(None, None, None)
                    except (RuntimeError, asyncio.CancelledError) as e:
                        logging.info(f"Note: Normal shutdown message for {self.name}: {e}")
                    except Exception as e:
                        logging.warning(f"Warning during stdio cleanup for {self.name}: {e}")
                    finally:
                        self.stdio_context = None
                self.status = "stopped"
            except Exception as e:
                logging.error(f"Error during cleanup of server {self.name}: {e}")

# 管理与LLM的通信
class LLMClient:
    def __init__(self, base_url: str, api_key: str, chat_model: str) -> None:
        self.base_url: str = base_url
        self.api_key: str = api_key
        self.chat_model: str = chat_model

    def get_response(self, messages: List[Dict[str, str]]) -> str:
        url = self.base_url
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "messages": messages,
            "temperature": 1.0,
            "top_p": 1.0,
            "max_tokens": 4000,
            "model": self.chat_model
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except requests.exceptions.RequestException as e:
            error_message = f"Error getting LLM response: {str(e)}"
            logging.error(error_message)
            if e.response is not None:
                status_code = e.response.status_code
                logging.error(f"Status code: {status_code}")
                logging.error(f"Response details: {e.response.text}")
            return f"I encountered an error: {error_message}. Please try again or rephrase your request."

# 协调用户、 LLM和工具之间的交互
class ChatSession:
    def __init__(self, servers: List[Server], llm_client: LLMClient) -> None:
        self.servers: List[Server] = servers
        self.llm_client: LLMClient = llm_client
        self.messages = [{
            "role": "system",
            "content": ""
        }]

    async def initialize(self) -> None:
        # 初始化所有服务器
        for server in self.servers:
            try:
                await server.initialize()
            except Exception as e:
                logging.error(f"Failed to initialize server: {e}")
                await self.cleanup_servers()
                raise
        
        # 获取所有工具和资源
        all_tools = []
        for server in self.servers:
            try:
                tools = await server.list_tools()
                all_tools.extend(tools)
            except Exception as e:
                logging.error(f"Server {server.name} does not have 'list_tools' method: {e}")
        
        all_resources = []
        for server in self.servers:
            try:
                resources = await server.list_resources()
                all_resources.extend(resources)
            except Exception as e:
                logging.error(f"Server {server.name} does not have 'list_resources' method: {e}")
        
        # 构建系统消息
        tools_description = "\n".join([tool.format_for_llm() for tool in all_tools])
        resources_description = "\n".join([resource.format_for_llm() for resource in all_resources])
        
        system_message = f"""You are a helpful assistant with access to these resources and tools: 

                            resources:{resources_description}
                            tools:{tools_description}
                            Choose the appropriate resource or tool based on the user's question. If no resource or tool is needed, reply directly.

                            IMPORTANT: When you need to use a resource, you must ONLY respond with the exact JSON object format below, nothing else:
                            {{
                                "resource": "resource-name",
                                "uri": "resource-URI"
                            }}

                            After receiving a resource's response:
                            1. Transform the raw data into a natural, conversational response
                            2. Keep responses concise but informative
                            3. Focus on the most relevant information
                            4. Use appropriate context from the user's question
                            5. Avoid simply repeating the raw data

                            IMPORTANT: When you need to use a tool, you must ONLY respond with the exact JSON object format below, nothing else:
                            {{
                                "tool": "tool-name",
                                "arguments": {{
                                    "argument-name": "value"
                                }}
                            }}

                            After receiving a tool's response:
                            1. Transform the raw data into a natural, conversational response
                            2. Keep responses concise but informative
                            3. Focus on the most relevant information
                            4. Use appropriate context from the user's question
                            5. Avoid simply repeating the raw data

                            Please use only the resources or tools that are explicitly defined above."""
        
        self.messages = [{"role": "system", "content": system_message}]

    async def cleanup_servers(self) -> None:
        cleanup_tasks = []
        for server in self.servers:
            cleanup_tasks.append(asyncio.create_task(server.cleanup()))

        if cleanup_tasks:
            try:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            except Exception as e:
                logging.warning(f"Warning during final cleanup: {e}")

    async def process_llm_response(self, llm_response: str) -> str:
        try:
            llm_call = json.loads(llm_response)
            if "tool" in llm_call and "arguments" in llm_call:
                logging.info(f"Executing tool: {llm_call['tool']}")
                logging.info(f"With arguments: {llm_call['arguments']}")
                for server in self.servers:
                    try:
                        tools = await server.list_tools()
                        if any(tool.name == llm_call["tool"] for tool in tools):
                            try:
                                result = await server.execute_tool(llm_call["tool"], llm_call["arguments"])
                                # 在结果中添加服务端信息
                                return f"Tool execution result: {result} (handled by {server.name} service)"
                            except Exception as e:
                                error_msg = f"Error executing tool: {str(e)} (handled by {server.name} service)"
                                logging.error(error_msg)
                                return error_msg
                    except Exception as e:
                        logging.error(f"Server {server.name} does not have 'list_tools' method: {e}")
                        continue
                return f"No server found with tool: {llm_call['tool']}"
            
            if "resource" in llm_call:
                logging.info(f"Executing resource: {llm_call['resource']}")
                logging.info(f"With URI: {llm_call['uri']}")
                for server in self.servers:
                    try:
                        resources = await server.list_resources()
                        if any(resource.uri == llm_call["uri"] for resource in resources):
                            try:
                                result = await server.read_resource(llm_call["uri"])
                                # 在结果中添加服务端信息
                                return f"Resource execution result: {result} (handled by {server.name} service)"
                            except Exception as e:
                                error_msg = f"Error executing resource: {str(e)} (handled by {server.name} service)"
                                logging.error(error_msg)
                                return error_msg
                    except Exception as e:
                        logging.error(f"Server {server.name} does not have 'list_resources' method: {e}")
                        continue
                return f"No server found with resource: {llm_call['uri']}"
            return llm_response
        except json.JSONDecodeError:
            return llm_response

    async def send_message(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})
        llm_response = self.llm_client.get_response(self.messages)
        self.messages.append({"role": "assistant", "content": llm_response})
        
        result = await self.process_llm_response(llm_response)
        if result != llm_response:
            self.messages.append({"role": "system", "content": result})
            final_response = self.llm_client.get_response(self.messages)
            
            # 尝试从result中提取服务端信息 Tool execution result: meta=None content=[TextContent(type='text', text='2.0', annotations=None)] isError=False (handled by calculator service)
            # 获取上面括号中内容
            server_info = ""
            if "handled by" in result:
                server_info = result.split("(")[-1].strip(")")
                # 使用HTML标签设置小一号灰色字体
                server_info = f" <small style='color: gray;'>({server_info})</small>"
            
            # 在最终回答中添加服务端信息
            final_response_with_server = final_response + server_info
            self.messages.append({"role": "assistant", "content": final_response_with_server})
            return final_response_with_server
        else:
            return llm_response

# 初始化应用
def init_app():
    if 'initialized' not in st.session_state:
        st.session_state.initialized = False
        st.session_state.chat_session = None
        st.session_state.messages = []
        st.session_state.servers = []

# 主应用逻辑
def main():
    init_app()
    
    # 应用设置
    st.sidebar.title("MCP Servers Status")
    
    # 自动初始化MCP客户端
    if not st.session_state.initialized:
        try:
            # 使用占位符显示初始化状态
            init_placeholder = st.sidebar.empty()
            init_placeholder.info("Initializing MCP Servers...")
            
            # 加载配置
            config = Configuration()
            server_config = config.load_config('servers_config.json')
            
            # 创建服务器实例
            servers = [Server(name, srv_config) for name, srv_config in server_config['mcpServers'].items()]
            st.session_state.servers = servers
            
            # 创建LLM客户端
            llm_client = LLMClient(config.llm_base_url, config.llm_api_key, config.llm_chat_model)
            
            # 创建聊天会话
            chat_session = ChatSession(servers, llm_client)
            
            # 初始化聊天会话
            st.session_state.loop.run_until_complete(chat_session.initialize())
            st.session_state.chat_session = chat_session
            st.session_state.initialized = True
            
            # 更新占位符为成功状态
            init_placeholder.success("MCP Client initialized successfully!")
            
            # 初始化对话记录列表
            if 'chat_history' not in st.session_state:
                st.session_state.chat_history = []
                # 添加欢迎消息
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": "MCP Client initialized successfully! I'm ready to help you with your requests."
                })
            
            # 刷新页面，确保所有状态都能显示
            st.rerun()
        except Exception as e:
            st.error(f"Error initializing MCP Client: {e}")
            logging.error(f"Error initializing MCP Client: {e}")
    else:
        # 显示服务器状态
        st.sidebar.subheader("Server Status")
        for server in st.session_state.servers:
            if server.status == "running":
                # 添加运行状态的动画效果
                st.sidebar.markdown(f"{server.name}: <span class='running-status'>running</span> <span class='spinner'></span>", unsafe_allow_html=True)
            else:
                st.sidebar.write(f"{server.name}: {server.status}")
        
        # 清理按钮
        if st.sidebar.button("Cleanup Servers"):
            st.session_state.loop.run_until_complete(st.session_state.chat_session.cleanup_servers())
            st.session_state.initialized = False
            st.success("Servers cleaned up successfully!")
    
    # 聊天界面
    st.subheader("Chat Interface")
    
    # 聊天容器
    chat_container = st.container()
    
    # 显示聊天历史，左右分栏
    with chat_container:
        # 初始化对话记录列表
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        
        # 显示所有对话记录
        for chat in st.session_state.chat_history:
            if chat["role"] == "user":
                # 用户消息显示在左侧
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.write("You:")
                with col2:
                    st.info(chat["content"])
            else:
                # 助手消息显示在右侧，支持HTML渲染
                col1, col2 = st.columns([3, 1])
                with col1:
                    # 使用markdown渲染，支持HTML
                    st.markdown(f"<div class='assistant-message'>{chat['content']}</div>", unsafe_allow_html=True)
                with col2:
                    st.write("Assistant:")
    
    # 用户输入
    user_input = st.chat_input("Enter your message:")
    if user_input and st.session_state.initialized:
        # 添加用户消息到聊天历史
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        # 处理用户消息
        with st.spinner("Processing..."):
            response = st.session_state.loop.run_until_complete(st.session_state.chat_session.send_message(user_input))
        
        # 添加助手响应到聊天历史
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        
        # 刷新页面
        st.rerun()

# 运行应用
if __name__ == "__main__":
    main()