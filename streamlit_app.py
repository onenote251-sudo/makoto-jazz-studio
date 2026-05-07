import streamlit as st
from pydub import AudioSegment
import io, datetime, requests, base64
import numpy as np
import matplotlib.pyplot as plt

# --- 設定 ---
GAS_URL = st.secrets["GAS_URL"]
IDS = {"TAKUROKU": "1UxtJsNqonfIJ5UjFzZQLdXikaRMd7XLA", "PHRASE": "1wyKwSZpb9qPNld8uTqMQ5q6-g6-UfGm5"}

def finalize_audio(audio_bytes):
    """
    NotebookLMが100%読み取れる『真の標準MP3』に強制変換する
    ※GASだけでは不可能な『データの再構築』をここで行います
    """
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    audio = audio.set_channels(1)  # モノラル化（AI解析に最適）
    audio = audio.set_frame_rate(44100) # 44.1kHz（CD規格）
    buf = io.BytesIO()
    # メタデータを一切含まず、固定ビットレートで書き出し
    audio.export(
        buf, 
        format="mp3", 
        bitrate="128k", 
        parameters=["-codec:a", "libmp3lame", "-write_xing", "0", "-id3v2_version", "0"]
    )
    return buf.getvalue()

st.set_page_config(page_title="まことの宅録スタジオ")
st.title("🎸 まことの宅録スタジオ")

mode = st.sidebar.radio("メニュー", ["🔴 即録音", "✂️ 編集：トリミング"])

try:
    init_data = requests.get(f"{GAS_URL}?action=init").json()

    # --- 録音モード ---
    if mode == "🔴 即録音":
        from streamlit_mic_recorder import mic_recorder
        st.subheader("練習を録音（AI解析用）")
        type_choice = st.radio("カテゴリー", ["Song", "フレーズ"], horizontal=True)
        target = st.selectbox("対象", init_data["songs"] if type_choice=="Song" else init_data["phrases"])
        
        file_name = f"{target}_{datetime.date.today()}.mp3"
        f_id = IDS["TAKUROKU"] if type_choice=="Song" else IDS["PHRASE"]

        audio = mic_recorder(start_prompt="🔴 録音開始", stop_prompt="⏹️ 保存", key='rec')
        
        if audio:
            with st.spinner("AI用にデータを完全に作り直しています..."):
                clean_audio = finalize_audio(audio['bytes'])
                b64 = base64.b64encode(clean_audio).decode('utf-8')
                requests.post(GAS_URL, json={"folderId": f_id, "fileName": file_name, "fileData": b64, "isEdit": False})
                st.success("保存完了！ドライブに新しいファイル（通番付き）を作成しました。")

    # --- 編集（トリミング）モード ---
    else:
        st.subheader("✂️ 範囲を選んで上書き")
        edit_folder = st.radio("フォルダ", ["02_宅録", "03_フレーズ"], horizontal=True)
        f_id = IDS["TAKUROKU"] if edit_folder=="02_宅録" else IDS["PHRASE"]
        
        file_list = requests.get(f"{GAS_URL}?action=list&folderId={f_id}").json()
        selected_file = st.selectbox("ファイルを選択", file_list, format_func=lambda x: x['name'])
        
        if st.button("読み込む"):
            with st.spinner("データを読み込み中..."):
                b64_res = requests.get(f"{GAS_URL}?action=download&fileId={selected_file['id']}").text
                st.session_state['edit_bytes'] = base64.b64decode(b64_res)
                st.session_state['edit_name'] = selected_file['name']
                seg = AudioSegment.from_file(io.BytesIO(st.session_state['edit_bytes']))
                st.session_state['samples'] = np.array(seg.get_array_of_samples())[::seg.channels]
                st.session_state['duration'] = len(seg) / 1000.0

        if 'edit_bytes' in st.session_state:
            dur = st.session_state['duration']
            start_t, end_t = st.slider("範囲 (秒)", 0.0, dur, (0.0, dur), step=0.1)
            
            fig, ax = plt.subplots(figsize=(10, 2))
            ax.plot(st.session_state['samples'], color='gray', alpha=0.5)
            s_idx = int((start_t / dur) * len(st.session_state['samples']))
            e_idx = int((end_t / dur) * len(st.session_state['samples']))
            ax.plot(np.arange(s_idx, e_idx), st.session_state['samples'][s_idx:e_idx], color='red')
            ax.axis('off')
            st.pyplot(fig)

            if st.button("✅ この範囲で上書き保存", type="primary"):
                with st.spinner("データを再構築して上書き中..."):
                    seg = AudioSegment.from_file(io.BytesIO(st.session_state['edit_bytes']))
                    trimmed = seg[start_t*1000 : end_t*1000]
                    buf = io.BytesIO()
                    # 上書き時も NotebookLM 向けに標準化して書き出し
                    trimmed.export(buf, format="mp3", bitrate="128k", 
                                 parameters=["-ar", "44100", "-ac", "1", "-write_xing", "0", "-id3v2_version", "0"])
                    
                    new_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                    requests.post(GAS_URL, json={"folderId": f_id, "fileName": st.session_state['edit_name'], "fileData": new_b64, "isEdit": True})
                    st.success("NotebookLM対応形式で上書きしました！")
                    del st.session_state['edit_bytes']

except Exception as e:
    st.error(f"エラーが発生しました: {e}")
