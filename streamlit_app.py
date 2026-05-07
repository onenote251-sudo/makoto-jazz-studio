import streamlit as st
from pydub import AudioSegment
import io, datetime, requests, base64

# 設定
GAS_URL = st.secrets["GAS_URL"]
IDS = {"TAKUROKU": "1UxtJsNqonfIJ5UjFzZQLdXikaRMd7XLA", "PHRASE": "1wyKwSZpb9qPNld8uTqMQ5q6-g6-UfGm5"}

def fix_for_lm(audio_bytes):
    # FFmpegを使い、LMが拒絶する「VBR」を「CBR(固定)」に完全に焼き直す
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    audio = audio.set_channels(1).set_frame_rate(44100)
    buf = io.BytesIO()
    audio.export(buf, format="mp3", bitrate="128k", parameters=["-write_xing", "0", "-id3v2_version", "0"])
    return buf.getvalue()

st.title("🎸 まことの宅録スタジオ")
mode = st.sidebar.radio("メニュー", ["🔴 即録音", "✂️ 編集"])

try:
    init_data = requests.get(f"{GAS_URL}?action=init").json()

    if mode == "🔴 即録音":
        from streamlit_mic_recorder import mic_recorder
        target = st.selectbox("対象", init_data["songs"] + init_data["phrases"])
        audio = mic_recorder(start_prompt="🔴 録音開始", stop_prompt="⏹️ 保存", key='rec')
        
        if audio:
            with st.spinner("AI用に変換中..."):
                clean_audio = fix_for_lm(audio['bytes'])
                b64 = base64.b64encode(clean_audio).decode('utf-8')
                file_name = f"{target}_{datetime.date.today()}.mp3"
                f_id = IDS["PHRASE"] if target in init_data["phrases"] else IDS["TAKUROKU"]
                requests.post(GAS_URL, json={"folderId": f_id, "fileName": file_name, "fileData": b64, "isEdit": False})
                st.success("保存完了")
    else:
        st.write("編集モードは録音が成功してから調整しましょう")

except Exception as e:
    st.error(f"エラー: {e}")
