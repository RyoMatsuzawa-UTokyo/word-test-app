import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import io
import glob
import os
import random
from streamlit_pdf_viewer import pdf_viewer  # 専用ライブラリ

# --- 設定 ---
st.set_page_config(page_title="単語テスト作成機", layout="wide")
DATA_DIR = "単語data"

# --- フォント設定 ---
try:
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
    JP_FONT_NAME = 'HeiseiMin-W3'
except:
    JP_FONT_NAME = 'Helvetica'
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
    text = str(text)
    current_size = max_size
    text_width = c.stringWidth(text, font_name, current_size)
    if text_width > max_width:
        ratio = max_width / text_width
        new_size = current_size * ratio
        if new_size < min_size:
            new_size = min_size
        current_size = new_size
    c.setFont(font_name, current_size)
    c.drawString(x, y, text)

# --- データ読み込み ---
def get_csv_files():
    if not os.path.exists(DATA_DIR):
        return []
    files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    return files

def load_data(filepath):
    try:
        df = pd.read_csv(filepath)
        if not {'id', 'english', 'japanese'}.issubset(df.columns):
            st.error(f"エラー: {os.path.basename(filepath)} の形式が正しくありません。")
            return None
        return df
    except Exception as e:
        st.error(f"読み込みエラー: {e}")
        return None

# --- PDF作成 ---
def create_pdf(target_data, all_data_df, title, score_str, test_type, include_answers=False):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    pos_groups = {"verb_like": [], "adj_like": [], "noun_like": [], "adv_like": []}
    unique_meanings = all_data_df['japanese'].dropna().unique().tolist()
    for m in unique_meanings:
        pos_groups[guess_pos(m)].append(m)

    margin_x = 12 * mm
    margin_y = 15 * mm
    col_gap = 10 * mm
    cols = 2
    
    if test_type == "記述式":
        rows_per_col = 25
    else:
        rows_per_col = 10
        
    items_per_page = cols * rows_per_col
    col_width = (width - (2 * margin_x) - col_gap) / 2
    row_height = (height - (2 * margin_y) - 20*mm) / rows_per_col

    total_pages = (len(target_data) + items_per_page - 1) // items_per_page

    for page in range(total_pages):
        c.setFont(JP_FONT_NAME, 14)
        header_text = f"{title}        {score_str}"
        c.drawCentredString(width / 2, height - margin_y, header_text)
        
        c.setFont(EN_FONT_NAME, 10)
        c.drawRightString(width - margin_x, 10 * mm, f"{page + 1} / {total_pages}")

        start_y = height - margin_y - 15 * mm
        page_data = target_data[page * items_per_page : (page + 1) * items_per_page]
        
        c.setLineWidth(0.5)

        for i, item in enumerate(page_data):
            col_idx = i // rows_per_col
            row_idx = i % rows_per_col
            
            x_base = margin_x + col_idx * (col_width + col_gap)
            y_base = start_y - row_idx * row_height
            text_y = y_base - row_height + (row_height / 2)

            if test_type == "記述式":
                w_id = col_width * 0.10
                w_word = col_width * 0.45
                w_ans = col_width * 0.45
                
                c.rect(x_base, y_base - row_height, w_id, row_height)
                c.rect(x_base + w_id, y_base - row_height, w_word, row_height)
                c.rect(x_base + w_id + w_word, y_base - row_height, w_ans, row_height)
                
                c.setFont(EN_FONT_NAME, 11)
                c.drawCentredString(x_base + (w_id / 2), text_y - 3.5, str(item['id']))
                
                draw_text_fitted(c, str(item['english']), x_base + w_id + 2*mm, text_y - 3.5, w_word - 4*mm, EN_FONT_NAME, 11)
                
                if include_answers:
                    draw_text_fitted(c, str(item['japanese']), x_base + w_id + w_word + 2*mm, text_y - 3.5, w_ans - 4*mm, JP_FONT_NAME, 9)
            
            else:
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
                
                c.setFont(EN_FONT_NAME, 12
