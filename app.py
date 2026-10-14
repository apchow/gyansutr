import os

import streamlit as st

from database import (
    clear_chat_history,
    get_chat_history,
    get_note,
    get_notes_list,
    init_db,
    save_chat_message,
    save_note,
)
from flashcard_actions import approve_flashcards, cancel_flashcards
from ingest import ingest_file, ingest_note
from personas import PERSONAS, get_persona, persona_by_id
from query import generate_flashcards, get_available_models, query_llm

st.set_page_config(page_title="GyanSutr", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")


@st.cache_data(ttl=60, max_entries=1)
def cached_available_models():
    return get_available_models()


def apply_theme(theme_name: str, accent: str):
    dark = theme_name == "dark"
    page_background = "linear-gradient(180deg, #020817 0%, #0f172a 100%)" if dark else "linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%)"
    surface = "#0f172a" if dark else "#f8fafc"
    input_surface = "#111827" if dark else "#ffffff"
    page_end = "#0f172a" if dark else "#e2e8f0"
    text = "#e2e8f0" if dark else "#0f172a"
    border = "#334155" if dark else "#cbd5e1"
    primary = accent
    color_scheme = "dark" if dark else "light"

    st.markdown(
        f"""
        <style>
        :root {{ color-scheme: {color_scheme}; }}
        .stApp, [data-testid="stAppViewContainer"] {{
            background: {page_background} !important;
            color: {text} !important;
        }}
        [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {{
            background: {surface} !important;
            color: {text} !important;
        }}
        [data-testid="stSidebar"] :not(svg):not(path) {{ color: {text} !important; }}
        [data-testid="stSidebar"] hr {{ border-color: {border} !important; }}
        [data-testid="stSidebar"] code {{
            background-color: {input_surface} !important;
            color: {text} !important;
        }}
        [data-testid="stSelectbox"] [role="group"] {{
            background-color: {input_surface} !important;
            border-color: {border} !important;
        }}
        [data-testid="stSelectbox"] [role="combobox"] {{ background: transparent !important; }}
        .stApp input:not([type="radio"]):not([type="checkbox"]),
        .stApp textarea,
        .stApp [data-baseweb="select"] > div,
        [data-testid="stChatInput"],
        [data-testid="stChatInput"] > div {{
            background-color: {input_surface} !important;
            color: {text} !important;
            border-color: {border} !important;
        }}
        .stApp input::placeholder,
        .stApp textarea::placeholder {{ color: {text} !important; opacity: 0.65; }}
        [data-testid="stChatInput"] textarea {{ background: transparent !important; }}
        [data-testid="stBottom"], [data-testid="stBottomBlockContainer"] {{
            background: {page_end} !important;
        }}
        .stApp button {{
            background-color: {input_surface} !important;
            color: {text} !important;
            border-color: {border} !important;
        }}
        .stApp button svg, .stApp button svg * {{ color: {text} !important; }}
        [data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"],
        [data-testid="stSidebar"] [data-testid="stIconMaterial"] {{ color: {text} !important; }}
        .stApp button[kind="primary"] {{ background: {primary} !important; color: #ffffff !important; }}
        [data-baseweb="popover"], [role="listbox"] {{
            background: {surface} !important;
            color: {text} !important;
            border: 1px solid {border} !important;
        }}
        [role="option"] {{ color: {text} !important; cursor: pointer; pointer-events: auto !important; }}
        [role="option"][aria-selected="true"],
        [role="option"][data-focused="true"],
        [role="option"]:hover {{ background: {input_surface} !important; color: {text} !important; }}
        [data-testid="stHeader"] {{ background: transparent !important; }}
        .block-container {{ padding-top: 2rem; padding-bottom: 2rem; }}
        .stChatMessage {{ border-radius: 12px; padding: 0.75rem 1rem; }}
        [data-testid="stChatMessage"]:has([aria-label="Chat message from assistant"]) {{
            border-left: 4px solid {primary};
        }}
        [data-testid="stChatMessageContent"][aria-label="Chat message from assistant"],
        [data-testid="stChatMessageContent"][aria-label="Chat message from assistant"] * {{
            color: {text} !important;
        }}
        .stTextInput>div>div>input, .stTextArea>div>div>textarea {{ border-radius: 8px; }}
        .stButton>button {{ border-radius: 10px; }}
        .sutr-brand {{ margin: 0.25rem 0 1.25rem; }}
        .brand-name {{
            font-size: 2.35rem;
            line-height: 1.1;
            font-weight: 800;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            background: linear-gradient(135deg, #7dd3fc 0%, #c4b5fd 35%, #f9a8d4 100%);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            text-shadow: 0 0 18px rgba(125, 211, 252, 0.25);
        }}
        .sutr-acronym {{
            margin-top: 0.2rem;
            font-size: 0.9rem;
            font-weight: 800;
            letter-spacing: 0.42em;
            text-transform: uppercase;
            color: #7dd3fc;
        }}
        .sutr-full {{
            margin-top: 0.35rem;
            font-size: 0.72rem;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: rgba(226, 232, 240, 0.8);
        }}
        footer {{ visibility: hidden; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _queue_prompt(text: str):
    st.session_state.queued_prompt = text


# Initialization
os.makedirs("workspace/documents", exist_ok=True)
os.makedirs("vault", exist_ok=True)
init_db()

if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "dark"
if "chat_thread_id" not in st.session_state:
    st.session_state.chat_thread_id = "default"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = get_chat_history(thread_id=st.session_state.chat_thread_id)
if "active_note_id" not in st.session_state:
    st.session_state.active_note_id = None
if "new_note_counter" not in st.session_state:
    st.session_state.new_note_counter = 0
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False
if "files_to_process" not in st.session_state:
    st.session_state.files_to_process = []
if "pending_flashcards" not in st.session_state:
    st.session_state.pending_flashcards = None
if "note_editor_revision" not in st.session_state:
    st.session_state.note_editor_revision = 0
if "active_persona" not in st.session_state:
    st.session_state.active_persona = PERSONAS[0].label
if "queued_prompt" not in st.session_state:
    st.session_state.queued_prompt = None

with st.sidebar:
    st.title("GyanSutr")
    st.caption(f"Local Workspace: `{os.path.abspath('workspace')}`")

    st.divider()
    st.subheader("Appearance")
    st.session_state.theme_mode = st.radio(
        "Theme",
        ["dark", "light"],
        index=0 if st.session_state.theme_mode == "dark" else 1,
        horizontal=True,
    )

    st.subheader("Persona")
    selected_domain = st.segmented_control(
        "Active persona",
        options=[persona.label for persona in PERSONAS],
        key="active_persona",
        required=True,
        format_func=lambda label: f"{get_persona(label).material_icon} {get_persona(label).short_name}",
        disabled=st.session_state.is_processing,
    )
    active_persona = get_persona(selected_domain)
    apply_theme(st.session_state.theme_mode, active_persona.accent)
    st.badge(active_persona.short_name, icon=active_persona.icon, color=active_persona.badge_color)
    st.caption(active_persona.tagline)
    st.caption(f"Cites as {active_persona.citation_example}")

    st.divider()
    nav = st.radio(
        "Navigation",
        ["Ask Assistant", "Document Workspace", "Notes & Flashcards", "System Activity"],
        label_visibility="collapsed",
        disabled=st.session_state.is_processing,
    )

    st.divider()
    st.subheader("Configuration")
    selected_model = st.selectbox("LLM Engine", cached_available_models(), disabled=st.session_state.is_processing)

    st.divider()
    st.subheader("Conversation")
    thread_options = ["default", "study", "research", "project"]
    st.session_state.chat_thread_id = st.selectbox(
        "Thread",
        thread_options,
        index=thread_options.index(st.session_state.chat_thread_id) if st.session_state.chat_thread_id in thread_options else 0,
        help="Separate chat histories by purpose.",
    )
    st.session_state.chat_history = get_chat_history(thread_id=st.session_state.chat_thread_id)

    if st.button("Clear chat history", use_container_width=True):
        clear_chat_history(st.session_state.chat_thread_id)
        st.session_state.chat_history = []
        st.rerun()
    if st.session_state.chat_history:
        for message in st.session_state.chat_history[-6:]:
            if message["role"] == "user":
                label = "You"
            else:
                stored_persona = persona_by_id(message.get("persona"))
                label = stored_persona.short_name if stored_persona else "Assistant"
            preview = message["content"][:60].replace("\n", " ")
            st.caption(f"{label}: {preview}{'...' if len(message['content']) > 60 else ''}")
    else:
        st.caption("No saved conversation yet.")

if nav == "Ask Assistant":
    st.markdown(
        """
        <div class="sutr-brand">
            <div class="brand-name">GyanSutr</div>
            <div class="sutr-acronym">S U T R</div>
            <div class="sutr-full">Sovereign Unified Trusted Retrieval</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.header("Ask your second brain", icon=active_persona.material_icon)
    st.badge(active_persona.short_name, icon=active_persona.icon, color=active_persona.badge_color)
    st.caption(f"{active_persona.tagline} · {st.session_state.chat_thread_id}")
    st.caption(active_persona.answer_shape)
    with st.expander("How this persona responds"):
        st.markdown(active_persona.response_format)
        st.markdown(active_persona.citation_rules)

    if st.session_state.chat_history:
        with st.container(border=True):
            for message in st.session_state.chat_history:
                ts = message.get("timestamp", "")
                if message["role"] == "user":
                    with st.chat_message("user"):
                        st.caption(f"You · {ts}")
                        st.markdown(message["content"])
                else:
                    stored_persona = persona_by_id(message.get("persona"))
                    speaker = stored_persona.short_name if stored_persona else "Assistant"
                    avatar = stored_persona.icon if stored_persona else "🧠"
                    with st.chat_message("assistant", avatar=avatar):
                        st.caption(f"{speaker} · {ts}")
                        st.markdown(message["content"])
                        if message.get("sources"):
                            with st.expander("View evidence citations"):
                                for source in message["sources"]:
                                    st.markdown(f"- {source}")

    st.caption("Suggested prompts")
    for index, suggestion in enumerate(active_persona.suggested_prompts):
        st.button(
            suggestion,
            key=f"suggest_{active_persona.id}_{index}",
            icon=active_persona.material_icon if index == 0 else ":material/chat:",
            help="Same question for both personas." if index == 0 else None,
            on_click=_queue_prompt,
            args=(suggestion,),
            disabled=st.session_state.is_processing,
            width="stretch",
        )

    typed = st.chat_input("Ask your indexed documents and notes...", disabled=st.session_state.is_processing)
    prompt = st.session_state.queued_prompt or typed
    if st.session_state.queued_prompt:
        st.session_state.queued_prompt = None
    if prompt:
        user_message = {"role": "user", "content": prompt, "sources": [], "timestamp": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        st.session_state.chat_history.append(user_message)
        save_chat_message("user", prompt, [], thread_id=st.session_state.chat_thread_id)
        with st.spinner(f"Analyzing via {active_persona.short_name}..."):
            answer, sources, retrieved_chunk_ids = query_llm(prompt, selected_model, selected_domain)
        assistant_message = {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "persona": active_persona.id,
            "timestamp": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        st.session_state.chat_history.append(assistant_message)
        save_chat_message(
            "assistant",
            answer,
            sources,
            thread_id=st.session_state.chat_thread_id,
            persona=active_persona.id,
        )
        st.rerun()

elif nav == "Document Workspace":
    st.header("Document Workspace")

    with st.container(border=True):
        st.markdown("#### Upload & Index")
        st.write("Add standard PDFs, DOCX, TXT, or MD files to your primary retrieval database.")

        uploaded_files = st.file_uploader(
            "Select Files",
            type=["pdf", "txt", "md", "docx"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            disabled=st.session_state.is_processing,
        )

        if uploaded_files and not st.session_state.is_processing:
            if st.button("Process & Index Files", type="primary"):
                for uploaded in uploaded_files:
                    file_path = os.path.join("workspace/documents", uploaded.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded.getbuffer())

                st.session_state.files_to_process = [u.name for u in uploaded_files]
                st.session_state.is_processing = True
                st.rerun()

        if st.session_state.is_processing:
            st.warning("⚠️ Indexing in progress. The navigation menu is locked to prevent data loss.")
            progress_bar = st.progress(0)
            status_text = st.empty()

            files = st.session_state.files_to_process
            total = len(files)

            for idx, filename in enumerate(files):
                try:
                    res = ingest_file(
                        filename,
                        progress_callback=lambda msg, current_idx=idx, current_name=filename: status_text.text(
                            f"⏳ [{current_idx + 1}/{total}] {current_name}: {msg}"
                        ),
                    )
                    if res["status"] == "duplicate":
                        st.toast(f"'{filename}' already indexed (Skipped).", icon="⚠️")
                    else:
                        st.toast(f"'{filename}' indexed ({res['chunks']} chunks).", icon="✅")
                except Exception as e:
                    st.error(f"Error indexing '{filename}': {str(e)}")

                progress_bar.progress((idx + 1) / total)

            status_text.success("✅ Batch indexing complete.")
            st.session_state.is_processing = False
            st.session_state.files_to_process = []

            if st.button("Acknowledge & Unlock Interface", type="primary"):
                st.rerun()

elif nav == "Notes & Flashcards":
    st.header("Knowledge Capture")
    col1, col2 = st.columns([1, 3], gap="large")

    with col1:
        with st.container(border=True):
            st.subheader("Directory")
            if st.button("➕ New Note", use_container_width=True, type="primary"):
                st.session_state.active_note_id = None
                st.session_state.new_note_counter += 1
                st.rerun()
            st.divider()
            for n in get_notes_list():
                if st.button(f"📄 {n['title']}", key=f"n_{n['id']}", use_container_width=True):
                    st.session_state.active_note_id = n["id"]
                    st.rerun()

    with col2:
        with st.container(border=True):
            current = get_note(st.session_state.active_note_id) if st.session_state.active_note_id else None
            editor_key = (
                f"note_{st.session_state.active_note_id}"
                if st.session_state.active_note_id
                else f"new_{st.session_state.new_note_counter}"
            ) + f"_{st.session_state.note_editor_revision}"

            st.subheader("Editor")
            title = st.text_input(
                "Note Title",
                value=current["title"] if current else "",
                placeholder="e.g., Quantum Mechanics Overview",
                key=f"title_{editor_key}",
            )
            content = st.text_area(
                "Content",
                value=current["content"] if current else "",
                height=350,
                placeholder="Draft your insights here...",
                key=f"content_{editor_key}",
            )

            c_save, c_export = st.columns(2)
            with c_save:
                if st.button("💾 Save to Workspace", use_container_width=True):
                    if title and content:
                        nid = save_note(st.session_state.active_note_id, title, content)
                        st.session_state.active_note_id = nid
                        chunks = ingest_note(nid, title, content)
                        st.toast(f"Saved & Vectorized ({chunks} chunks)", icon="✅")
                        st.rerun()
                    else:
                        st.error("Title and content are mandatory.")
            with c_export:
                if st.button("🔗 Push to Obsidian", use_container_width=True):
                    if current:
                        export_path = f"vault/{current['title'].replace(' ', '_')}.md"
                        with open(export_path, "w", encoding="utf-8") as f:
                            f.write(f"# {current['title']}\n\n{current['content']}")
                        st.toast(f"Pushed to {export_path}", icon="✅")

            if st.button("⚡ Generate preview", type="primary"):
                if not st.session_state.active_note_id or not title.strip():
                    st.error("Save this note with a title before generating a preview.")
                else:
                    with st.spinner("Retrieving local sources and drafting cards..."):
                        preview = generate_flashcards(title, selected_model, selected_domain)
                    preview["note_id"] = st.session_state.active_note_id
                    preview["topic"] = title
                    st.session_state.pending_flashcards = preview

            preview = st.session_state.pending_flashcards
            if preview:
                st.divider()
                st.subheader("Flashcard review")
                if preview.get("cards"):
                    for index, card in enumerate(preview["cards"], start=1):
                        with st.container(border=True):
                            st.caption(f"Card {index}")
                            st.text(card.get("front", ""))
                            if card.get("back"):
                                st.text(card["back"])
                            source = card.get("source")
                            if source:
                                location = f"{source.get('filename', 'Indexed Document')} · page {source.get('page') or 'unknown'} · chunk {source.get('chunk_id', 'unknown')}"
                                st.caption(location)
                                st.caption(source.get("excerpt", ""))
                            else:
                                st.caption("No source citation was returned for this card.")
                    st.caption("Sources are retrieved from your local corpus. This is not a fact-check.")
                else:
                    st.warning("The model did not produce parseable cards.")
                    with st.expander("Raw model output"):
                        st.text(preview.get("raw_model_output", ""))

                export_key = f"export_obsidian_{preview['preview_id']}"
                export_obsidian = st.checkbox("Also export to Obsidian", value=False, key=export_key)
                approve_col, cancel_col = st.columns(2)
                with approve_col:
                    if st.button(
                        "✅ Approve & Save",
                        type="primary",
                        key=f"approve_{preview['preview_id']}",
                        disabled=not preview.get("cards"),
                    ):
                        note = get_note(preview.get("note_id"))
                        if not note:
                            st.error("The saved note for this preview no longer exists.")
                        else:
                            try:
                                result = approve_flashcards(
                                    preview,
                                    note["id"],
                                    note["title"],
                                    note["content"],
                                    export_obsidian=export_obsidian,
                                )
                                if result["status"] == "already_resolved":
                                    st.toast("This preview was already resolved.", icon="⚠️")
                                else:
                                    st.session_state.active_note_id = result["note_id"]
                                    st.session_state.note_editor_revision += 1
                                    if result["result"] == "approved":
                                        st.toast("Flashcards approved and saved.", icon="✅")
                                    else:
                                        st.warning(result["result"])
                                st.session_state.pending_flashcards = None
                                st.rerun()
                            except Exception as error:
                                st.error(f"Could not save the approved cards: {error}")
                with cancel_col:
                    if st.button("✖ Cancel", key=f"cancel_{preview['preview_id']}"):
                        result = cancel_flashcards(preview["preview_id"])
                        st.session_state.pending_flashcards = None
                        st.toast("Preview cancelled; no cards were saved.", icon="ℹ️")
                        st.rerun()

elif nav == "System Activity":
    st.header("System Activity")
    with st.container(border=True):
        st.markdown(
            """
            ### Architecture Status
            - **Primary Vector Store:** Active (`./chroma_db`)
            - **Relational DB:** Active (`./workspace/gyansutr.db`)
            - **LLM Engine:** Local Ollama Bindings
            """
        )

    st.subheader("Audit Log")
    with st.container(border=True):
        from receipts import read_queries, read_actions
        queries = read_queries()
        actions = read_actions()

        if not queries and not actions:
            st.caption("No activity yet. Run a query or generate flashcards to see the audit trail.")
        else:
            st.caption(f"{len(queries)} queries · {len(actions)} actions")

            # Merge and sort by timestamp
            all_entries = []
            for q in queries:
                all_entries.append({
                    "Time": q.get("timestamp", ""),
                    "Query": q.get("question", q.get("topic", "")),
                    "Model": q.get("model", ""),
                    "Action": "rag_query",
                    "Status": "success",
                })
            for a in actions:
                all_entries.append({
                    "Time": a.get("timestamp", ""),
                    "Query": a.get("details", a.get("tool", "")),
                    "Model": a.get("model", ""),
                    "Action": a.get("tool", "action"),
                    "Status": a.get("status", ""),
                })

            # Sort by timestamp descending
            all_entries.sort(key=lambda x: x["Time"], reverse=True)

            # Show as a table
            st.dataframe(
                all_entries,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Time": st.column_config.TextColumn("Time", width="medium"),
                    "Query": st.column_config.TextColumn("Query", width="large"),
                    "Model": st.column_config.TextColumn("Model", width="medium"),
                    "Action": st.column_config.TextColumn("Action", width="medium"),
                    "Status": st.column_config.TextColumn("Status", width="small"),
                },
            )
