import streamlit as st
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment
import io
import datetime
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account

# --- 設定 ---
IDS = {
    "PRACTICE": "19zxiuyYOdNSuWJ2f9k92O90lKP7Ty4euOMTWLigJAuM",
    "STANDARD": "1A4JldliQvJvGv51dEnw_tpkhIkTXZlzRtiyZU7eKgzw",
    "FOLDER_TAKUROKU": "1UxtJsNqonfIJ5UjFzZQLdXikaRMd7XLA",
    "FOLDER_PHRASE": "1wyKwSZpb9qPNld8uTqMQ5q6-g6-UfGm5"
}

def get_gcp_creds():
    creds_info = st.secrets["gcp_service_account"]
    # 秘密鍵の改行コードを正しく処理する
    if "private_key" in creds_info:
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(creds_info)
    return creds.with_scopes([
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])

def get_initial_data(creds):
    gc = gspread.authorize(creds)
    p_ss = gc.open_by_key(IDS["PRACTICE"])
    keys = list(filter(None, p_ss.worksheet('key').col_values(1)))
    phrases = list(filter(None, p_ss.worksheet('フレーズ名').col_values(1)))
    s_ss = gc.open_by_key(IDS["STANDARD"])
    songs = list(filter(None, s_ss.get_worksheet(0).col_values(1)))
    return keys, phrases, songs

def get_next_serial(drive_service, folder_id, prefix):
    query = f"'{folder_id}' in parents and name starts with '{prefix}' and trashed = false"
    results = drive_service.files().list(q=query, fields="files(name)").execute()
    files = results.get('files', [])
    max_num = 0
    for f in files:
        name = f['name'].rsplit('.', 1)[0]
        try:
            num = int(name.split('_')[-1])
            if num > max_num: max_num = num
        except: continue
    return f"{max_num + 1:02}"

st.set_page_config(page_title="まことの宅録スタジオ", layout="centered")
st.title("🎸 まことの宅録スタジオ")

# 診断用：エラーの詳細を表示するように変更
try:
    creds = get_gcp_creds()
    drive_service = build('drive', 'v3', credentials=creds)
    keys, phrases, songs = get_initial_data(creds)

    date_val = st.date_input("日付", datetime.date.today())
    mode = st.radio("タイプ", ["フレーズ", "Song"], horizontal=True)

    if mode == "フレーズ":
        col1, col2 = st.columns(2)
        with col1: key_val = st.selectbox("Key", keys)
        with col2: phrase_val = st.selectbox("フレーズ名", phrases)
        display_name = f"{phrase_val}({key_val})"
    else:
        song_val = st.selectbox("Song名", songs)
        display_name = song_val

    st.divider()
    audio = mic_recorder(start_prompt="🔴 録音開始", stop_prompt="⏹️ 終了", key='recorder')

    if audio:
        audio_bytes = audio['bytes']
        raw_audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        duration = len(raw_audio) / 1000.0
        st.audio(audio_bytes)
        start_t, end_t = st.slider("保存範囲(秒)", 0.0, duration, (0.0, duration))
        
        if st.button("✅ Googleドライブへ保存", type="primary"):
            with st.spinner("MP3変換中..."):
                trimmed = raw_audio[start_t*1000 : end_t*1000]
                prefix = f"{display_name}_{date_val}"
                folder_id = IDS["FOLDER_PHRASE"] if mode == "フレーズ" else IDS["FOLDER_TAKUROKU"]
                serial = get_next_serial(drive_service, folder_id, prefix)
                file_name = f"{prefix}_{serial}.mp3"
                
                mp3_io = io.BytesIO()
                trimmed.export(mp3_io, format="mp3", bitrate="192k")
                mp3_io.seek(0)
                
                file_metadata = {'name': file_name, 'parents': [folder_id]}
                media = MediaIoBaseUpload(mp3_io, mimetype='audio/mpeg')
                drive_service.files().create(body=file_metadata, media_body=media).execute()
                st.success(f"保存完了: {file_name}")
                st.balloons()

except Exception as e:
    # エラーの正体を隠さず表示する
    st.error(f"エラーが発生しました: {e}")
    st.info("スプレッドシートやフォルダの共有設定、またはSecretsの形式を確認してください。")
