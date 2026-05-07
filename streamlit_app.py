import streamlit as st
from pydub import AudioSegment
import io, datetime, requests, base64

GAS_URL = st.secrets["GAS_URL"]
IDS = {"TAKUROKU": "1UxtJsNqonfIJ5UjFzZQLdXikaRMd7XLA", "PHRASE": "1wyKwSZpb9qPNld8uTqMQ5q6-g6-UfGm5"}

st.set_page_config(page_title="まことの宅録スタジオ")
st.title("🎸 まことの宅録スタジオ")

mode = st.sidebar.radio("メニュー", ["🔴 即録音", "✂️ 編集：ファイルを選んで上書き"])

try:
    # 初期データ取得
    init_data = requests.get(f"{GAS_URL}?action=init").json()

    if mode == "🔴 即録音":
        from streamlit_mic_recorder import mic_recorder
        st.subheader("練習をそのまま録音・保存")
        type_choice = st.radio("カテゴリー", ["Song", "フレーズ"], horizontal=True)
        target = st.selectbox("対象", init_data["songs"] if type_choice=="Song" else init_data["phrases"])
        file_name = f"{target}_{datetime.date.today()}.mp3"
        f_id = IDS["TAKUROKU"] if type_choice=="Song" else IDS["PHRASE"]

        audio = mic_recorder(start_prompt="🔴 録音開始", stop_prompt="⏹️ 保存", key='rec')
        if audio:
            b64 = base64.b64encode(audio['bytes']).decode('utf-8')
            requests.post(GAS_URL, json={"folderId": f_id, "fileName": file_name, "fileData": b64})
            st.success(f"保存完了: {file_name}")

    else:
        st.subheader("ドライブのファイルをトリミング")
        # 1. フォルダ選択
        edit_folder = st.radio("フォルダを選択", ["02_宅録", "03_フレーズ"], horizontal=True)
        f_id = IDS["TAKUROKU"] if edit_folder=="02_宅録" else IDS["PHRASE"]
        
        # 2. ファイル一覧取得
        file_list = requests.get(f"{GAS_URL}?action=list&folderId={f_id}").json()
        
        if not file_list:
            st.info("ファイルがありません。")
        else:
            selected_file = st.selectbox("編集するファイルを選択", file_list, format_func=lambda x: x['name'])
            
            if st.button("ファイルを読み込む"):
                with st.spinner("読み込み中..."):
                    b64_res = requests.get(f"{GAS_URL}?action=download&fileId={selected_file['id']}").text
                    st.session_state['edit_bytes'] = base64.b64decode(b64_res)
                    st.session_state['edit_name'] = selected_file['name']

            if 'edit_bytes' in st.session_state:
                st.write(f"編集中のファイル: {st.session_state['edit_name']}")
                audio_data = io.BytesIO(st.session_state['edit_bytes'])
                segment = AudioSegment.from_file(audio_data)
                duration = len(segment) / 1000.0
                
                st.audio(st.session_state['edit_bytes'])
                start_t, end_t = st.slider("保存範囲(秒)", 0.0, duration, (0.0, duration))
                
                if st.button("✅ この範囲で上書き保存", type="primary"):
                    with st.spinner("更新中..."):
                        trimmed = segment[start_t*1000 : end_t*1000]
                        out_buf = io.BytesIO()
                        trimmed.export(out_buf, format="mp3", bitrate="192k")
                        new_b64 = base64.b64encode(out_buf.getvalue()).decode('utf-8')
                        requests.post(GAS_URL, json={"folderId": f_id, "fileName": st.session_state['edit_name'], "fileData": new_b64})
                        st.success("上書きが完了しました！")
                        del st.session_state['edit_bytes'] # 掃除

except Exception as e:
    st.error(f"システムエラー: {e}")
