import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import io
import base64
import glob
import os
import random
import streamlit.components.v1 as components
from streamlit_pdf_viewer import pdf_viewer

# --- 設定 ---
st.set_page_config(page_title="単語テストアプリ", layout="wide")
DATA_DIR = "単語data"

# --- フォント設定 ---
try:
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
    JP_FONT_NAME = 'HeiseiMin-W3' # 明朝体
    
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    JP_FONT_GOTHIC = 'HeiseiKakuGo-W5' # ゴシック体
except:
    JP_FONT_NAME = 'Helvetica'
    JP_FONT_GOTHIC = 'Helvetica-Bold'

EN_FONT_NAME = 'Times-Roman'

# --- ユーティリティ関数 ---
def guess_pos(text):
    text = str(text).strip()
    if "～" in text or text.endswith("する") or text.endswith("る"):
        return "verb_like"
    elif text.endswith("い") or text.endswith("な") or text.endswith("の"):
        return "adj_like"
    elif text.endswith("に") and len(text) > 1:
        return "adv_like"
    else:
        return "noun_like"

def draw_text_fitted(c, text, x, y, max_width, font_name, max_size, min_size=6):
    """枠に合わせて文字サイズを自動縮小して描画（日本語混じり自動対応版）"""
    text = str(text)
    
    if font_name == EN_FONT_NAME:
        if any(ord(char) > 127 for char in text):
            font_name = JP_FONT_NAME 

    current_size = max_size
    try:
        text_width = c.stringWidth(text, font_name, current_size)
        if text_width > max_width:
            ratio = max_width / text_width
            new_size = current_size * ratio
            if new_size < min_size:
                new_size = min_size
            current_size = new_size
    except:
        pass
    c.setFont(font_name, current_size)
    c.drawString(x, y, text)

def get_csv_files():
    if not os.path.exists(DATA_DIR):
        return []
    files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    return files

def load_data(filepath):
    try:
        df = pd.read_csv(filepath)
        required_cols = {'id', 'english', 'japanese'}
        if not required_cols.issubset(df.columns):
            st.error(f"エラー: {os.path.basename(filepath)} に必要な列が含まれていません。")
            return None
        return df
    except Exception as e:
        st.error(f"読み込みエラー: {e}")
        return None

