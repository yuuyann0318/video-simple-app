"""
動画アップ管理（配布用）

フロー:
  1. 初回アクセス → ブラウザの localStorage にランダムIDを自動生成・保存
  2. 以降はURLを開くだけで自分のシートが即表示（名前入力・ブックマーク不要）
  3. データはIDごとに完全分離
"""

import streamlit as st
import streamlit.components.v1 as components
from datetime import date, datetime as dt
from utils.sheets import load_data, add_row, update_status, delete_row

st.set_page_config(
    page_title="動画アップ管理",
    page_icon="🎬",
    layout="centered",
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ユーザー識別：localStorage → session_state
# 同じブラウザで開けば毎回同じシートが自動で表示される
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if "user" in st.query_params and not st.session_state.get("username"):
    st.session_state["username"] = st.query_params["user"]

if not st.session_state.get("username"):
    # localStorage からIDを取得し、URLパラメータ経由でStreamlitに渡す
    # ?user=xxx が付いた状態でリロードされ、上の行で username が確定する
    components.html("""
    <script>
    (function() {
        try {
            var uid = localStorage.getItem('video_uid');
            if (!uid) {
                var c = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
                uid = '';
                for (var i = 0; i < 10; i++) {
                    uid += c[Math.floor(Math.random() * c.length)];
                }
                localStorage.setItem('video_uid', uid);
            }
            var url = new URL(window.parent.location.href);
            if (!url.searchParams.get('user')) {
                url.searchParams.set('user', uid);
                window.parent.location.replace(url.toString());
            }
        } catch(e) { console.error(e); }
    })();
    </script>
    """, height=0)
    st.stop()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メイン画面
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def show_main(username: str):

    # ── スタイル ────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    body, [data-testid="stAppViewContainer"] { background-color: #f4f6fb; }
    [data-testid="stHeader"] { background: transparent; }

    /* ヘッダーバー */
    .top-bar {
        background: linear-gradient(90deg, #1a1a2e, #0f3460);
        color: white;
        border-radius: 16px;
        padding: 16px 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(15,52,96,0.25);
    }
    .top-bar-name {
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .top-bar-sub {
        font-size: 0.78rem;
        opacity: 0.65;
        margin-top: 3px;
    }

    /* フォームカード */
    .form-card {
        background: white;
        border-radius: 18px;
        padding: 24px 28px;
        box-shadow: 0 2px 14px rgba(0,0,0,0.07);
        margin-bottom: 24px;
    }

    /* 動画カード */
    .video-card {
        background: white;
        border-radius: 14px;
        padding: 16px 20px 12px;
        margin-bottom: 10px;
        box-shadow: 0 1px 8px rgba(0,0,0,0.07);
        border-left: 5px solid #667eea;
    }
    .video-card.done    { border-left-color: #22c55e; background: #f0fdf4; }
    .video-card.overdue { border-left-color: #ef4444; background: #fff5f5; }
    .video-card.today   { border-left-color: #f59e0b; background: #fffbeb; }
    .video-card.soon    { border-left-color: #f97316; }

    .v-title { font-size: 1.05rem; font-weight: 700; color: #1a1a2e; margin-bottom: 5px; }
    .v-date  { font-size: 0.87rem; color: #666; margin-bottom: 8px; }

    .badge {
        display: inline-block;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 3px 11px;
        border-radius: 999px;
    }
    .b-pending { background:#ede9fe; color:#5b21b6; }
    .b-done    { background:#dcfce7; color:#166534; }
    .b-overdue { background:#fee2e2; color:#991b1b; }
    .b-today   { background:#fef9c3; color:#92400e; }
    .b-soon    { background:#ffedd5; color:#9a3412; }

    .empty-msg {
        text-align: center;
        color: #c0c4cc;
        padding: 52px 0;
        font-size: 1rem;
        line-height: 1.8;
    }

    /* ボタン */
    div.stButton > button { border-radius: 9px; font-weight: 600; font-size: 0.88rem; }

    /* タブ */
    div[role="tab"] { font-weight: 600; font-size: 0.95rem; }
    </style>
    """, unsafe_allow_html=True)

    # ── ヘッダーバー ────────────────────────────────────────────────────────
    st.markdown("""
    <div class="top-bar">
        <div>
            <div class="top-bar-name">🎬 動画管理シート</div>
            <div class="top-bar-sub">このデバイス専用のシートです</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 追加フォーム ────────────────────────────────────────────────────────
    st.markdown("#### ➕ 動画を追加する")

    with st.form("add_form", clear_on_submit=True):
        title_input = st.text_input(
            "動画タイトル",
            placeholder="例：〇〇チャンネル向け商品紹介",
        )
        date_input = st.date_input(
            "アップ予定日",
            value=date.today(),
            format="YYYY/MM/DD",
        )
        submitted = st.form_submit_button(
            "✅ 追加する",
            use_container_width=True,
            type="primary",
        )
        if submitted:
            if not title_input.strip():
                st.warning("タイトルを入力してください")
            else:
                add_row(username, {
                    "タイトル":   title_input.strip(),
                    "投稿予定日": date_input.strftime("%Y/%m/%d"),
                    "ステータス": "未投稿",
                })
                st.success(f"「{title_input.strip()}」を追加しました！")
                st.rerun()

    st.divider()

    # ── 動画一覧 ────────────────────────────────────────────────────────────
    st.markdown("#### 📋 動画一覧")

    df = load_data(username)
    today = date.today()

    def classify(row) -> dict:
        """1行分の表示情報（カードクラス・バッジ・日付ラベル）を返す。"""
        d_str  = row.get("投稿予定日", "")
        status = row.get("ステータス", "未投稿")
        is_done = (status == "投稿済み")

        try:
            d_obj = dt.strptime(d_str, "%Y/%m/%d").date()
            diff  = (d_obj - today).days
        except Exception:
            d_obj, diff = None, None

        if is_done:
            return dict(
                card="video-card done",
                badge_cls="b-done", badge="✅ 投稿済み",
                date_label=f"📅 {d_str}",
                is_done=True,
            )
        if diff is None:
            return dict(
                card="video-card",
                badge_cls="b-pending", badge="⏳ 未投稿",
                date_label=f"📅 {d_str}",
                is_done=False,
            )
        if diff < 0:
            return dict(
                card="video-card overdue",
                badge_cls="b-overdue", badge=f"🔴 {abs(diff)}日超過",
                date_label=f"⚠️ {d_str}（{abs(diff)}日超過）",
                is_done=False,
            )
        if diff == 0:
            return dict(
                card="video-card today",
                badge_cls="b-today", badge="🔥 今日！",
                date_label=f"🔥 {d_str}（今日！）",
                is_done=False,
            )
        if diff <= 3:
            return dict(
                card="video-card soon",
                badge_cls="b-soon", badge=f"⏰ あと{diff}日",
                date_label=f"⏰ {d_str}（あと{diff}日）",
                is_done=False,
            )
        return dict(
            card="video-card",
            badge_cls="b-pending", badge=f"⏳ あと{diff}日",
            date_label=f"📅 {d_str}（あと{diff}日）",
            is_done=False,
        )

    def render_card(row, prefix: str):
        """動画カードを1枚描画する。prefix でタブごとにキーを分離する。"""
        row_id = row.get("ID", "")
        title  = row.get("タイトル", "—")
        info   = classify(row)

        st.markdown(f"""
        <div class="{info['card']}">
            <div class="v-title">{title}</div>
            <div class="v-date">{info['date_label']}</div>
            <span class="badge {info['badge_cls']}">{info['badge']}</span>
        </div>
        """, unsafe_allow_html=True)

        c1, c2 = st.columns([2, 1])
        with c1:
            if not info["is_done"]:
                if st.button("✅ 投稿済みにする", key=f"{prefix}_done_{row_id}",
                             use_container_width=True, type="primary"):
                    update_status(username, row_id, "投稿済み")
                    st.rerun()
            else:
                if st.button("↩ 未投稿に戻す", key=f"{prefix}_undo_{row_id}",
                             use_container_width=True):
                    update_status(username, row_id, "未投稿")
                    st.rerun()
        with c2:
            if st.button("🗑 削除", key=f"{prefix}_del_{row_id}", use_container_width=True):
                delete_row(username, row_id)
                st.rerun()

    def render_list(target_df, prefix: str):
        if target_df.empty:
            st.markdown(
                '<div class="empty-msg">該当する動画はありません</div>',
                unsafe_allow_html=True,
            )
            return
        for _, row in target_df.iterrows():
            render_card(row, prefix)

    if df.empty:
        st.markdown(
            '<div class="empty-msg">まだ動画が登録されていません<br>'
            '<small style="color:#ccc">上のフォームから追加してみましょう</small></div>',
            unsafe_allow_html=True,
        )
        return

    # 日付昇順ソート（期限が近い順）
    df_sorted = df.sort_values("投稿予定日", ascending=True).reset_index(drop=True)
    pending   = df_sorted[df_sorted["ステータス"] != "投稿済み"].reset_index(drop=True)
    done      = df_sorted[df_sorted["ステータス"] == "投稿済み"].reset_index(drop=True)

    tab_all, tab_pending, tab_done = st.tabs([
        f"　すべて（{len(df_sorted)}）　",
        f"　未投稿（{len(pending)}）　",
        f"　投稿済み（{len(done)}）　",
    ])
    with tab_all:
        render_list(df_sorted, "all")
    with tab_pending:
        render_list(pending, "pending")
    with tab_done:
        render_list(done, "done")


show_main(st.session_state["username"])
