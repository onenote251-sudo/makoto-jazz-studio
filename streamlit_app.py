import streamlit as st
from pydub import AudioSegment
import io, datetime, requests, base64
import numpy as np
import matplotlib.pyplot as plt

GAS_URL = st.secrets["GAS_URL"]
IDS = {"TAKUROKU": "1UxtJsNqonfIJ5UjFzZQLdXikaRMd7XLA", "PHRASE": "1wyKwSZpb9qPNld8uTqMQ5q6-g6-UfGm5"}

def process_audio(audio_bytes):
    # Python(FFmpeg)で、AIが最も安定して読める「44.1kHz / 192kbps / CBR」に強制変換
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    buf = io.BytesIO()
    audio.export(buf, format="mp3", bitrate="192k", parameters=["-ar", "44100", "-ac", "2", "-codec:a", "libmp3lame"])
    return buf.getvalue()

st.set_page_config(page_title="まことの宅録スタジオ")
st.title("🎸 まことの宅録スタジオ")

mode = st.sidebar.radio("メニュー", ["🔴 即録音", "✂️ 編集：トリミング"])

try:
    init_data = requests.get(f"{GAS_URL}?action=init").json()

    if mode == "🔴 即録音":
        from streamlit_mic_recorder import mic_recorder
        st.subheader("練習を録音（NotebookLM最適化済み）")
        type_choice = st.radio("カテゴリー", ["Song", "フレーズ"], horizontal=True)
        target = st.selectbox("対象", init_data["songs"] if type_choice=="Song" else init_data["phrases"])
        date_str = datetime.date.today().strftime("%Y-%m-%d")
        file_name = f"{target}_{date_str}.mp3"
        f_id = IDS["TAKUROKU"] if type_choice=="Song" else IDS["PHRASE"]

        audio = mic_recorder(start_prompt="🔴 録音開始", stop_prompt="⏹️ 保存", key='rec')
        if audio:
            with st.spinner("AI用に音質を整えています..."):
                clean_audio = process_audio(audio['bytes'])
                b64 = base64.b64encode(clean_audio).decode('utf-8')
                res = requests.post(GAS_URL, json={"folderId": f_id, "fileName": file_name, "fileData": b64, "mode": "record"})
                st.success(f"保存しました。ドライブを確認してください。")

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
            start_t, end_t = st.slider("範囲", 0.0, st.session_state['duration'], (0.0, st.session_state['duration']), step=0.1)
            # 波形描画
            fig, ax = plt.subplots(figsize=(10, 2))
            ax.plot(st.session_state['samples'], color='gray', alpha=0.5)
            ax.axis('off')
            st.pyplot(fig)

            if st.button("✅ この範囲で上書き保存", type="primary"):
                with st.spinner("AI最適化中..."):
                    seg = AudioSegment.from_file(io.BytesIO(st.session_state['edit_bytes']))
                    trimmed = seg[start_t*1000 : end_t*1000]
                    buf = io.BytesIO()
                    trimmed.export(buf, format="mp3", bitrate="192k", parameters=["-ar", "44100", "-ac", "2"])
                    new_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                    requests.post(GAS_URL, json={"folderId": f_id, "fileName": st.session_state['edit_name'], "fileData": new_b64, "mode": "edit"})
                    st.success("上書き完了！")
                    del st.session_state['edit_bytes']

except Exception as e:
    st.error(f"エラー: {e}")