# --- PDF作成関数 ---
def create_pdf(target_data, all_data_df, title, test_type, include_answers=False):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    GRAY_BG = (0.96, 0.96, 0.96)
    
    pos_groups = {"verb_like": [], "adj_like": [], "noun_like": [], "adv_like": []}
    unique_meanings = all_data_df['japanese'].dropna().unique().tolist()
    for m in unique_meanings:
        pos_groups[guess_pos(m)].append(m)

    # レイアウト設定
    margin_x = 5 * mm
    margin_y = 15 * mm
    col_gap = 6 * mm
    cols = 2
    
    if test_type == "記述式":
        rows_per_col = 25
    else:
        rows_per_col = 10
        
    items_per_page = cols * rows_per_col
    header_height = 35 * mm
    body_height = height - (2 * margin_y) - header_height
    row_height = body_height / rows_per_col
    col_width = (width - (2 * margin_x) - col_gap) / 2

    total_pages = (len(target_data) + items_per_page - 1) // items_per_page

    for page in range(total_pages):
        # ヘッダー
        c.setFillColorRGB(0, 0, 0)
        c.setFont(JP_FONT_GOTHIC, 18)
        c.drawCentredString(width / 2, height - margin_y - 8*mm, title)
        
        line_y = height - margin_y - 12*mm
        c.setLineWidth(1.0)
        c.line(margin_x, line_y, width - margin_x, line_y)
        c.setLineWidth(0.3)
        c.line(margin_x, line_y - 1*mm, width - margin_x, line_y - 1*mm)

        c.setFont(JP_FONT_NAME, 10)
        info_y = height - margin_y - 22*mm
        c.drawRightString(width - margin_x - 50*mm, info_y, "日付: ______ / ______   氏名: ______________________")
        
        score_box_w = 40 * mm
        score_box_h = 14 * mm
        score_box_x = width - margin_x - score_box_w
        score_box_y = height - margin_y - 28*mm
        
        c.setLineWidth(1.2)
        c.rect(score_box_x, score_box_y, score_box_w, score_box_h)
        c.setFont(JP_FONT_GOTHIC, 11)
        c.drawString(score_box_x + 2*mm, score_box_y + score_box_h - 5*mm, "SCORE")
        c.setFont(EN_FONT_NAME, 16)
        c.drawRightString(score_box_x + score_box_w - 5*mm, score_box_y + 3*mm, "/       ")

        c.setFont(EN_FONT_NAME, 9)
        c.drawRightString(width - margin_x, 8 * mm, f"- {page + 1} -")

        # 問題描画
        start_y = height - margin_y - header_height
        page_data = target_data[page * items_per_page : (page + 1) * items_per_page]
        
        c.setLineWidth(0.3) 

        for i, item in enumerate(page_data):
            col_idx = i // rows_per_col
            row_idx = i % rows_per_col
            
            x_base = margin_x + col_idx * (col_width + col_gap)
            y_base = start_y - row_idx * row_height
            text_y = y_base - row_height + (row_height / 2)

            if row_idx % 2 == 0:
                c.setFillColorRGB(*GRAY_BG)
                c.rect(x_base, y_base - row_height, col_width, row_height, fill=1, stroke=0)
                c.setFillColorRGB(0, 0, 0)

            if test_type == "記述式":
                w_id = col_width * 0.10
                w_word = col_width * 0.45
                w_ans = col_width * 0.45
                
                c.setDash(1, 2)
                c.setStrokeColorRGB(0.5, 0.5, 0.5)
                c.line(x_base, y_base - row_height, x_base + col_width, y_base - row_height)
                c.setDash([])
                c.setStrokeColorRGB(0, 0, 0)

                c.setFont(JP_FONT_GOTHIC, 9)
                c.drawCentredString(x_base + (w_id / 2), text_y - 2, str(item['id']))
                
                c.setLineWidth(0.3)
                c.line(x_base + w_id, y_base, x_base + w_id, y_base - row_height)
                
                draw_text_fitted(c, str(item['english']), x_base + w_id + 2*mm, text_y - 2, w_word - 4*mm, EN_FONT_NAME, 11)
                
                c.line(x_base + w_id + w_word, y_base, x_base + w_id + w_word, y_base - row_height)
                if include_answers:
                    draw_text_fitted(c, str(item['japanese']), x_base + w_id + w_word + 2*mm, text_y - 2, w_ans - 4*mm, JP_FONT_NAME, 9)

            else:
                c.setLineWidth(0.3)
                c.setStrokeColorRGB(0, 0, 0)
                c.rect(x_base, y_base - row_height, col_width, row_height)
                
                correct_ans = item['japanese']
                target_pos = guess_pos(correct_ans)
                candidates = [cand for cand in pos_groups.get(target_pos, []) if cand != correct_ans]
                
                if len(candidates) < 3:
                    fallback = [m for m in unique_meanings if m != correct_ans]
                    distractors = random.sample(fallback, 3)
                else:
                    random.seed(item['id'])
                    distractors = random.sample(candidates, 3)

                choices = distractors + [correct_ans]
                random.seed(item['id'] + 10000)
                random.shuffle(choices)
                
                correct_num = choices.index(correct_ans) + 1

                line_1_y = y_base - 13
                line_2_y = y_base - 32
                line_3_y = y_base - 48
                
                c.setFont(JP_FONT_GOTHIC, 11)
                id_str = f"{item['id']}."
                c.drawString(x_base + 3*mm, line_1_y, id_str)
                id_width = c.stringWidth(id_str, JP_FONT_GOTHIC, 11)
                
                max_word_width = col_width - 25*mm - id_width 
                
                draw_text_fitted(c, str(item['english']), x_base + 4*mm + id_width, line_1_y, max_word_width, EN_FONT_NAME, 13)
                
                c.setFont(EN_FONT_NAME, 12)
                c.drawRightString(x_base + col_width - 5*mm, line_1_y, "(       )")
                
                if include_answers:
                    c.setFont(JP_FONT_GOTHIC, 11)
                    c.drawCentredString(x_base + col_width - 10*mm, line_1_y, str(correct_num))
                
                c.setFont(JP_FONT_NAME, 9)
                c.setFillColorRGB(0, 0, 0)
                
                def draw_choice(idx, txt, cx, cy):
                    label = f"{idx}. {txt}"
                    if len(label) > 18: label = label[:17] + ".."
                    c.drawString(cx, cy, label)

                draw_choice(1, choices[0], x_base + 5*mm, line_2_y)
                draw_choice(2, choices[1], x_base + (col_width/2) + 2*mm, line_2_y)
                draw_choice(3, choices[2], x_base + 5*mm, line_3_y)
                draw_choice(4, choices[3], x_base + (col_width/2) + 2*mm, line_3_y)

        if page_data:
            c.setLineWidth(1.0)
            c.setStrokeColorRGB(0, 0, 0)
            items_in_col1 = min(rows_per_col, len(page_data))
            h_col1 = items_in_col1 * row_height
            c.rect(margin_x, start_y - h_col1, col_width, h_col1)
            
            if len(page_data) > rows_per_col:
                items_in_col2 = len(page_data) - rows_per_col
                h_col2 = items_in_col2 * row_height
                c.rect(margin_x + col_width + col_gap, start_y - h_col2, col_width, h_col2)

        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer

