import requests
import streamlit as st
from code_editor import code_editor

CODE_FIELD_HEIGHT = [10, 20]
EXTENSIONS = {
    "py": "python",
    "sql": "sql",
}
state = st.session_state


def default_monitor():
    return {
        "enabled": True,
        "code": "",
        "additional_files": {},
    }


def load_monitors():
    monitors = requests.get("http://localhost:8000/monitor/list").json()
    state.monitors_names = [monitor["name"] for monitor in monitors]


def init_monitor_info(monitor_info):
    state.monitor_enabled = monitor_info["enabled"]
    state.monitor_code = monitor_info["code"]

    additional_files = sorted(
        monitor_info["additional_files"].items(), key=lambda file: file[0]
    )
    state.monitor_additional_files = []
    for file_name, content in additional_files:
        state.monitor_additional_files.append([file_name, content])


def load_monitor_info():
    if "monitor_name" not in state or not state.monitor_name:
        return

    monitor_name = state.monitor_name
    response = requests.get(f"http://localhost:8000/monitor/{monitor_name}")
    if response.status_code == 200:
        monitor_info = response.json()
    else:
        monitor_info = default_monitor()

    init_monitor_info(monitor_info)


def set_new_monitor_name():
    state.new_monitor_name = monitor_name


def create_additional_file_form(i, tab, file_name, file_content):
    with tab:
        col1, col2 = st.columns([99, 1])
        file_extension = file_name.split(".")[-1]
        language = EXTENSIONS.get(file_extension)

        with col1:
            code_response = code_editor(
                file_content,
                lang=language,
                response_mode="blur",
                allow_reset=True,
                height=CODE_FIELD_HEIGHT,
                key=f"widget_content_{file_name}",
            )
            if code_response and code_response["type"] == "blur":
                state.monitor_additional_files[i][1] = code_response["text"]

        with col2:
            st.button(
                "",
                icon=":material/delete:",
                on_click=delete_additional_file,
                key=f"widget_delete_{i}",
                args=(i,),
            )


def delete_additional_file(i):
    state.monitor_additional_files.pop(i)


def add_new_additional_file(new_file_name):
    for file_name, _ in state.monitor_additional_files:
        if file_name == state.widget_additional_file_name:
            return
    state.monitor_additional_files.append([new_file_name, ""])


def create_monitor_form():
    tabs = st.tabs(
        ["Code"] +
        [
            file_name
            for file_name, content in state.monitor_additional_files
        ]
    )
    code_tab = tabs[0]
    additional_files_tabs = tabs[1:]

    with code_tab:
        code_response = code_editor(
            state.monitor_code,
            lang="python",
            response_mode="blur",
            allow_reset=True,
            height=CODE_FIELD_HEIGHT,
            key="widget_monitor_code",
        )
        if code_response and code_response["type"] == "blur":
            state.monitor_code = code_response["text"]

    for i, (file_name, content) in enumerate(state.monitor_additional_files):
        create_additional_file_form(
            i, additional_files_tabs[i], file_name, content
        )


def save_monitor():
    monitor_name = state.monitor_name
    monitor_code = state.monitor_code
    monitor_additional_files = state.monitor_additional_files

    additional_files = {
        file_name: content
        for file_name, content in monitor_additional_files
    }

    monitor_info = {
        "monitor_code": monitor_code,
        "additional_files": additional_files,
    }

    response = requests.post(
        f"http://localhost:8000/monitor/register/{monitor_name}",
        json=monitor_info,
    )
    if response.status_code == 200:
        st.toast("Monitor saved successfully")
    else:
        st.toast(f"Error: {response.text}")


st.set_page_config(page_title="Sentinela", layout="wide")
sidebar = st.sidebar.title("Sentinela")

if not state.get("monitors_names"):
    load_monitors()

if new_monitor_name := state.get("new_monitor_name"):
    # If the new monitor was just created, add it to the list
    if new_monitor_name not in state.monitors_names:
        state.monitors_names.append(state.new_monitor_name)
        state.monitor_name = state.new_monitor_name
        init_monitor_info(default_monitor())

monitor_name = st.sidebar.selectbox(
    "Monitor",
    state.monitors_names,
    index=None,
    placeholder="Choose a monitor",
    key="monitor_name",
    on_change=load_monitor_info,
)

if state.monitor_name:
    st.sidebar.checkbox(
        "Enabled",
        value=state.monitor_enabled,
    )
    with st.sidebar.popover("Create additional file"):
        file_name = st.text_input(
            "File name",
            key="widget_additional_file_name",
        )
        st.button(
            "Create",
            on_click=add_new_additional_file,
            args=(file_name,),
            disabled=not file_name,
        )
    st.sidebar.divider()

    col1, col2 = st.sidebar.columns([1, 1])
    with col2:
        st.button(
            "Save",
            on_click=save_monitor,
            use_container_width=True,
        )

    create_monitor_form()
else:
    with st.sidebar.popover("Create new monitor"):
        monitor_name = st.text_input(
            "Monitor name",
            key="widget_new_monitor_name",
        )
        create_button = st.button(
            "Create",
            on_click=set_new_monitor_name,
            disabled=not monitor_name,
        )
