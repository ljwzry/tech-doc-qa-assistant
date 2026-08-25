import streamlit as st
import requests, json, os

API_BASE = "http://localhost:8000/api"

st.set_page_config(page_title="TechDoc QA", page_icon="📚", layout="wide")

# ============ 自定义样式 ============
st.markdown("""
<style>
/* 主标题样式 */
h1 {
    padding-bottom: 0.3rem;
    border-bottom: 2px solid #4CAF50;
}

/* 聊天消息区域美化 */
.stChatMessage {
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

/* 用户消息 */
[data-testid="stChatMessage"]:has([data-testid="chat-avatar-user"]) {
    background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
}

/* AI 消息 */
[data-testid="stChatMessage"]:has([data-testid="chat-avatar-assistant"]) {
    background: linear-gradient(135deg, #f1f8e9 0%, #dcedc8 100%);
}

/* 聊天输入框 */
[data-testid="stChatInput"] {
    border-radius: 12px;
}
[data-testid="stChatInput"] textarea {
    border-radius: 10px;
}

/* 侧边栏样式 */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #fafafa 0%, #f0f7ff 100%);
}
section[data-testid="stSidebar"] h2 {
    font-size: 1.1rem;
    color: #2e7d32;
    border-left: 3px solid #4CAF50;
    padding-left: 0.5rem;
}

/* 工具调用提示动画 */
.tool-status {
    display: inline-block;
    animation: pulse 1.2s ease-in-out infinite;
    color: #1565c0;
    font-style: italic;
}
@keyframes pulse {
    0%, 100% { opacity: 0.6; }
    50% { opacity: 1; }
}

/* 按钮圆角 */
.stButton > button {
    border-radius: 8px;
    transition: all 0.2s;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 6px rgba(0,0,0,0.12);
}

/* 欢迎卡片 */
.welcome-card {
    text-align: center;
    padding: 2.5rem 1.5rem;
    border-radius: 16px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    margin: 1rem 0;
}
.welcome-card h2 {
    color: white;
    border: none;
    font-size: 1.6rem;
}
.welcome-card p {
    opacity: 0.9;
    font-size: 0.95rem;
}
</style>
""", unsafe_allow_html=True)

# ============ 会话管理 ============
def create_session():
    """创建新会话"""
    try:
        r = requests.post(f"{API_BASE}/sessions", timeout=5)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", {}).get("session_id")
    except:
        pass
    return None

def get_session(session_id):
    """获取会话详情"""
    try:
        r = requests.get(f"{API_BASE}/sessions/{session_id}", timeout=5)
        if r.status_code == 200:
            return r.json().get("data")
    except:
        pass
    return None

def list_sessions():
    """获取会话列表"""
    try:
        r = requests.get(f"{API_BASE}/sessions", timeout=5)
        if r.status_code == 200:
            return r.json().get("data", [])
    except:
        pass
    return []

def delete_session(session_id):
    """删除会话"""
    try:
        r = requests.delete(f"{API_BASE}/sessions/{session_id}", timeout=5)
        return r.status_code == 200
    except:
        return False

# 初始化会话状态
if "session_id" not in st.session_state:
    st.session_state.session_id = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_project" not in st.session_state:
    st.session_state.selected_project = ""
if "upload_project" not in st.session_state:
    st.session_state.upload_project = "general"

# 方案1：从 URL 查询参数读取 session_id（用于切换/刷新后恢复会话）
try:
    query_params = st.query_params
    url_session_id = query_params.get("sid", None)
    if url_session_id and url_session_id != st.session_state.session_id:
        st.session_state.session_id = url_session_id
        # 加载对应的消息
        session_data = get_session(url_session_id)
        if session_data:
            st.session_state.messages = session_data.get("messages", [])
except Exception:
    pass

# 如果有 session_id 但没有 messages，从后端加载
if st.session_state.session_id and not st.session_state.messages:
    session_data = get_session(st.session_state.session_id)
    if session_data:
        st.session_state.messages = session_data.get("messages", [])

