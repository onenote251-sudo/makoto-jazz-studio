import streamlit as st
from pydub import AudioSegment
import io, datetime, requests, base64
import numpy as np
import matplotlib.pyplot as plt

GAS_URL = st.secrets["GAS_URL"]
IDS = {"TAKUROKU": "1UxtJsNqonfIJ5UjFzZQLdXikaRMd7XLA", "PHRASE": "1wyKwSZpb9qPNld8uTqMQ5q6-g6-UfGm5"}

st.set_page_config(page_title="まことの宅録スタジオ")
st.title("🎸 まことの宅録スタジオ")

mode = st.sidebar.radio("メニュー", ["🔴 即録音", "✂️ 編集：トリミング"])

try:
    init_data = requests.get(f"{GAS_URL}?action=init").json()

    if mode == "🔴 即録音":
        from streamlit_mic_recorder import mic_recorder
        st.subheader("練習をそのまま録音・保存")
        type_choice = st.radio("カテゴリー", ["Song", "フレーズ"], horizontal=True)
        target = st.selectbox("対象を選択", init_data["songs"] if type_choice=="Song" else init_data["phrases"])
        file_name = f"{target}_{datetime.date.today()}.mp3"
        f_id = IDS["TAKUROKU"] if type_choice=="Song" else IDS["PHRASE"]

        audio = mic_recorder(start_prompt="🔴 録音開始", stop_prompt="⏹️ 保存", key='rec')
        if audio:
            with st.spinner("保存中..."):
                b64 = base64.b64encode(audio['bytes']).decode('utf-8')
                requests.post(GAS_URL, json={"folderId": f_id, "fileName": file_name, "fileData": b64})
                st.success(f"保存完了: {file_name}")
    
    else:
        st.subheader("✂️ 波形を見ながらトリミング")
        edit_folder = st.radio("フォルダを選択", ["02_宅録", "03_フレーズ"], horizontal=True)
        f_id = IDS["TAKUROKU"] if edit_folder=="02_宅録" else IDS["PHRASE"]
        
        # ファイルリスト取得
        file_list = requests.get(f"{GAS_URL}?action=list&folderId={f_id}").json()
        selected_file = st.selectbox("ファイルを選択", file_list, format_func=lambda x: x['name'])
        
        if st.button("ファイルを読み込む"):
            with st.spinner("音声をダウンロード中..."):
                b64_res = requests.get(f"{GAS_URL}?action=download&fileId={selected_file['id']}").text
                audio_bytes = base64.b64decode(b64_res)
                # 記憶
                st.session_state['edit_bytes'] = audio_bytes
                st.session_state['edit_name'] = selected_file['name']
                # 解析
                seg = AudioSegment.from_file(io.BytesIO(audio_bytes))
                st.session_state['duration'] = len(seg) / 1000.0
                samples = np.array(seg.get_array_of_samples())
                if seg.channels == 2: samples = samples[::2]
                st.session_state['samples'] = samples

        if 'edit_bytes' in st.session_state:
            # スライダー
            dur = st.session_state['duration']
            start_t, end_t = st.slider("範囲指定 (秒)", 0.0, dur, (0.0, dur), step=0.1)

            # --- 波形描画（選択範囲をハイライト） ---
            fig, ax = plt.subplots(figsize=(10, 3))
            ax.plot(st.session_state['samples'], color='gray', alpha=0.5, linewidth=0.5)
            # 選択範囲だけ色を変える
            s_idx = int((start_t / dur) * len(st.session_state['samples']))
            e_idx = int((end_t / dur) * len(st.session_state['samples']))
            ax.plot(np.arange(s_idx, e_idx), st.session_state['samples'][s_idx:e_idx], color='red', linewidth=0.8)
            ax.set_title(f"Selected: {start_t}s - {end_t}s")
            ax.axis('off')
            st.pyplot(fig)

            # 音声プレイヤー（安定再生のため format 指定）
            st.audio(st.session_state['edit_bytes'], format="audio/mp3")

            if st.button("✅ この範囲で上書き保存", type="primary"):
                with st.spinner("更新中..."):
                    seg = AudioSegment.from_file(io.BytesIO(st.session_state['edit_bytes']))
                    trimmed = seg[start_t*1000 : end_t*1000]
                    buf = io.BytesIO()
                    trimmed.export(buf, format="mp3", bitrate="192k")
                    new_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                    requests.post(GAS_URL, json={"folderId": f_id, "fileName": st.session_state['edit_name'], "fileData": new_b64})
                    st.success("上書き完了！")
                    del st.session_state['edit_bytes']

except Exception as e:
    st.error(f"エラー: {e}")
