import streamlit as st
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment
import io
import datetime
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account

# --- 設定（GASのIDをそのまま使用） ---
IDS = {
    "PRACTICE": "19zxiuyYOdNSuWJ2f9k92O90lKP7Ty4euOMTWLigJAuM",
    "STANDARD": "1A4JldliQvJvGv51dEnw_tpkhIkTXZlzRtiyZU7eKgzw",
    "FOLDER_TAKUROKU": "1UxtJsNqonfIJ5UjFzZQLdXikaRMd7XLA",
    "FOLDER_PHRASE": "1wyKwSZpb9qPNld8uTqMQ5q6-g6-UfGm5"
}

# --- Google認証設定 ---
def get_gcp_creds():
    # StreamlitのSecretsから認証情報を読み込む
    creds_info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(creds_info)
    return creds.with_scopes([
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])

# --- データ取得関数 ---
def get_initial_data(creds):
    gc = gspread.authorize(creds)
    # 練習記録スプレッドシート
    p_ss = gc.open_by_key(IDS["PRACTICE"])
    keys = list(filter(None, p_ss.worksheet('key').col_values(1)))
    phrases = list(filter(None, p_ss.worksheet('フレーズ名').col_values(1)))
    # スタンダード曲集
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

# --- アプリ画面構成 ---
st.set_page_config(page_title="まことの宅録スタジオ", layout="centered")
st.title("🎸 まことの宅録スタジオ")

try:
    creds = get_gcp_creds()
    drive_service = build('drive', 'v3', credentials=creds)
    keys, phrases, songs = get_initial_data(creds)

    # ユーザー入力
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

    # 録音
    st.write("録音後にトリミングが可能です")
    audio = mic_recorder(start_prompt="🔴 録音開始", stop_prompt="⏹️ 終了", key='recorder')

    if audio:
        # 録音データの読み込み
        audio_bytes = audio['bytes']
        raw_audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        duration = len(raw_audio) / 1000.0
        
        st.audio(audio_bytes) # プレビュー再生
        
        # トリミングスライダー
        start_t, end_t = st.slider("保存する範囲を選択 (秒)", 0.0, duration, (0.0, duration))
        
        if st.button("✅ Googleドライブへ保存", type="primary"):
            with st.spinner("変換中..."):
                # トリミング
                trimmed = raw_audio[start_t*1000 : end_t*1000]
                
                # ファイル名決定
                prefix = f"{display_name}_{date_val}"
                folder_id = IDS["FOLDER_PHRASE"] if mode == "フレーズ" else IDS["FOLDER_TAKUROKU"]
                serial = get_next_serial(drive_service, folder_id, prefix)
                file_name = f"{prefix}_{serial}.mp3"
                
                # MP3へ変換 (192kbps / 高品質)
                mp3_io = io.BytesIO()
                trimmed.export(mp3_io, format="mp3", bitrate="192k")
                mp3_io.seek(0)
                
                # アップロード
                file_metadata = {'name': file_name, 'parents': [folder_id]}
                media = MediaIoBaseUpload(mp3_io, mimetype='audio/mpeg')
                drive_service.files().create(body=file_metadata, media_body=media).execute()
                
                st.success(f"保存完了: {file_name}")
                st.balloons()

except Exception as e:
    st.info("現在は設定準備中です。Googleの認証設定（Secrets）を完了させると動作します。")