# --- アプリ画面 ---
st.title("🖨️ 単語テストアプリ")

csv_files_paths = get_csv_files()

if not csv_files_paths:
    st.warning(f"「{DATA_DIR}」フォルダ内にCSVファイルが見つかりません。")
else:
    st.sidebar.header("1. 単語帳・範囲選択")
    files_map = {os.path.basename(p): p for p in csv_files_paths}
    selected_filename = st.sidebar.selectbox("ファイルを選択", list(files_map.keys()))
    selected_filepath = files_map[selected_filename]
    
    df = load_data(selected_filepath)

    if df is not None:
        min_id = int(df['id'].min())
        max_id = int(df['id'].max())
        
        st.sidebar.subheader("出題範囲")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_id = st.number_input("開始ID", min_value=min_id, max_value=max_id, value=min_id)
        with col2:
            end_id_default = min(min_id+49, max_id)
            end_id = st.number_input("終了ID", min_value=min_id, max_value=max_id, value=end_id_default)
        
        # --- 変更箇所(ここから)：出題数の選択を追加 ---
        # 選択された範囲内の実際のデータ数を計算
        temp_target_df = df[(df['id'] >= start_id) & (df['id'] <= end_id)]
        max_questions = len(temp_target_df)
        if max_questions == 0: 
            max_questions = 1 # エラー回避用
            
        st.sidebar.caption(f"選択範囲内の単語数: {len(temp_target_df)}語")
        num_questions = st.sidebar.number_input("出題数", min_value=1, max_value=max_questions, value=max_questions)
        # --- 変更箇所(ここまで) ---

        st.sidebar.markdown("---")
        st.sidebar.header("2. テスト形式")
        test_type = st.sidebar.selectbox("出題形式", ["4択式", "記述式"])
        
        default_title = f"{os.path.splitext(selected_filename)[0]} テスト"
        title_input = st.sidebar.text_input("タイトル", value=default_title)
        
        order_mode = st.sidebar.radio("出題順序", ["順番通り", "ランダム"], horizontal=True)
        
        st.sidebar.markdown("---")
        mode = st.sidebar.radio("出力モード", ["問題用紙", "模範解答"], horizontal=True)
        
        if st.sidebar.button("作成", type="primary"):
            target_df = df[(df['id'] >= start_id) & (df['id'] <= end_id)]
            
            if len(target_df) > 0 and start_id <= end_id:
                # --- 変更箇所(ここから)：出題数による絞り込み ---
                if num_questions < len(target_df):
                    # 範囲内から指定数だけランダムに抽出
                    target_df = target_df.sample(n=num_questions)
                # --- 変更箇所(ここまで) ---

                if order_mode == "ランダム":
                    target_df = target_df.sample(frac=1) # 最終的な並び順をランダムに
                else:
                    target_df = target_df.sort_values('id') # ID順に戻す

                include_answers = (mode == "模範解答")
                final_title = title_input + ("【解答】" if include_answers else "")
                
                pdf_bytes = create_pdf(
                    target_df.to_dict('records'), 
                    df,
                    final_title, 
                    test_type, 
                    include_answers=include_answers
                )
                
                st.success(f"✅ 作成完了！プレビューは印刷ボタンを押して確認してね！")
                pdf_b64 = base64.b64encode(pdf_bytes.getvalue()).decode('utf-8')
                
                js_code = f"""
                <script>
                    function openPdf() {{
                        var binary = atob("{pdf_b64}");
                        var array = [];
                        for (var i = 0; i < binary.length; i++) {{
                            array.push(binary.charCodeAt(i));
                        }}
                        var blob = new Blob([new Uint8Array(array)], {{type: 'application/pdf'}});
                        var url = URL.createObjectURL(blob);
                        window.open(url, '_blank');
                    }}
                </script>
                <div style="text-align: center; margin: 20px 0;">
                    <button onclick="openPdf()" style="
                        background-color: #FF4B4B; color: white; border: none; padding: 12px 24px; 
                        font-size: 18px; font-weight: bold; border-radius: 8px; cursor: pointer;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: background-color 0.3s;
                    ">
                        🖨️ 印刷
                    </button>
                </div>
                """
                components.html(js_code, height=80)
                st.markdown("### 📄 プレビュー")
                pdf_viewer(input=pdf_bytes.getvalue(), width=800)
                
            else:
                st.error("指定された範囲にデータがありません。")