# 不再在页面加载时自动创建空会话，改为用户发消息时延迟创建

# 页面标题
st.title("📚 TechDoc QA Assistant")
st.caption("技术文档智能问答助手")


# ============ 辅助函数 ============
def get_projects():
    """获取项目列表"""
    try:
        r = requests.get(f"{API_BASE}/documents/projects", timeout=5)
        if r.status_code == 200:
            data = r.json().get("data", {})
            return data.get("projects", ["general"])
    except:
        pass
    return ["general"]


def get_docs(project=None):
    """获取文档列表（包含索引状态和孤儿索引信息）"""
    try:
        params = {}
        if project:
            params["project"] = project
        r = requests.get(f"{API_BASE}/documents/list", params=params, timeout=5)
        if r.status_code == 200:
            return r.json().get("data", {"documents": [], "orphaned": []})
    except:
        pass
    return {"documents": [], "orphaned": []}


# ============ 侧边栏 ============
with st.sidebar:
    # ---------- 会话管理 ----------
    st.header("💬 会话管理")
    
    # 当前会话ID
    if st.session_state.session_id:
        st.code(f"会话ID: {st.session_state.session_id}")
    
    # 创建新会话按钮
    if st.button("➕ 新对话", key="new_session_btn"):
        # 不再立即创建会话，清除当前状态即可
        # 会话在用户发第一条消息时延迟创建
        st.session_state.session_id = ""
        st.session_state.messages = []
        # 新对话清除 sid 参数
        st.components.v1.html(
            '''
            <script>
                setTimeout(() => {
                    const currentUrl = new URL(window.parent.location.href);
                    currentUrl.searchParams.delete('sid');
                    window.parent.location.href = currentUrl.toString();
                }, 300);
            </script>
            ''',
            height=0, width=0
        )
    
    # 历史会话列表
    sessions = list_sessions()
    if sessions:
        st.caption("历史会话")
        for sess in sessions:
            sid = sess.get("session_id", "")
            msgs = sess.get("messages", [])
            if msgs:
                preview = msgs[0].get("content", "")[:30] + "..." if len(msgs[0].get("content", "")) > 30 else msgs[0].get("content", "")
                col_sess, col_del = st.columns([4, 1])
                with col_sess:
                    if st.button(preview, key=f"switch_sess_{sid}", use_container_width=True):
                        st.session_state.session_id = sid
                        # 加载会话消息
                        session_data = get_session(sid)
                        if session_data:
                            st.session_state.messages = session_data.get("messages", [])
                        # 通过 URL 参数传递 sid，刷新后恢复会话
                        st.components.v1.html(
                            f'''
                            <script>
                                setTimeout(() => {{
                                    const currentUrl = new URL(window.parent.location.href);
                                    currentUrl.searchParams.set('sid', '{sid}');
                                    window.parent.location.href = currentUrl.toString();
                                }}, 100);
                            </script>
                            ''',
                            height=0, width=0
                        )
                with col_del:
                    if st.button("🗑", key=f"del_sess_{sid}"):
                        delete_session(sid)
                        if st.session_state.session_id == sid:
                            st.session_state.session_id = ""
                            st.session_state.messages = []
                        # 刷新时清除 sid 参数
                        st.components.v1.html(
                            '''
                            <script>
                                setTimeout(() => {
                                    const currentUrl = new URL(window.parent.location.href);
                                    currentUrl.searchParams.delete('sid');
                                    window.parent.location.href = currentUrl.toString();
                                }, 300);
                            </script>
                            ''',
                            height=0, width=0
                        )

    st.divider()

    # ---------- 检索范围 ----------
    st.header("🎯 检索范围")
    projects = get_projects()
    projects_with_all = [""] + projects
    st.session_state.selected_project = st.selectbox(
        "选择问答检索的项目范围",
        projects_with_all,
        index=projects_with_all.index(st.session_state.selected_project) if st.session_state.selected_project in projects_with_all else 0,
        format_func=lambda x: "全部项目" if x == "" else x,
        key="retrieve_project_selector"
    )

    st.divider()

    # ---------- 文档上传（单个/批量上传到已有项目） ----------
    st.header("📤 文档上传")
    
    # 上传目标项目选择
    upload_projects = get_projects()
    st.session_state.upload_project = st.selectbox(
        "上传到项目",
        upload_projects,
        index=upload_projects.index(st.session_state.upload_project) if st.session_state.upload_project in upload_projects else 0,
        key="upload_project_selector"
    )

    # 批量文件上传
    uploaded_files = st.file_uploader(
        f"选择文档（上传到: {st.session_state.upload_project}）",
        type=["pdf", "md", "txt"],
        accept_multiple_files=True,
        key="doc_uploader"
    )

    if uploaded_files:
        st.info(f"已选择 {len(uploaded_files)} 个文件")
        if st.button(f"⬆️ 上传并索引到 {st.session_state.upload_project}", type="primary", key="upload_btn"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            success_count = 0
            fail_count = 0
            total_chunks = 0

            for i, file in enumerate(uploaded_files):
                filename = file.name
                status_text.text(f"正在上传: {filename} ({i+1}/{len(uploaded_files)})")
                try:
                    files = {"file": (filename, file.getvalue())}
                    params = {"project": st.session_state.upload_project}
                    r = requests.post(f"{API_BASE}/documents/upload", files=files, params=params, timeout=120)
                    if r.status_code == 200:
                        result = r.json().get("data", {})
                        success_count += 1
                        total_chunks += result.get("chunks", 0)
                    else:
                        fail_count += 1
                except requests.exceptions.Timeout:
                    fail_count += 1
                except requests.exceptions.ConnectionError:
                    fail_count += 1
                except Exception:
                    fail_count += 1
                progress_bar.progress((i + 1) / len(uploaded_files))

            status_text.empty()
            progress_bar.empty()
            if success_count > 0:
                st.success(f"✅ 成功 {success_count} 个, 失败 {fail_count} 个, 共 {total_chunks} 块")
                # 使用 JavaScript 清空文件上传器 + 刷新页面（保持当前会话）
                current_sid = st.session_state.session_id or ""
                st.components.v1.html(
                    f'''
                    <script>
                        setTimeout(() => {{
                            const uploader = window.parent.document.querySelector('input[type="file"]');
                            if (uploader) {{
                                uploader.value = '';
                            }}
                        }}, 500);
                        setTimeout(() => {{
                            const currentUrl = new URL(window.parent.location.href);
                            {f"currentUrl.searchParams.set('sid', '{current_sid}');" if current_sid else "currentUrl.searchParams.delete('sid');"}
                            window.parent.location.href = currentUrl.toString();
                        }}, 1200);
                    </script>
                    ''',
                    height=0,
                    width=0
                )
            if fail_count > 0 and success_count == 0:
                st.error("❌ 全部上传失败")

    st.divider()

    # ---------- 项目管理（新建项目 + 上传整个项目） ----------
    st.header("📁 项目管理")
    
    # 新建项目
    with st.expander("➕ 新建项目", expanded=False):
        new_project_name = st.text_input("项目名称", placeholder="如: greenhouse-simulator", key="new_project_name")
        if st.button("创建项目", key="create_proj_btn"):
            if new_project_name:
                new_name = new_project_name.strip().replace(" ", "-")
                if new_name and new_name not in upload_projects:
                    proj_dir = os.path.join("./data/docs", new_name)
                    os.makedirs(proj_dir, exist_ok=True)
                    st.success(f"项目 '{new_name}' 已创建")
                    st.session_state.upload_project = new_name
                else:
                    st.warning("项目名已存在或为空")

    # 上传整个项目
    with st.expander("📦 上传整个项目技术文档", expanded=False):
        target_project = st.text_input("项目名称", placeholder="如: my-project", key="upload_whole_project")
        project_files = st.file_uploader(
            "选择项目下的所有文档（支持子目录）",
            type=["pdf", "md", "txt"],
            accept_multiple_files=True,
            key="project_files_uploader"
        )

        if project_files and target_project:
            st.info(f"已选择 {len(project_files)} 个文件，将上传到项目: {target_project}")
            if st.button("📤 上传整个项目", type="primary", key="upload_whole_btn"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                success_count = 0
                fail_count = 0
                total_chunks = 0

                # 先创建项目目录
                proj_dir = os.path.join("./data/docs", target_project)
                os.makedirs(proj_dir, exist_ok=True)

                for i, file in enumerate(project_files):
                    status_text.text(f"正在上传: {file.name} ({i+1}/{len(project_files)})")
                    try:
                        files = {"file": (file.name, file.getvalue())}
                        params = {"project": target_project}
                        r = requests.post(f"{API_BASE}/documents/upload", files=files, params=params, timeout=120)
                        if r.status_code == 200:
                            result = r.json().get("data", {})
                            success_count += 1
                            total_chunks += result.get("chunks", 0)
                        else:
                            fail_count += 1
                    except Exception as e:
                        fail_count += 1
                    progress_bar.progress((i + 1) / len(project_files))

                status_text.empty()
                progress_bar.empty()
                if success_count > 0:
                    st.success(f"✅ 项目 '{target_project}' 上传完成: 成功 {success_count} 个, 失败 {fail_count} 个, 共 {total_chunks} 块")
                    st.session_state.upload_project = target_project
                    current_sid = st.session_state.session_id or ""
                    st.components.v1.html(
                        f'''
                        <script>
                            setTimeout(() => {{
                                const uploaders = window.parent.document.querySelectorAll('input[type="file"]');
                                uploaders.forEach(uploader => {{
                                    uploader.value = '';
                                }});
                            }}, 500);
                            setTimeout(() => {{
                                const currentUrl = new URL(window.parent.location.href);
                                {f"currentUrl.searchParams.set('sid', '{current_sid}');" if current_sid else "currentUrl.searchParams.delete('sid');"}
                                window.parent.location.href = currentUrl.toString();
                            }}, 1200);
                        </script>
                        ''',
                        height=0,
                        width=0
                    )
                if fail_count > 0 and success_count == 0:
                    st.error("❌ 全部上传失败")

    st.divider()

    # ---------- 已索引文档（按项目分类，显示索引状态+孤儿索引清理） ----------
    st.header("📋 已索引文档")
    list_result = get_docs(st.session_state.selected_project if st.session_state.selected_project else None)
    
    # 适配新的返回格式: {"documents": [...], "orphaned": [...]}
    if isinstance(list_result, dict):
        docs = list_result.get("documents", [])
        orphaned = list_result.get("orphaned", [])
    else:
        docs = list_result if isinstance(list_result, list) else []
        orphaned = []
    
    # 先处理孤儿索引（在文档列表之上显示警告和清理按钮）
    if orphaned:
        st.warning(f"⚠️ 检测到 {len(orphaned)} 个孤儿索引（磁盘文件已删除，但知识库中仍有残留）")
        with st.expander(f"🔴 孤儿索引详情 ({len(orphaned)} 个)", expanded=False):
            for o in orphaned:
                st.markdown(f"- **{o['filename']}** ({o['chunks']} 个chunk残留)")
            if st.button("🧹 清理孤儿索引", key="cleanup_btn", type="primary"):
                try:
                    r = requests.post(f"{API_BASE}/documents/cleanup", timeout=60)
                    if r.status_code == 200:
                        result = r.json().get("data", {})
                        st.success(f"✅ 清理完成: 删除 {result.get('orphaned_files_found', 0)} 个文件, "
                                   f"{result.get('chroma_chunks_deleted', 0)} 个Chroma chunk, "
                                   f"{result.get('bm25_chunks_deleted', 0)} 个BM25 chunk")
                        current_sid = st.session_state.session_id or ""
                        st.components.v1.html(
                            f'''
                            <script>
                                setTimeout(() => {{
                                    const currentUrl = new URL(window.parent.location.href);
                                    {f"currentUrl.searchParams.set('sid', '{current_sid}');" if current_sid else "currentUrl.searchParams.delete('sid');"}
                                    window.parent.location.href = currentUrl.toString();
                                }}, 1000);
                            </script>
                            ''',
                            height=0,
                            width=0
                        )
                    else:
                        st.error(f"清理失败: {r.text}")
                except Exception as e:
                    st.error(f"清理失败: {str(e)}")
    
    if docs:
        # 按项目分组
        docs_by_project = {}
        unindexed_count = 0
        for d in docs:
            proj = d.get("project", "未分类")
            if proj not in docs_by_project:
                docs_by_project[proj] = []
            is_indexed = d.get("indexed", True)
            if not is_indexed:
                unindexed_count += 1
            docs_by_project[proj].append({"filename": d["filename"], "indexed": is_indexed})

        total = len(docs)
        if unindexed_count > 0:
            st.caption(f"共 {total} 个文档，{len(docs_by_project)} 个项目  |  ⚠️ {unindexed_count} 个未索引")
            if st.button("🔄 重新索引未索引的文档", key="reindex_btn"):
                try:
                    params = {}
                    if st.session_state.selected_project:
                        params["project"] = st.session_state.selected_project
                    r = requests.post(f"{API_BASE}/documents/reindex", params=params, timeout=120)
                    if r.status_code == 200:
                        result = r.json().get("data", {})
                        st.success(f"✅ 重新索引完成: 成功 {result.get('success', 0)} 个, 共 {result.get('total_chunks', 0)} 块")
                        current_sid = st.session_state.session_id or ""
                        st.components.v1.html(
                            f'''
                            <script>
                                setTimeout(() => {{
                                    const currentUrl = new URL(window.parent.location.href);
                                    {f"currentUrl.searchParams.set('sid', '{current_sid}');" if current_sid else "currentUrl.searchParams.delete('sid');"}
                                    window.parent.location.href = currentUrl.toString();
                                }}, 1000);
                            </script>
                            ''',
                            height=0,
                            width=0
                        )
                    else:
                        st.error(f"重新索引失败: {r.text}")
                except Exception as e:
                    st.error(f"重新索引失败: {str(e)}")
        else:
            st.caption(f"共 {total} 个文档，{len(docs_by_project)} 个项目  | ✅ 全部已索引")

        # 按项目分类展示
        for proj, finfos in docs_by_project.items():
            indexed_fnames = [f for f in finfos if f["indexed"]]
            unindexed_fnames = [f for f in finfos if not f["indexed"]]
            label = f"📁 {proj} ({len(finfos)} 个文档"
            if unindexed_fnames:
                label += f", ⚠️ {len(unindexed_fnames)} 个未索引"
            label += ")"
            with st.expander(label, expanded=True):
                for finfo in finfos:
                    fname = finfo["filename"]
                    is_indexed = finfo["indexed"]
                    col_doc, col_del = st.columns([4, 1])
                    with col_doc:
                        if not is_indexed:
                            st.markdown(f"⚠️ **{fname}** <span style='color:#e53935;font-size:0.85em'>未索引</span>", unsafe_allow_html=True)
                        else:
                            st.text(fname)
                    with col_del:
                        if st.button("🗑", key=f"del_{proj}_{fname}"):
                            try:
                                params = {}
                                if proj and proj != "未分类":
                                    params["project"] = proj
                                r = requests.delete(f"{API_BASE}/documents/{fname}", params=params, timeout=10)
                                if r.status_code == 200:
                                    st.success(f"已删除: {fname}")
                                    current_sid = st.session_state.session_id or ""
                                    st.components.v1.html(
                                        f'''
                                        <script>
                                            setTimeout(() => {{
                                                const currentUrl = new URL(window.parent.location.href);
                                                {f"currentUrl.searchParams.set('sid', '{current_sid}');" if current_sid else "currentUrl.searchParams.delete('sid');"}
                                                window.parent.location.href = currentUrl.toString();
                                            }}, 800);
                                        </script>
                                        ''',
                                        height=0,
                                        width=0
                                    )
                                else:
                                    detail = r.json().get("detail", r.text)
                                    st.error(f"删除失败: {detail}")
                            except Exception as e:
                                st.error(f"删除失败: {str(e)}")
    else:
        st.text("暂无文档")

    st.divider()

    # ---------- 删除项目 ----------
    if st.session_state.selected_project and st.session_state.selected_project != "general":
        if st.button(f"⚠️ 删除项目 '{st.session_state.selected_project}'", type="secondary", key="del_proj_btn"):
            try:
                r = requests.delete(f"{API_BASE}/documents/project/{st.session_state.selected_project}", timeout=10)
                if r.status_code == 200:
                    st.success(f"项目已删除")
                    st.session_state.selected_project = ""
                    current_sid = st.session_state.session_id or ""
                    st.components.v1.html(
                        f'''
                        <script>
                            setTimeout(() => {{
                                const currentUrl = new URL(window.parent.location.href);
                                {f"currentUrl.searchParams.set('sid', '{current_sid}');" if current_sid else "currentUrl.searchParams.delete('sid');"}
                                window.parent.location.href = currentUrl.toString();
                            }}, 800);
                        </script>
                        ''',
                        height=0,
                        width=0
                    )
                else:
                    detail = r.json().get("detail", "")
                    st.error(f"删除失败: {detail}")
            except Exception as e:
                st.error(f"删除失败: {str(e)}")


# ============ 聊天区域 ============
st.divider()
st.header("💬 智能问答")
if st.session_state.selected_project:
    st.info(f"📌 当前检索范围: **{st.session_state.selected_project}**")

# 欢迎卡片（无对话时显示）
if not st.session_state.messages:
    st.markdown("""
    <div class="welcome-card">
        <h2>👋 你好！我是技术文档问答助手</h2>
        <p>我可以帮你检索项目文档、回答技术问题</p>
        <p>试试问我：<em>"项目A的数据库配置是什么？"</em> 或 <em>某个项目的"README.md 里讲了什么？"</em></p>
    </div>
    """, unsafe_allow_html=True)

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("请输入你的问题..."):
    # 延迟创建会话：首次发消息时才创建
    if not st.session_state.session_id:
        sid = create_session()
        if sid:
            st.session_state.session_id = sid

    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full = ""
        error_msg = ""
        try:
            # 构建请求参数
            request_data = {
                "message": prompt,
                "session_id": st.session_state.session_id
            }
            if st.session_state.selected_project:
                request_data["project"] = st.session_state.selected_project

            r = requests.post(f"{API_BASE}/chat/stream",
                json=request_data,
                stream=True, timeout=120)
            for line in r.iter_lines():
                if line and line.decode("utf-8").startswith("data: "):
                    data = json.loads(line.decode("utf-8")[6:])
                    if data["type"] == "token":
                        full += data["content"]
                        placeholder.markdown(full + "▌")
                    elif data["type"] == "tool_call":
                        placeholder.markdown(f"<span class='tool-status'>� {data['content']}...</span>", unsafe_allow_html=True)
                    elif data["type"] == "error":
                        error_msg = data["content"]
            if error_msg:
                placeholder.error(f"后端处理出错: {error_msg}")
            else:
                placeholder.markdown(full)
        except requests.exceptions.ConnectionError:
            st.error("无法连接后端，请启动 FastAPI")
        except Exception as e:
            st.error(f"请求出错: {str(e)}")
    if full and not error_msg:
        st.session_state.messages.append({"role": "assistant", "content": full})
