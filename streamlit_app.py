import streamlit as st
from pydub import AudioSegment
import io, datetime, requests, base64
import numpy as np
import matplotlib.pyplot as plt

GAS_URL = st.secrets["GAS_URL"]
IDS = {"TAKUROKU": "1UxtJsNqonfIJ5UjFzZQLdXikaRMd7XLA", "PHRASE": "1wyKwSZpb9qPNld8uTqMQ5q6-g6-UfGm5"}

# --- NotebookLM対策：標準的なMP3に強制整形する関数 ---
def fix_audio_for_notebooklm(audio_bytes):
    # いったん読み込んで、標準規格（44.1kHz / 192kbps）で書き出し直す
    seg = AudioSegment.from_file(io.BytesIO(audio_bytes))
    buf = io.BytesIO()
    seg.export(buf, format="mp3", bitrate="192k", parameters=["-ar", "44100", "-ac", "2"])
    return buf.getvalue()

st.set_page_config(page_title="まことの宅録スタジオ")
st.title("🎸 まことの宅録スタジオ")

mode = st.sidebar.radio("メニュー", ["🔴 即録音", "✂️ 編集：トリミング"])

try:
    init_data = requests.get(f"{GAS_URL}?action=init").json()

    if mode == "🔴 即録音":
        from streamlit_mic_recorder import mic_recorder
        st.subheader("練習を録音（AI最適化済み）")
        type_choice = st.radio("カテゴリー", ["Song", "フレーズ"], horizontal=True)
        target = st.selectbox("対象", init_data["songs"] if type_choice=="Song" else init_data["phrases"])
        file_name = f"{target}_{datetime.date.today()}.mp3"
        f_id = IDS["TAKUROKU"] if type_choice=="Song" else IDS["PHRASE"]

        audio = mic_recorder(start_prompt="🔴 録音開始", stop_prompt="⏹️ 保存", key='rec')
        if audio:
            with st.spinner("NotebookLM用に変換中..."):
                # ここで「AI用整形」を実行
                clean_audio = fix_audio_for_notebooklm(audio['bytes'])
                b64 = base64.b64encode(clean_audio).decode('utf-8')
                requests.post(GAS_URL, json={"folderId": f_id, "fileName": file_name, "fileData": b64, "mode": "record"})
                st.success("保存完了！自動で通番を振りました。")

    else:
        st.subheader("✂️ 範囲を選んで上書き")
        edit_folder = st.radio("フォルダ", ["02_宅録", "03_フレーズ"], horizontal=True)
        f_id = IDS["TAKUROKU"] if edit_folder=="02_宅録" else IDS["PHRASE"]
        
        file_list = requests.get(f"{GAS_URL}?action=list&folderId={f_id}").json()
        selected_file = st.selectbox("ファイル", file_list, format_func=lambda x: x['name'])
        
        if st.button("読み込む"):
            b64_res = requests.get(f"{GAS_URL}?action=download&fileId={selected_file['id']}").text
            st.session_state['edit_bytes'] = base64.b64decode(b64_res)
            st.session_state['edit_name'] = selected_file['name']
            seg = AudioSegment.from_file(io.BytesIO(st.session_state['edit_bytes']))
            st.session_state['samples'] = np.array(seg.get_array_of_samples())[::seg.channels]
            st.session_state['duration'] = len(seg) / 1000.0

        if 'edit_bytes' in st.session_state:
            dur = st.session_state['duration']
            start_t, end_t = st.slider("範囲(秒)", 0.0, dur, (0.0, dur), step=0.1)
            
            # 波形表示（略）
            fig, ax = plt.subplots(figsize=(10, 2))
            ax.plot(st.session_state['samples'], color='gray', alpha=0.5, linewidth=0.5)
            s_idx = int((start_t / dur) * len(st.session_state['samples']))
            e_idx = int((end_t / dur) * len(st.session_state['samples']))
            ax.plot(np.arange(s_idx, e_idx), st.session_state['samples'][s_idx:e_idx], color='red')
            ax.axis('off')
            st.pyplot(fig)

            if st.button("✅ この範囲で上書き保存", type="primary"):
                with st.spinner("AI用に最適化して上書き中..."):
                    seg = AudioSegment.from_file(io.BytesIO(st.session_state['edit_bytes']))
                    trimmed = seg[start_t*1000 : end_t*1000]
                    # 上書き時も「AI用整形」を実行
                    buf = io.BytesIO()
                    trimmed.export(buf, format="mp3", bitrate="192k", parameters=["-ar", "44100", "-ac", "2"])
                    
                    new_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                    requests.post(GAS_URL, json={"folderId": f_id, "fileName": st.session_state['edit_name'], "fileData": new_b64, "mode": "edit"})
                    st.success("NotebookLM対応形式で上書きしました！")
                    del st.session_state['edit_bytes']

except Exception as e:
    st.error(f"エラー: {e}")
