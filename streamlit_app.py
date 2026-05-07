import streamlit as st
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment
import io, datetime, requests, base64

# --- 設定 ---
GAS_URL = st.secrets["GAS_URL"]
IDS = {
    "TAKUROKU": "1UxtJsNqonfIJ5UjFzZQLdXikaRMd7XLA",
    "PHRASE": "1wyKwSZpb9qPNld8uTqMQ5q6-g6-UfGm5"
}

st.set_page_config(page_title="まことの宅録スタジオ", layout="centered")
st.title("🎸 まことの宅録スタジオ")

# サイドメニュー
mode = st.sidebar.radio("メニュー", ["🔴 練習：即録音", "✂️ 編集：トリミング・上書き"])

try:
    # GAS（受取窓口）からリストを取得
    res = requests.get(GAS_URL).json()
    
    if mode == "🔴 練習：即録音":
        st.subheader("練習をそのまま録音・保存")
        col1, col2 = st.columns(2)
        with col1:
            type_choice = st.radio("カテゴリー", ["Song", "フレーズ"], horizontal=True)
        with col2:
            date_val = st.date_input("日付", datetime.date.today())
        
        if type_choice == "Song":
            target = st.selectbox("曲名を選択", res["songs"])
            file_name = f"{target}_{date_val}.mp3"
            f_id = IDS["TAKUROKU"]
        else:
            key_val = st.selectbox("Key", res["keys"])
            phrase_val = st.selectbox("フレーズ名", res["phrases"])
            file_name = f"{phrase_val}({key_val})_{date_val}.mp3"
            f_id = IDS["PHRASE"]

        st.divider()
        audio = mic_recorder(start_prompt="🔴 録音開始", stop_prompt="⏹️ 終了して保存", key='rec_immed')

        if audio:
            st.audio(audio['bytes'])
            with st.spinner("Googleドライブへ保存中..."):
                b64_data = base64.b64encode(audio['bytes']).decode('utf-8')
                requests.post(GAS_URL, json={"folderId": f_id, "fileName": file_name, "fileData": b64_data})
                st.success(f"保存完了: {file_name}")
                st.balloons()

    else:
        st.subheader("録音済みファイルをトリミング")
        st.info("※録音した後にスライダーで範囲を決めて、上書き保存できます。")
        
        audio_edit = mic_recorder(start_prompt="🔴 編集用録音", stop_prompt="⏹️ 録音終了", key='rec_edit')
        
        if audio_edit:
            raw_audio = AudioSegment.from_file(io.BytesIO(audio_edit['bytes']))
            duration = len(raw_audio) / 1000.0
            st.audio(audio_edit['bytes'])
            
            start_t, end_t = st.slider("保存範囲(秒)", 0.0, duration, (0.0, duration))
            
            st.divider()
            ed_type = st.radio("保存先", ["Song", "フレーズ"], horizontal=True, key="ed_type")
            if ed_type == "Song":
                target_ed = st.selectbox("曲名", res["songs"], key="ed_song")
                file_name_ed = f"{target_ed}_{datetime.date.today()}.mp3"
                f_id_ed = IDS["TAKUROKU"]
            else:
                target_ed = st.selectbox("フレーズ", res["phrases"], key="ed_phrase")
                file_name_ed = f"{target_ed}_{datetime.date.today()}.mp3"
                f_id_ed = IDS["PHRASE"]

            if st.button("✅ この範囲で上書き/保存", type="primary"):
                with st.spinner("高品質MP3に変換中..."):
                    trimmed = raw_audio[start_t*1000 : end_t*1000]
                    buf = io.BytesIO()
                    trimmed.export(buf, format="mp3", bitrate="192k")
                    b64_data_ed = base64.b64encode(buf.getvalue()).decode('utf-8')
                    requests.post(GAS_URL, json={"folderId": f_id_ed, "fileName": file_name_ed, "fileData": b64_data_ed})
                    st.success(f"更新完了: {file_name_ed}")

except Exception as e:
    st.error(f"システム接続エラー: {e}")
