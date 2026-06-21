"""English vocabulary learning game — Streamlit app (Hebrew UI)."""

from __future__ import annotations

import base64
import hashlib
import json
import random
import re
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from gtts import gTTS

import database as db

TEACHER_PASSWORD = "teacher123"
AUDIO_CACHE_DIR = Path(__file__).parent / ".cache" / "tts"
AUDIO_ERROR_MSG = "לא הצלחתי להשמיע כרגע, נסי שוב עוד רגע"
PRIORITY_LABELS = {"normal": "רגיל", "high": "גבוה", "test": "למבחן"}
PRIORITY_BOOST = {"test": 25.0, "high": 15.0, "normal": 0.0}
TEACHER_SOURCE_BOOST = 10.0
MASTERED_MIN_SEEN = 3
MASTERED_MIN_ACCURACY = 0.75
GRADE_OPTIONS = list(db.VALID_GRADES)
AVATAR_OPTIONS = list(db.VALID_AVATARS)

# ---------------------------------------------------------------------------
# Page config & styling
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="משחק אוצר מילים באנגלית",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Rubik:wght@400;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Rubik', sans-serif;
        }

        .main-title {
            font-size: 2.6rem;
            font-weight: 700;
            color: #6C3CE1;
            text-align: center;
            margin-bottom: 0.2rem;
        }

        .subtitle {
            font-size: 1.3rem;
            color: #555;
            text-align: center;
            margin-bottom: 1.5rem;
        }

        .word-card {
            background: linear-gradient(135deg, #FFE066 0%, #FF9A56 100%);
            border-radius: 20px;
            padding: 1.4rem 1.6rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }

        .word-english {
            font-size: 2rem;
            font-weight: 700;
            color: #2D1B69;
        }

        .word-hebrew {
            font-size: 1.5rem;
            color: #333;
            direction: rtl;
        }

        .example-box {
            background: #fff;
            border-radius: 12px;
            padding: 0.8rem 1rem;
            margin-top: 0.8rem;
            font-size: 1.15rem;
        }

        .score-box {
            background: linear-gradient(135deg, #56CCF2 0%, #2F80ED 100%);
            color: white;
            border-radius: 16px;
            padding: 1rem 1.5rem;
            text-align: center;
            font-size: 1.4rem;
            font-weight: 600;
        }

        .story-box {
            background: #F0F7FF;
            border-right: 6px solid #6C3CE1;
            border-radius: 16px;
            padding: 1.5rem;
            font-size: 1.25rem;
            line-height: 1.8;
            direction: rtl;
        }

        .story-en {
            direction: ltr;
            background: #FFF8E7;
            border-left: 6px solid #FF9A56;
            border-radius: 16px;
            padding: 1.5rem;
            font-size: 1.2rem;
            line-height: 1.8;
            margin-bottom: 1rem;
        }

        .story-vocab {
            background: linear-gradient(135deg, #FFE066 0%, #FF9A56 100%);
            color: #2D1B69;
            font-weight: 700;
            padding: 0.1rem 0.45rem;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        }

        .story-vocab-row {
            background: #fff;
            border-radius: 12px;
            padding: 0.6rem 0.8rem;
            margin-bottom: 0.5rem;
            border: 1px solid #EDE7FF;
        }

        div[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #EDE7FF 0%, #FFF 100%);
        }

        .stButton > button {
            font-size: 1.1rem !important;
            border-radius: 12px !important;
            padding: 0.5rem 1.5rem !important;
        }

        .stRadio > label, .stSelectbox > label {
            font-size: 1.15rem !important;
        }

        .feedback-wrong {
            background: #FFF0F0;
            border: 2px solid #FF6B6B;
            border-radius: 16px;
            padding: 1.2rem 1.4rem;
            margin: 1rem 0;
            font-size: 1.15rem;
            line-height: 1.7;
        }

        .feedback-wrong .label {
            color: #888;
            font-size: 0.95rem;
        }

        .feedback-tip {
            background: #FFF8E7;
            border-radius: 12px;
            padding: 0.9rem 1rem;
            margin-top: 0.8rem;
            font-size: 1.1rem;
            direction: rtl;
        }

        .student-pick {
            background: linear-gradient(135deg, #EDE7FF 0%, #D4F1FF 100%);
            border-radius: 20px;
            padding: 2rem;
            text-align: center;
            margin: 1rem 0;
        }

        .student-card {
            background: linear-gradient(135deg, #FFE066 0%, #FF9A56 100%);
            border-radius: 24px;
            padding: 1.8rem 1rem;
            text-align: center;
            margin-bottom: 1rem;
            box-shadow: 0 6px 16px rgba(0,0,0,0.12);
            border: 3px solid #fff;
        }

        .student-card-avatar {
            font-size: 3.5rem;
            line-height: 1.2;
        }

        .student-card-name {
            font-size: 1.6rem;
            font-weight: 700;
            color: #2D1B69;
            margin-top: 0.5rem;
        }

        .student-card-grade {
            font-size: 1rem;
            color: #555;
            margin-top: 0.2rem;
        }

        .welcome-box {
            background: linear-gradient(135deg, #EDE7FF 0%, #FFF8E7 100%);
            border-radius: 24px;
            padding: 2rem;
            margin: 1rem 0 2rem 0;
            text-align: center;
            border: 3px dashed #6C3CE1;
        }

        .personal-greeting {
            background: linear-gradient(135deg, #56CCF2 0%, #6C3CE1 100%);
            color: white;
            border-radius: 20px;
            padding: 1.2rem 1.5rem;
            text-align: center;
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Text-to-speech (disk cache + memory cache)
# ---------------------------------------------------------------------------


def _cache_path(text: str) -> Path:
    digest = hashlib.md5(text.strip().lower().encode("utf-8")).hexdigest()
    return AUDIO_CACHE_DIR / f"{digest}.mp3"


@st.cache_data(show_spinner=False)
def get_pronunciation_audio(text: str) -> bytes:
    clean = text.strip()
    if not clean:
        raise ValueError("empty text")

    cache_file = _cache_path(clean)
    if cache_file.exists():
        return cache_file.read_bytes()

    buffer = BytesIO()
    gTTS(text=clean, lang="en").write_to_fp(buffer)
    audio_bytes = buffer.getvalue()

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(audio_bytes)
    return audio_bytes


@st.cache_data(show_spinner=False)
def generate_audio_base64(text: str) -> str:
    audio_bytes = get_pronunciation_audio(text)
    return base64.b64encode(audio_bytes).decode("ascii")


def make_audio_key(word: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", word.strip().lower()).strip("_") or "word"
    return f"audio_{slug}_{index}"


def play_text(text: str, key: str, help_text: str = "") -> None:
    clean = text.strip()
    if not clean:
        return

    label = help_text or f"השמיעי: {clean[:60]}{'...' if len(clean) > 60 else ''}"
    if st.button("🔊", key=key, help=label):
        try:
            audio_b64 = generate_audio_base64(clean)
            audio_bytes = base64.b64decode(audio_b64)
            st.markdown(
                f"""
                <audio autoplay>
                  <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
                </audio>
                """,
                unsafe_allow_html=True,
            )
            st.audio(audio_bytes, format="audio/mp3")
        except Exception:
            st.warning(AUDIO_ERROR_MSG)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_words() -> pd.DataFrame:
    csv_df = pd.read_csv("words.csv")
    csv_df["source"] = "csv"
    csv_df["priority"] = "normal"
    csv_df["lesson_name"] = csv_df["lesson"].apply(lambda x: f"שיעור {int(x)}")
    csv_df["test_date"] = ""

    teacher_rows = db.get_teacher_words()
    if teacher_rows:
        teacher_df = pd.DataFrame(teacher_rows)
        teacher_df["source"] = "teacher"
        teacher_df["test_date"] = teacher_df["test_date"].fillna("")
        return pd.concat([teacher_df, csv_df], ignore_index=True)

    return csv_df


def word_badges(row: pd.Series) -> str:
    badges: list[str] = []
    if row.get("source") == "teacher":
        badges.append("⭐ מילת מורה")
    if row.get("priority") == "test":
        badges.append("📝 למבחן")
    return " ".join(badges)


def sort_words_for_display(words_df: pd.DataFrame) -> pd.DataFrame:
    df = words_df.copy()
    priority_order = {"test": 0, "high": 1, "normal": 2}
    source_order = {"teacher": 0, "csv": 1}
    df["_priority_sort"] = df["priority"].map(priority_order).fillna(2)
    df["_source_sort"] = df["source"].map(source_order).fillna(2)
    return (
        df.sort_values(["_priority_sort", "_source_sort"])
        .drop(columns=["_priority_sort", "_source_sort"])
        .reset_index(drop=True)
    )


@st.cache_data
def load_stories() -> pd.DataFrame:
    return pd.read_csv("stories.csv")


def get_lessons(words_df: pd.DataFrame) -> list[int]:
    return sorted(words_df["lesson"].unique().tolist())


def get_lesson_words(words_df: pd.DataFrame, lesson: int) -> pd.DataFrame:
    lesson_df = words_df[words_df["lesson"] == lesson].copy()
    teacher_df = lesson_df[lesson_df["source"] == "teacher"]
    csv_df = lesson_df[lesson_df["source"] == "csv"]
    ordered = pd.concat(
        [sort_words_for_display(teacher_df), sort_words_for_display(csv_df)],
        ignore_index=True,
    )
    return ordered


def get_story(stories_df: pd.DataFrame, lesson: int) -> dict[str, Any] | None:
    rows = stories_df[stories_df["lesson"] == lesson]
    if rows.empty:
        return None
    return rows.iloc[0].to_dict()


def parse_options(options_str: str) -> list[str]:
    return [opt.strip() for opt in str(options_str).split("|") if opt.strip()]


def normalize_answer(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def shuffle_with_seed(items: list[Any], seed: int) -> list[Any]:
    rng = random.Random(seed)
    shuffled = items[:]
    rng.shuffle(shuffled)
    return shuffled


def lookup_word_metadata(words_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for _, row in words_df.iterrows():
        key = normalize_answer(row["english"])
        lookup[key] = row.to_dict()
    return lookup


def get_performance_map(student_id: int) -> dict[str, dict[str, Any]]:
    return db.get_all_word_performance(student_id)


def effective_difficulty(row: dict[str, Any], perf: dict[str, Any]) -> float:
    boost = PRIORITY_BOOST.get(str(row.get("priority", "normal")), 0.0)
    if row.get("source") == "teacher":
        boost += TEACHER_SOURCE_BOOST
    return float(perf.get("difficulty_score", db.DEFAULT_DIFFICULTY)) + boost


def enrich_word_row(row: pd.Series, perf_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    data = row.to_dict()
    key = normalize_answer(data["english"])
    perf = perf_map.get(key)
    if not perf:
        perf = {
            "word": key,
            "times_seen": 0,
            "times_correct": 0,
            "times_wrong": 0,
            "last_seen": None,
            "difficulty_score": db.DEFAULT_DIFFICULTY,
        }
    data["perf"] = perf
    data["effective_difficulty"] = effective_difficulty(data, perf)
    return data


def select_practice_words(lesson_words: pd.DataFrame, perf_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = [enrich_word_row(row, perf_map) for _, row in lesson_words.iterrows()]
    if not enriched:
        return []

    priority_rank = {"test": 0, "high": 1, "normal": 2}
    enriched.sort(
        key=lambda w: (
            priority_rank.get(str(w.get("priority", "normal")), 2),
            0 if w.get("source") == "teacher" else 1,
            -w["effective_difficulty"],
        )
    )

    if len(enriched) <= 3:
        return enriched

    easy_count = min(2, max(1, len(enriched) // 4))
    hard_count = len(enriched) - easy_count
    hard_words = enriched[:hard_count]
    easy_words = enriched[-easy_count:]

    for word in easy_words:
        word["is_easy_mix"] = True

    selected: list[dict[str, Any]] = []
    easy_idx = 0
    for i, word in enumerate(hard_words):
        selected.append(word)
        if easy_idx < len(easy_words) and i % 2 == 1:
            selected.append(easy_words[easy_idx])
            easy_idx += 1
    selected.extend(easy_words[easy_idx:])
    return selected


def build_practice_recommendation(words_df: pd.DataFrame, student_id: int) -> str:
    summary = db.get_learning_summary(student_id)
    difficult = db.get_difficult_words(student_id, limit=5)
    metadata = lookup_word_metadata(words_df)

    if summary["practiced_words"] == 0:
        return "התחילי עם תרגול קצר של 10 דקות — האפליקציה תזכור מה קל ומה קשה! 🌱"

    difficult_names = []
    for item in difficult[:3]:
        meta = metadata.get(item["word"], {})
        hebrew = meta.get("hebrew", "")
        label = f"{meta.get('english', item['word'])} ({hebrew})" if hebrew else item["word"]
        difficult_names.append(label)

    test_words: list[str] = []
    if "priority" in words_df.columns:
        test_words = words_df[words_df["priority"] == "test"]["english"].astype(str).tolist()
    if test_words:
        test_preview = ", ".join(test_words[:3])
        if difficult_names:
            return (
                f"מומלץ לתרגל קודם: {', '.join(difficult_names)}. "
                f"יש גם מילים למבחן 📝: {test_preview}."
            )
        return f"קרוב מבחן — תרגלי את המילים: {test_preview} 📝"

    if difficult_names:
        return f"מומלץ להתמקד במילים: {', '.join(difficult_names)}. הן מופיעות יותר בתרגול! 💪"

    if summary["strong_words"] >= 5:
        return "כל הכבוד! יש לך הרבה מילים חזקות. המשיכי לתרגל מדי יום כדי לא לשכוח. 🌟"

    return "המשיכי לתרגל — האפליקציה תבחר אוטומטית מילים שצריך לחזק! 🎯"


# ---------------------------------------------------------------------------
# Daily mission
# ---------------------------------------------------------------------------


def _word_priority_key(word: dict[str, Any], grade: str) -> tuple[Any, ...]:
    grade_lesson = db.GRADE_TO_LESSON.get(grade, 4)
    priority_rank = {"test": 0, "high": 1, "normal": 2}
    lesson = int(word.get("lesson", grade_lesson))
    return (
        priority_rank.get(str(word.get("priority", "normal")), 2),
        0 if word.get("source") == "teacher" else 1,
        abs(lesson - grade_lesson),
    )


def _serialize_word(word: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "english", "hebrew", "example_en", "example_he",
        "lesson", "source", "priority", "lesson_name",
    )
    return {k: word[k] for k in keys if k in word}


def _deserialize_plan(plan: dict[str, Any], words_df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    metadata = lookup_word_metadata(words_df)

    def load_items(items: list[Any]) -> list[dict[str, Any]]:
        loaded: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            key = normalize_answer(str(item.get("english", "")))
            loaded.append(metadata.get(key, item))
        return loaded

    return {
        "new": load_items(plan.get("new", [])),
        "difficult": load_items(plan.get("difficult", [])),
        "review": load_items(plan.get("review", [])),
    }


def _pick_words(
    candidates: list[dict[str, Any]],
    count: int,
    selected_keys: set[str],
    grade: str,
) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    for word in sorted(candidates, key=lambda w: _word_priority_key(w, grade)):
        key = normalize_answer(str(word.get("english", "")))
        if not key or key in selected_keys:
            continue
        picked.append(word)
        selected_keys.add(key)
        if len(picked) >= count:
            break
    return picked


def build_daily_word_plan(
    words_df: pd.DataFrame,
    student_id: int,
    grade: str,
) -> dict[str, list[dict[str, Any]]]:
    perf_map = get_performance_map(student_id)
    metadata = lookup_word_metadata(words_df)
    selected_keys: set[str] = set()

    all_enriched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, row in sort_words_for_display(words_df).iterrows():
        key = normalize_answer(str(row["english"]))
        if key in seen:
            continue
        seen.add(key)
        all_enriched.append(enrich_word_row(row, perf_map))

    unseen = [w for w in all_enriched if int(w["perf"]["times_seen"]) == 0]
    new_words = _pick_words(unseen, 3, selected_keys, grade)
    if len(new_words) < 3:
        low_seen = [
            w for w in all_enriched
            if int(w["perf"]["times_seen"]) <= 1
            and normalize_answer(str(w["english"])) not in selected_keys
        ]
        new_words.extend(_pick_words(low_seen, 3 - len(new_words), selected_keys, grade))

    difficult_candidates: list[dict[str, Any]] = []
    for item in db.get_difficult_words(student_id, limit=12):
        meta = metadata.get(item["word"])
        if meta:
            difficult_candidates.append(enrich_word_row(pd.Series(meta), perf_map))
    difficult = _pick_words(difficult_candidates, 3, selected_keys, grade)
    if len(difficult) < 3:
        hard_pool = [
            w for w in all_enriched
            if float(w["effective_difficulty"]) >= 55
            and normalize_answer(str(w["english"])) not in selected_keys
        ]
        difficult.extend(_pick_words(hard_pool, 3 - len(difficult), selected_keys, grade))

    review_candidates: list[dict[str, Any]] = []
    for item in db.get_mastered_words(student_id, limit=12):
        meta = metadata.get(item["word"])
        if meta:
            review_candidates.append(enrich_word_row(pd.Series(meta), perf_map))
    for item in db.get_review_word_candidates(student_id, limit=12):
        meta = metadata.get(item["word"])
        if meta:
            review_candidates.append(enrich_word_row(pd.Series(meta), perf_map))
    review = _pick_words(review_candidates, 2, selected_keys, grade)
    if len(review) < 2:
        practiced = [
            w for w in all_enriched
            if int(w["perf"]["times_seen"]) > 0
            and normalize_answer(str(w["english"])) not in selected_keys
        ]
        review.extend(_pick_words(practiced, 2 - len(review), selected_keys, grade))

    if len(new_words) < 3:
        extra_new = [
            w for w in all_enriched
            if normalize_answer(str(w["english"])) not in selected_keys
        ]
        new_words.extend(_pick_words(extra_new, 3 - len(new_words), selected_keys, grade))

    if len(difficult) < 3:
        extra_hard = [
            w for w in all_enriched
            if normalize_answer(str(w["english"])) not in selected_keys
        ]
        difficult.extend(_pick_words(extra_hard, 3 - len(difficult), selected_keys, grade))

    if len(review) < 2:
        extra_review = [
            w for w in all_enriched
            if normalize_answer(str(w["english"])) not in selected_keys
        ]
        review.extend(_pick_words(extra_review, 2 - len(review), selected_keys, grade))

    return {"new": new_words, "difficult": difficult, "review": review}


def get_or_create_daily_plan(
    words_df: pd.DataFrame,
    student_id: int,
    grade: str,
) -> dict[str, list[dict[str, Any]]]:
    session = db.get_daily_session(student_id)
    if session and session.get("words_json"):
        plan = json.loads(session["words_json"])
        return _deserialize_plan(plan, words_df)

    plan = build_daily_word_plan(words_df, student_id, grade)
    serializable = {key: [_serialize_word(w) for w in words] for key, words in plan.items()}
    db.save_daily_session_plan(student_id, serializable)
    return plan


def daily_all_words(plan: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in ("new", "difficult", "review"):
        for word in plan.get(group, []):
            key = normalize_answer(str(word.get("english", "")))
            if key and key not in seen:
                combined.append(word)
                seen.add(key)
    return combined


def build_daily_questions(
    words_df: pd.DataFrame,
    plan: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    all_words = daily_all_words(plan)
    if not all_words:
        return []

    questions: list[dict[str, Any]] = []
    for word in all_words:
        row = pd.Series(word)
        word_questions = _questions_for_word(row, words_df)
        for q in word_questions:
            q["lesson"] = int(word.get("lesson", 0))
        questions.extend(word_questions)
    return questions


def build_difficult_review_questions(
    words_df: pd.DataFrame,
    student_id: int,
    limit: int = 8,
) -> list[dict[str, Any]]:
    metadata = lookup_word_metadata(words_df)
    perf_map = get_performance_map(student_id)
    words: list[dict[str, Any]] = []
    for item in db.get_difficult_words(student_id, limit=limit):
        meta = metadata.get(item["word"])
        if meta:
            words.append(enrich_word_row(pd.Series(meta), perf_map))

    questions: list[dict[str, Any]] = []
    for word in words:
        row = pd.Series(word)
        questions.extend(_questions_for_word(row, words_df))
    return questions


def build_extra_practice_questions(
    words_df: pd.DataFrame,
    student_id: int,
    grade: str,
    limit: int = 8,
) -> list[dict[str, Any]]:
    perf_map = get_performance_map(student_id)
    enriched = [enrich_word_row(row, perf_map) for _, row in sort_words_for_display(words_df).iterrows()]
    enriched.sort(key=lambda w: _word_priority_key(w, grade))
    selected = enriched[:limit]
    questions: list[dict[str, Any]] = []
    for word in selected:
        questions.extend(_questions_for_word(pd.Series(word), words_df))
    return questions


def build_story_questions(
    featured: list[dict[str, Any]],
    words_df: pd.DataFrame,
    csv_story: dict[str, Any] | None = None,
    min_q: int = 2,
    max_q: int = 5,
) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    if csv_story:
        for i in range(1, 4):
            he_key = f"q{i}_he"
            if csv_story.get(he_key):
                options = parse_options(str(csv_story.get(f"q{i}_options", "")))
                questions.append(
                    {
                        "key": f"comp_{i}",
                        "en": str(csv_story.get(f"q{i}_en", "")),
                        "he": str(csv_story[he_key]),
                        "options": options,
                        "answer": str(csv_story.get(f"q{i}_answer", "")),
                        "type": "comprehension",
                        "word_key": "",
                    }
                )

    for word in featured:
        if len(questions) >= max_q:
            break
        if any(q.get("word_key") == word["english"] for q in questions):
            continue
        correct_he = str(word["hebrew"])
        pool = words_df[words_df["hebrew"] != correct_he]["hebrew"].dropna()
        sample_size = min(3, max(0, len(pool)))
        distractors = pool.sample(sample_size).tolist() if sample_size else []
        options = shuffle_with_seed([correct_he] + distractors, hash(word["english"]) % 10000)
        questions.append(
            {
                "key": f"vocab_{word['english']}",
                "en": f"What does '{word['english']}' mean?",
                "he": f"מה פירוש המילה '{word['english']}'?",
                "options": options,
                "answer": correct_he,
                "type": "vocabulary",
                "word_key": str(word["english"]),
            }
        )

    if len(questions) < min_q:
        for word in featured:
            if len(questions) >= min_q:
                break
            if any(q.get("word_key") == word["english"] for q in questions):
                continue
            correct_he = str(word["hebrew"])
            pool = words_df[words_df["hebrew"] != correct_he]["hebrew"].dropna()
            sample_size = min(3, max(0, len(pool)))
            distractors = pool.sample(sample_size).tolist() if sample_size else []
            options = shuffle_with_seed([correct_he] + distractors, hash(word["english"]) % 10000)
            questions.append(
                {
                    "key": f"vocab_{word['english']}",
                    "en": f"What does '{word['english']}' mean?",
                    "he": f"מה פירוש המילה '{word['english']}'?",
                    "options": options,
                    "answer": correct_he,
                    "type": "vocabulary",
                    "word_key": str(word["english"]),
                }
            )

    return questions[:max_q]


def highlight_story_words(story_en: str, words: list[dict[str, Any]]) -> str:
    highlighted = story_en
    english_words = sorted(
        {str(w.get("english", "")).strip() for w in words if w.get("english")},
        key=len,
        reverse=True,
    )
    for word in english_words:
        pattern = re.compile(rf"\b({re.escape(word)})\b", re.IGNORECASE)
        highlighted = pattern.sub(r'<span class="story-vocab">\1</span>', highlighted)
    return highlighted


def generate_narrative_story(
    words: list[dict[str, Any]],
    student_name: str | None = None,
) -> tuple[str, str]:
    name = (student_name or "Maya").strip() or "Maya"
    featured = words[:6]
    intro = f"Today, {name} practiced new English words at school. "
    sentences: list[str] = []
    he_sentences: list[str] = []
    for word in featured:
        example = str(word.get("example_en", "")).strip()
        if example:
            sentences.append(example)
        he = str(word.get("example_he", "")).strip()
        if he:
            he_sentences.append(he)

    if not sentences:
        word_list = ", ".join(str(w["english"]) for w in featured)
        story_en = intro + f"She learned these words: {word_list}."
        story_he = f"היום {name} למדה מילים חדשות: {', '.join(str(w['hebrew']) for w in featured)}."
    else:
        story_en = intro + " ".join(sentences)
        story_he = " ".join([f"היום {name} למדה מילים חדשות."] + he_sentences)
    return story_en, story_he


def build_personalized_story(
    words: list[dict[str, Any]],
    words_df: pd.DataFrame,
    stories_df: pd.DataFrame | None = None,
    student_name: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    featured = words[:8] if words else []
    if not featured:
        return {
            "story_en": "",
            "story_he": "",
            "story_en_html": "",
            "words": [],
            "questions": [],
            "title": title or "",
        }

    csv_story: dict[str, Any] | None = None
    if stories_df is not None:
        lesson_counts: dict[int, int] = {}
        for word in featured:
            lesson = int(word.get("lesson", 0))
            lesson_counts[lesson] = lesson_counts.get(lesson, 0) + 1
        if lesson_counts:
            best_lesson = max(lesson_counts, key=lesson_counts.get)
            csv_story = get_story(stories_df, best_lesson)

    if csv_story:
        story_en = str(csv_story.get("story_en", ""))
        story_he = str(csv_story.get("story_he", ""))
    else:
        story_en, story_he = generate_narrative_story(featured, student_name)

    story_en_html = highlight_story_words(story_en, featured)
    questions = build_story_questions(featured, words_df, csv_story)

    return {
        "story_en": story_en,
        "story_en_html": story_en_html,
        "story_he": story_he,
        "words": featured,
        "questions": questions,
        "title": title or f"סיפור — {db.today_str()}",
    }


def select_story_words(
    student_id: int,
    words_df: pd.DataFrame,
    grade: str,
    count: int = 6,
) -> list[dict[str, Any]]:
    perf_map = get_performance_map(student_id)
    usage = db.get_story_word_usage(student_id)

    all_enriched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, row in sort_words_for_display(words_df).iterrows():
        key = normalize_answer(str(row["english"]))
        if key in seen:
            continue
        seen.add(key)
        all_enriched.append(enrich_word_row(row, perf_map))

    def story_score(word: dict[str, Any]) -> float:
        key = normalize_answer(str(word["english"]))
        perf = word.get("perf", {})
        score = float(word.get("effective_difficulty", 50))
        if word.get("priority") == "test":
            score += 50
        elif word.get("priority") == "high":
            score += 20
        if word.get("source") == "teacher":
            score += 30
        score += float(perf.get("times_wrong", 0)) * 3
        score -= usage.get(key, 0) * 8
        return score

    all_enriched.sort(key=story_score, reverse=True)

    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()

    for word in all_enriched:
        if word.get("priority") != "test":
            continue
        key = normalize_answer(str(word["english"]))
        if key in selected_keys:
            continue
        selected.append(word)
        selected_keys.add(key)
        if len(selected) >= count:
            return selected[:count]

    for word in all_enriched:
        if len(selected) >= count:
            break
        key = normalize_answer(str(word["english"]))
        if key in selected_keys:
            continue
        selected.append(word)
        selected_keys.add(key)

    return selected[:count]


def build_daily_story(
    plan: dict[str, list[dict[str, Any]]],
    words_df: pd.DataFrame,
    stories_df: pd.DataFrame,
    student_name: str | None = None,
) -> dict[str, Any]:
    words = daily_all_words(plan)
    return build_personalized_story(
        words,
        words_df,
        stories_df=stories_df,
        student_name=student_name,
        title=f"סיפור יומי — {db.today_str()}",
    )


def reset_daily_flow() -> None:
    st.session_state.daily_step = "hub"
    st.session_state.daily_story_answers = {}
    st.session_state.daily_story_submitted = False
    st.session_state.daily_story_score = 0
    reset_practice()


def render_word_card(word: dict[str, Any], key_prefix: str, index: int) -> None:
    badges = word_badges(pd.Series(word))
    badge_html = f' <span style="font-size:1rem;">{badges}</span>' if badges else ""
    header_col, speaker_col = st.columns([6, 1])
    with header_col:
        st.markdown(
            f"""
            <div class="word-card">
                <div class="word-english">🔤 {word['english']}{badge_html}</div>
                <div class="word-hebrew">🇮🇱 {word['hebrew']}</div>
                <div class="example-box">
                    <div style="direction:ltr;">📝 {word.get('example_en', '')}</div>
                    <div style="direction:rtl; color:#666; margin-top:0.4rem;">{word.get('example_he', '')}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with speaker_col:
        st.markdown("<br>", unsafe_allow_html=True)
        play_text(
            str(word["english"]),
            key=make_audio_key(str(word["english"]), index),
            help_text=f"השמיעי: {word['english']}",
        )


def render_story_content(story: dict[str, Any], key_prefix: str) -> None:
    if story.get("title"):
        st.markdown(f"#### {story['title']}")

    speak_col, _ = st.columns([1, 6])
    with speak_col:
        play_text(
            story["story_en"],
            key=make_audio_key(f"{key_prefix}_story", 0),
            help_text="השמיעי את הסיפור",
        )

    html = story.get("story_en_html") or story["story_en"]
    st.markdown(f'<div class="story-en">{html}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="story-box">📘 {story["story_he"]}</div>', unsafe_allow_html=True)

    words = story.get("words", [])
    if words:
        st.markdown("**🔤 מילים בסיפור — לחצי 🔊 לשמוע:**")
        cols = st.columns(min(len(words), 4))
        for i, word in enumerate(words):
            with cols[i % len(cols)]:
                play_text(
                    str(word["english"]),
                    key=make_audio_key(f"{key_prefix}_{word['english']}", i + 1),
                    help_text=f"השמיעי: {word['english']}",
                )
                st.markdown(
                    f'<div class="story-vocab-row"><strong>{word["english"]}</strong> — {word["hebrew"]}</div>',
                    unsafe_allow_html=True,
                )


def render_story_quiz(
    story: dict[str, Any],
    student_id: int,
    key_prefix: str,
    answers_key: str,
    submitted_key: str,
    score_key: str,
    section: str,
    lesson_lookup_words: list[dict[str, Any]] | None = None,
    on_submit: Any | None = None,
    submit_label: str = "✅ שלחי תשובות",
) -> bool:
    st.markdown("#### ❓ שאלות הבנה")
    questions = story.get("questions", [])
    if not questions:
        st.info("אין שאלות לסיפור זה.")
        return False

    submitted = st.session_state.get(submitted_key, False)
    answers = st.session_state.get(answers_key, {})

    for question in questions:
        selected = st.radio(
            question["he"],
            question["options"],
            key=f"{key_prefix}_{question['key']}",
            disabled=submitted,
        )
        answers[question["key"]] = selected
    st.session_state[answers_key] = answers

    if submitted:
        score = st.session_state.get(score_key, 0)
        st.success(f"🎉 ניקוד: {score}/{len(questions)}")
        return False

    if st.button(submit_label, type="primary", use_container_width=True, key=f"{key_prefix}_submit"):
        score = 0
        lookup = lesson_lookup_words or story.get("words", [])
        for question in questions:
            selected = answers.get(question["key"], "")
            is_correct = normalize_answer(selected) == normalize_answer(question["answer"])
            if is_correct:
                score += 1
            word_key = question.get("word_key") or question["key"]
            lesson = 0
            lookup_key = normalize_answer(str(word_key).replace("vocab_", ""))
            for word in lookup:
                if normalize_answer(str(word.get("english", ""))) == lookup_key:
                    lesson = int(word.get("lesson", 0))
                    break
            q_type = "comprehension" if question.get("type") == "comprehension" else "vocabulary"
            answer_key = question["key"] if q_type == "comprehension" else str(word_key)
            db.record_answer(student_id, lesson, answer_key, q_type, section, is_correct)

        st.session_state[score_key] = score
        st.session_state[submitted_key] = True
        if on_submit:
            on_submit(score, len(questions))
        return True
    return False


def render_stories_page(
    words_df: pd.DataFrame,
    stories_df: pd.DataFrame,
    student_id: int,
    grade: str,
) -> None:
    st.markdown("## 📚 סיפורים")
    st.caption(
        "סיפור מותאם אישית — עם מילים שקשה לך, מילים למבחן ומילים מהמורה. "
        "מילים קשות יופיעו יותר בסיפורים הבאים."
    )

    if st.button("📖 סיפור חדש", type="primary", use_container_width=True):
        reset_story()
        words = select_story_words(student_id, words_df, grade, count=6)
        st.session_state.standalone_story = build_personalized_story(
            words,
            words_df,
            stories_df=stories_df,
            student_name=st.session_state.current_student_name,
            title=f"סיפור — {db.today_str()}",
        )
        st.rerun()

    story = st.session_state.get("standalone_story")
    if not story:
        st.info("לחצי על «סיפור חדש» כדי להתחיל!")
        return

    render_story_content(story, "standalone")

    def on_standalone_submit(score: int, total: int) -> None:
        db.save_student_story(
            student_id,
            "standalone",
            story["title"],
            story["story_en"],
            story["story_he"],
            [_serialize_word(w) for w in story["words"]],
            score,
            total,
        )

    if render_story_quiz(
        story,
        student_id,
        "standalone_quiz",
        "story_answers",
        "story_submitted",
        "story_score",
        section="story",
        on_submit=on_standalone_submit,
        submit_label="✅ סיימי את הסיפור",
    ):
        st.balloons()
        st.rerun()


def render_story_history(student_id: int, words_df: pd.DataFrame) -> None:
    st.markdown("## 📖 סיפורים שלמדתי")
    stories = db.get_student_stories(student_id, limit=50)
    if not stories:
        st.info("עדיין לא סיימת סיפורים. לכי ל📚 סיפורים או למשימה היומית!")
        return

    st.caption(f"סה״כ {len(stories)} סיפורים")
    for item in stories:
        type_label = "משימה יומית" if item["story_type"] == "daily" else "סיפור חופשי"
        label = f"{item['title']} — {item['story_date']} · {item['score']}/{item['total']} · {type_label}"
        with st.expander(label, expanded=False):
            enriched_words = item.get("words", [])
            if enriched_words and isinstance(enriched_words[0], str):
                metadata = lookup_word_metadata(words_df)
                enriched_words = [
                    metadata.get(normalize_answer(w), {"english": w, "hebrew": ""})
                    for w in enriched_words
                ]
            html = highlight_story_words(item["story_en"], enriched_words)
            st.markdown(f'<div class="story-en">{html}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="story-box">📘 {item["story_he"]}</div>', unsafe_allow_html=True)
            word_labels = [
                f"{w.get('english', '')} — {w.get('hebrew', '')}"
                for w in enriched_words
                if isinstance(w, dict)
            ]
            if word_labels:
                st.caption("מילים: " + ", ".join(word_labels))
            st.caption(f"הושלם: {item['completed_at']}")


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------


def init_session_state() -> None:
    defaults = {
        "practice_questions": [],
        "practice_index": 0,
        "practice_score": 0,
        "practice_finished": False,
        "story_answers": {},
        "story_submitted": False,
        "story_score": 0,
        "teacher_authenticated": False,
        "words_version": 0,
        "practice_feedback": None,
        "current_student_id": None,
        "current_student_name": "",
        "current_student_avatar": db.DEFAULT_AVATAR,
        "current_student_grade": db.DEFAULT_GRADE,
        "pending_student_id": None,
        "daily_step": "hub",
        "daily_story_answers": {},
        "daily_story_submitted": False,
        "daily_story_score": 0,
        "daily_extra_mode": "",
        "standalone_story": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_practice() -> None:
    st.session_state.practice_questions = []
    st.session_state.practice_index = 0
    st.session_state.practice_score = 0
    st.session_state.practice_finished = False
    st.session_state.practice_feedback = None


def reset_story() -> None:
    st.session_state.story_answers = {}
    st.session_state.story_submitted = False
    st.session_state.story_score = 0
    st.session_state.standalone_story = None


def get_student_id() -> int | None:
    value = st.session_state.get("current_student_id")
    return int(value) if value is not None else None


def select_student(student: dict[str, Any]) -> None:
    st.session_state.current_student_id = student["id"]
    st.session_state.current_student_name = student["name"]
    st.session_state.current_student_avatar = student.get("avatar", db.DEFAULT_AVATAR)
    st.session_state.current_student_grade = student.get("grade", db.DEFAULT_GRADE)
    st.session_state.pending_student_id = None
    reset_practice()
    reset_story()


def clear_student() -> None:
    st.session_state.current_student_id = None
    st.session_state.current_student_name = ""
    st.session_state.current_student_avatar = db.DEFAULT_AVATAR
    st.session_state.current_student_grade = db.DEFAULT_GRADE
    st.session_state.pending_student_id = None
    reset_practice()
    reset_story()


def default_lesson_index(grade: str, lessons: list[int]) -> int:
    if not lessons:
        return 0
    suggested = db.GRADE_TO_LESSON.get(grade, lessons[0])
    return lessons.index(suggested) if suggested in lessons else 0


def get_current_student_profile() -> dict[str, Any]:
    return {
        "id": st.session_state.get("current_student_id"),
        "name": st.session_state.get("current_student_name", ""),
        "avatar": st.session_state.get("current_student_avatar", db.DEFAULT_AVATAR),
        "grade": st.session_state.get("current_student_grade", db.DEFAULT_GRADE),
    }


def sync_current_student_from_db() -> None:
    student_id = get_student_id()
    if student_id is None:
        return
    student = db.get_student(student_id)
    if student:
        st.session_state.current_student_name = student["name"]
        st.session_state.current_student_avatar = student["avatar"]
        st.session_state.current_student_grade = student["grade"]
    else:
        clear_student()


def render_teacher_add_student_form() -> bool:
    with st.form("teacher_add_student_form"):
        name = st.text_input("שם *", placeholder="נועה")
        grade = st.selectbox("כיתה *", GRADE_OPTIONS, index=GRADE_OPTIONS.index("ה'"))
        st.markdown("**אווטאר:**")
        avatar = st.radio(
            "אווטאר",
            AVATAR_OPTIONS,
            horizontal=True,
            label_visibility="collapsed",
        )
        password = st.text_input(
            "סיסמה",
            type="password",
            help="ברירת מחדל: שם + 123 (למשל נועה123). השאירי ריק לברירת מחדל.",
        )
        submitted = st.form_submit_button("➕ הוסיפי תלמידה", use_container_width=True)
        if submitted:
            if not name.strip():
                st.error("נא להזין שם.")
            else:
                try:
                    db.create_student(
                        name,
                        grade,
                        avatar,
                        password if password.strip() else None,
                    )
                    st.success("התלמידה נוספה! 🌟")
                    return True
                except ValueError as exc:
                    st.error(str(exc))
    return False


def render_student_card(student: dict[str, Any], key_prefix: str) -> None:
    avatar = student.get("avatar", db.DEFAULT_AVATAR)
    name = student["name"]
    grade = student.get("grade", db.DEFAULT_GRADE)
    st.markdown(
        f"""
        <div class="student-card">
            <div class="student-card-avatar">{avatar}</div>
            <div class="student-card-name">{name}</div>
            <div class="student-card-grade">כיתה {grade}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(f"▶️ {name}", key=f"{key_prefix}_{student['id']}", use_container_width=True):
        st.session_state.pending_student_id = student["id"]
        st.rerun()


def render_student_password_form(student: dict[str, Any]) -> None:
    st.markdown(
        '<p class="main-title">🔐 כניסה</p>',
        unsafe_allow_html=True,
    )
    avatar = student.get("avatar", db.DEFAULT_AVATAR)
    st.markdown(
        f'<p class="subtitle">{avatar} שלום {student["name"]}! הכניסי את הסיסמה שלך</p>',
        unsafe_allow_html=True,
    )
    with st.form("student_login_form"):
        password = st.text_input("סיסמה", type="password")
        submitted = st.form_submit_button("כניסה ✅", use_container_width=True)
        if submitted:
            if db.verify_student_password(student["id"], password):
                select_student(student)
                st.rerun()
            else:
                st.error("סיסמה לא נכונה. נסי שוב.")
    if st.button("↩️ חזרה לבחירת תלמידה", use_container_width=True):
        st.session_state.pending_student_id = None
        st.rerun()


def render_student_login() -> None:
    students = db.get_students()

    if not students:
        st.markdown(
            '<p class="main-title">🔐 כניסה</p>',
            unsafe_allow_html=True,
        )
        st.info("אין עדיין תלמידות. היכנסי למצב מורה כדי להוסיף תלמידה.")
        return

    pending_id = st.session_state.get("pending_student_id")
    if pending_id:
        student = db.get_student(int(pending_id))
        if not student:
            st.session_state.pending_student_id = None
            st.rerun()
        render_student_password_form(student)
        return

    st.markdown(
        '<p class="main-title">מי לומדת היום? 😊</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="subtitle">בחרי את הפרופיל שלך והכניסי סיסמה 💜</p>',
        unsafe_allow_html=True,
    )

    cols = st.columns(min(len(students), 3))
    for i, student in enumerate(students):
        with cols[i % len(cols)]:
            render_student_card(student, "pick_student")


def render_personal_greeting() -> None:
    profile = get_current_student_profile()
    if not profile["name"]:
        return
    st.markdown(
        f'<div class="personal-greeting">{profile["avatar"]} שלום {profile["name"]}! מוכנה ללמוד אנגלית?</div>',
        unsafe_allow_html=True,
    )


def _questions_for_word(row: pd.Series, all_words: pd.DataFrame) -> list[dict[str, Any]]:
    correct_he = row["hebrew"]
    distractors = (
        all_words[all_words["hebrew"] != correct_he]["hebrew"]
        .sample(min(3, len(all_words) - 1))
        .tolist()
    )
    options = shuffle_with_seed([correct_he] + distractors, hash(row["english"]) % 10000)
    blank_sentence = re.sub(
        re.escape(row["english"]),
        "_______",
        row["example_en"],
        count=1,
        flags=re.IGNORECASE,
    )
    return [
        {
            "type": "multiple_choice",
            "english": row["english"],
            "hebrew": correct_he,
            "example_en": row["example_en"],
            "example_he": row.get("example_he", ""),
            "prompt": f"מה המשמעות של המילה **{row['english']}**?",
            "options": options,
            "answer": correct_he,
        },
        {
            "type": "fill_blank",
            "english": row["english"],
            "hebrew": correct_he,
            "example_en": row["example_en"],
            "example_he": row.get("example_he", ""),
            "prompt": f"השלימי את המשפט: **{blank_sentence}**",
            "hint": f"({row['example_he']})",
            "answer": row["english"],
        },
    ]


def friendly_wrong_explanation(q: dict[str, Any]) -> str:
    english = q["english"]
    hebrew = q["hebrew"]
    if q["type"] == "multiple_choice":
        return (
            f"לא נורא בכלל! 💛 המילה **{english}** באנגלית פירושה **{hebrew}**. "
            f"קראי את המשפט לדוגמה ונסי לדמיין את המילה — כך זה נשאר בראש!"
        )
    return (
        f"כמעט! 💛 המילה הנכונה היא **{english}** ({hebrew}). "
        f"הקשבי ל🔊, קראי את המשפט — ותראי שזה כבר יותר קל בפעם הבאה!"
    )


def submit_practice_answer(
    student_id: int,
    lesson: int,
    q: dict[str, Any],
    user_answer: str,
    is_correct: bool,
    section: str = "practice",
) -> None:
    db.record_answer(student_id, lesson, q["english"], q["type"], section, is_correct)
    if is_correct:
        st.session_state.practice_score += 1
    st.session_state.practice_feedback = {
        "is_correct": is_correct,
        "user_answer": user_answer.strip() or "—",
        "english": q["english"],
        "hebrew": q["hebrew"],
        "example_en": q["example_en"],
        "correct_display": q["answer"] if q["type"] == "multiple_choice" else q["english"],
        "explanation": friendly_wrong_explanation(q),
    }


def advance_practice(
    student_id: int,
    lesson: int,
    total: int,
    section: str = "practice",
    on_finish: Any | None = None,
) -> None:
    st.session_state.practice_feedback = None
    st.session_state.practice_index += 1
    if st.session_state.practice_index >= total:
        st.session_state.practice_finished = True
        if on_finish:
            on_finish()
        else:
            db.record_session(student_id, lesson, section, st.session_state.practice_score, total)


def render_practice_feedback(
    student_id: int,
    lesson: int,
    idx: int,
    total: int,
    key_prefix: str = "practice",
    on_finish: Any | None = None,
    section: str = "practice",
) -> None:
    feedback = st.session_state.practice_feedback
    if not feedback:
        return

    if feedback["is_correct"]:
        st.success("כל הכבוד! התשובה נכונה 🎉")
        if st.button("לשאלה הבאה ➡️", key=f"continue_correct_{key_prefix}_{idx}", use_container_width=True):
            advance_practice(student_id, lesson, total, section=section, on_finish=on_finish)
            st.rerun()
        return

    st.error("התשובה לא נכונה — אבל זה בסדר גמור! 💛 בואי נלמד יחד:")
    st.markdown(
        f"""
        <div class="feedback-wrong">
            <div><span class="label">ענית:</span> <strong>{feedback['user_answer']}</strong></div>
            <div><span class="label">התשובה הנכונה:</span> <strong>{feedback['correct_display']}</strong></div>
            <div><span class="label">פירוש:</span> <strong>{feedback['hebrew']}</strong></div>
            <div style="direction:ltr; margin-top:0.5rem;">
                <span class="label">משפט לדוגמה:</span> {feedback['example_en']}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    speak_col, _ = st.columns([1, 5])
    with speak_col:
        play_text(
            feedback["english"],
            key=make_audio_key(feedback["english"], idx),
            help_text=f"השמיעי: {feedback['english']}",
        )

    st.markdown(f"💡 {feedback['explanation']}")

    if st.button("הבנתי, לשאלה הבאה ✅", key=f"continue_wrong_{key_prefix}_{idx}", use_container_width=True):
        advance_practice(student_id, lesson, total, section=section, on_finish=on_finish)
        st.rerun()


def build_practice_questions(words_df: pd.DataFrame, lesson: int, student_id: int) -> list[dict[str, Any]]:
    lesson_words = get_lesson_words(words_df, lesson)
    all_words = words_df.copy()
    perf_map = get_performance_map(student_id)
    selected_words = select_practice_words(lesson_words, perf_map)

    questions: list[dict[str, Any]] = []
    for i, word_data in enumerate(selected_words):
        row = pd.Series(word_data)
        word_questions = _questions_for_word(row, all_words)
        if word_data.get("is_easy_mix"):
            word_questions = [word_questions[i % 2]]
        questions.extend(word_questions)

    return questions


# ---------------------------------------------------------------------------
# UI sections
# ---------------------------------------------------------------------------


def render_practice_ui(
    student_id: int,
    questions: list[dict[str, Any]],
    key_prefix: str,
    section: str = "practice",
    on_finish: Any | None = None,
    start_label: str = "התחילי תרגול",
) -> None:
    if not questions:
        st.info("אין שאלות לתרגול כרגע.")
        return

    if not st.session_state.practice_questions:
        if st.button(start_label, type="primary", use_container_width=True):
            reset_practice()
            st.session_state.practice_questions = questions
            st.rerun()
        return

    idx = st.session_state.practice_index
    total = len(st.session_state.practice_questions)

    if st.session_state.practice_finished:
        if on_finish is not None:
            on_finish()
            st.success(f"🎉 סיימת את התרגול! הניקוד: {st.session_state.practice_score}/{total}")
            return
        score = st.session_state.practice_score
        st.balloons()
        st.success(f"🎉 סיימת! הניקוד שלך: {score}/{total}")
        if st.button("🔄 תרגול נוסף", use_container_width=True):
            reset_practice()
            st.rerun()
        return

    q = st.session_state.practice_questions[idx]
    lesson = int(q.get("lesson", 0)) if q.get("lesson") is not None else 0

    if st.session_state.practice_feedback:
        render_practice_feedback(
            student_id, lesson, idx, total,
            key_prefix=key_prefix,
            on_finish=on_finish,
            section=section,
        )
        st.markdown(
            f'<div class="score-box">⭐ ניקוד נוכחי: {st.session_state.practice_score}</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(f"### שאלה {idx + 1} מתוך {total}")
    st.markdown(q["prompt"])
    if q.get("hint"):
        st.caption(q["hint"])

    speak_col, _ = st.columns([1, 5])
    with speak_col:
        play_text(q["english"], key=make_audio_key(q["english"], idx), help_text=f"השמיעי: {q['english']}")

    if q["type"] == "multiple_choice":
        choice = st.radio("בחרי תשובה:", q["options"], key=f"mc_{key_prefix}_{idx}", label_visibility="collapsed")
        if st.button("✅ בדקי תשובה", key=f"check_{key_prefix}_{idx}", use_container_width=True):
            is_correct = normalize_answer(choice) == normalize_answer(q["answer"])
            submit_practice_answer(student_id, lesson, q, choice, is_correct, section=section)
            st.rerun()
    else:
        user_input = st.text_input("כתבי את המילה באנגלית:", key=f"fb_{key_prefix}_{idx}")
        if st.button("✅ בדקי תשובה", key=f"check_fb_{key_prefix}_{idx}", use_container_width=True):
            is_correct = normalize_answer(user_input) == normalize_answer(q["answer"])
            submit_practice_answer(student_id, lesson, q, user_input, is_correct, section=section)
            st.rerun()

    st.markdown(
        f'<div class="score-box">⭐ ניקוד נוכחי: {st.session_state.practice_score}</div>',
        unsafe_allow_html=True,
    )


def render_daily_mission(
    words_df: pd.DataFrame,
    student_id: int,
    grade: str,
) -> None:
    st.markdown("## 🌟 המשימה היומית שלי")
    today = db.today_str()

    if db.is_daily_completed(student_id, today):
        session = db.get_daily_session(student_id, today)
        score_text = ""
        if session and session.get("score") is not None and session.get("total"):
            score_text = f" הניקוד: {session['score']}/{session['total']}."
        st.success(f"סיימת את המשימה היומית 🎉{score_text}")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🎮 תרגול נוסף", use_container_width=True):
                reset_practice()
                st.session_state.daily_extra_mode = "extra"
                st.session_state.daily_step = "extra_practice"
                st.session_state.practice_questions = build_extra_practice_questions(words_df, student_id, grade)
                st.rerun()
        with col2:
            if st.button("😅 חזרה על מילים שקשה לי", use_container_width=True):
                reset_practice()
                st.session_state.daily_extra_mode = "difficult"
                st.session_state.daily_step = "extra_practice"
                st.session_state.practice_questions = build_difficult_review_questions(words_df, student_id)
                st.rerun()
        return

    step = st.session_state.get("daily_step", "hub")
    plan = get_or_create_daily_plan(words_df, student_id, grade)
    all_words = daily_all_words(plan)

    if step == "extra_practice":
        title = "🎮 תרגול נוסף" if st.session_state.daily_extra_mode == "extra" else "😅 חזרה על מילים שקשה לי"
        st.markdown(f"### {title}")
        render_practice_ui(
            student_id,
            st.session_state.practice_questions,
            key_prefix=f"daily_extra_{st.session_state.daily_extra_mode}",
            section="daily",
        )
        if st.button("↩️ חזרה למשימה היומית"):
            reset_daily_flow()
            st.rerun()
        return

    if not all_words:
        st.info("עדיין אין מספיק מילים. בקשי מהמורה להוסיף מילים במצב מורה.")
        return

    if step == "hub":
        st.markdown("### 📋 המילים של היום")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**✨ מילים חדשות (3)**")
            for w in plan.get("new", []):
                st.markdown(f"- {w.get('english')} — {w.get('hebrew')}")
        with c2:
            st.markdown("**😅 מילים שקשה לי (3)**")
            for w in plan.get("difficult", []):
                st.markdown(f"- {w.get('english')} — {w.get('hebrew')}")
        with c3:
            st.markdown("**🔄 חזרה (2)**")
            for w in plan.get("review", []):
                st.markdown(f"- {w.get('english')} — {w.get('hebrew')}")

        test_words = [w for w in all_words if w.get("priority") == "test"]
        if test_words:
            st.info("📝 יש היום מילים למבחן — הן מופיעות קודם במשימה!")

        if st.button("🚀 התחילי את המשימה היומית", type="primary", use_container_width=True):
            st.session_state.daily_step = "learn"
            st.rerun()
        return

    if step == "learn":
        st.markdown("### ✨ שלב 1: מילים חדשות")
        for i, word in enumerate(plan.get("new", [])):
            render_word_card(word, "daily_new", i)
        st.markdown("### 😅 שלב 2: מילים שקשה לי")
        for i, word in enumerate(plan.get("difficult", [])):
            render_word_card(word, "daily_hard", i)
        st.markdown("### 🔄 שלב 3: חזרה על מילים")
        for i, word in enumerate(plan.get("review", [])):
            render_word_card(word, "daily_review", i)
        if st.button("המשיכי לתרגול ➡️", type="primary", use_container_width=True):
            reset_practice()
            questions = build_daily_questions(words_df, plan)
            for q in questions:
                for w in all_words:
                    if normalize_answer(str(w["english"])) == normalize_answer(str(q["english"])):
                        q["lesson"] = int(w.get("lesson", 0))
                        break
            st.session_state.practice_questions = questions
            st.session_state.daily_step = "practice"
            st.rerun()
        return

    if step == "practice":
        st.markdown("### 🎮 שלב 4: תרגול ו השלמת משפטים")

        def finish_practice() -> None:
            st.session_state.daily_step = "story"

        render_practice_ui(
            student_id,
            st.session_state.practice_questions,
            key_prefix="daily_practice",
            section="daily",
            on_finish=finish_practice,
            start_label="התחילי תרגול יומי",
        )

        if st.session_state.practice_finished:
            if st.button("המשיכי לסיפור 📚", type="primary", use_container_width=True):
                st.session_state.daily_step = "story"
                st.rerun()
        return

    if step == "story":
        st.markdown("### 📚 שלב 5: סיפור קצר")
        stories_df = load_stories()
        story = build_daily_story(
            plan,
            words_df,
            stories_df,
            student_name=st.session_state.current_student_name,
        )
        if not story["story_en"]:
            db.complete_daily_session(
                student_id,
                st.session_state.practice_score,
                len(st.session_state.practice_questions),
            )
            st.session_state.daily_step = "hub"
            st.rerun()

        render_story_content(story, "daily_story")

        def on_daily_story_submit(score: int, total: int) -> None:
            practice_total = len(st.session_state.practice_questions)
            practice_score = st.session_state.practice_score
            combined_score = practice_score + score
            combined_total = practice_total + total
            db.complete_daily_session(student_id, combined_score, combined_total)
            db.save_student_story(
                student_id,
                "daily",
                story["title"],
                story["story_en"],
                story["story_he"],
                [_serialize_word(w) for w in story["words"]],
                score,
                total,
            )
            st.session_state.daily_story_score = score
            st.session_state.daily_step = "hub"

        if render_story_quiz(
            story,
            student_id,
            "daily_story_quiz",
            "daily_story_answers",
            "daily_story_submitted",
            "daily_story_score",
            section="daily",
            lesson_lookup_words=all_words,
            on_submit=on_daily_story_submit,
            submit_label="✅ סיימי את המשימה היומית",
        ):
            st.balloons()
            st.rerun()
        return


def render_header() -> None:
    st.markdown('<p class="main-title">📚 משחק אוצר מילים באנגלית 🌟</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">משימה יומית, סיפורים מותאמים ותרגול — הכל לפי ההתקדמות שלך!</p>',
        unsafe_allow_html=True,
    )



def render_vocabulary(words_df: pd.DataFrame, grade: str) -> None:
    st.markdown("## 📖 כל המילים")
    st.caption("עיון בכל המילים — המשימה היומית בוחרת מילים אוטומטית לפי ההתקדמות שלך.")
    lessons = get_lessons(words_df)
    default_lesson = db.GRADE_TO_LESSON.get(grade, lessons[0] if lessons else 1)
    with st.expander("📚 סינון לפי שיעור (אופציונלי)", expanded=False):
        st.selectbox(
            "שיעור:",
            lessons,
            index=default_lesson_index(grade, lessons),
            format_func=lambda x: f"שיעור {x}",
            key="browse_lesson_select",
        )
    lesson = st.session_state.get("browse_lesson_select", default_lesson)

    st.markdown(f"### מילים — שיעור {lesson}")
    st.markdown("לחצי 🔊 כדי לשמוע את ההגייה! 🧠✨")

    lesson_words = get_lesson_words(words_df, lesson)
    for i, row in lesson_words.iterrows():
        badges = word_badges(row)
        badge_html = f' <span style="font-size:1rem;">{badges}</span>' if badges else ""
        header_col, speaker_col = st.columns([6, 1])
        with header_col:
            st.markdown(
                f"""
                <div class="word-card">
                    <div class="word-english">🔤 {row['english']}{badge_html}</div>
                    <div class="word-hebrew">🇮🇱 {row['hebrew']}</div>
                    <div class="example-box">
                        <div style="direction:ltr;">📝 {row['example_en']}</div>
                        <div style="direction:rtl; color:#666; margin-top:0.4rem;">{row['example_he']}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with speaker_col:
            st.markdown("<br>", unsafe_allow_html=True)
            play_text(row["english"], key=make_audio_key(str(row["english"]), i), help_text=f"השמיעי: {row['english']}")

    st.success(f"🎉 יש {len(lesson_words)} מילים בשיעור {lesson}. המשימה היומית מחכה לך בתפריט!")


def render_word_list_with_speaker(
    items: list[dict[str, Any]],
    metadata: dict[str, dict[str, Any]],
    key_prefix: str,
) -> None:
    for i, item in enumerate(items):
        meta = metadata.get(item["word"], {})
        english = meta.get("english", item["word"])
        hebrew = meta.get("hebrew", "—")
        col_text, col_speaker = st.columns([6, 1])
        with col_text:
            st.markdown(
                f"""
                <div class="word-card" style="padding:1rem 1.2rem;">
                    <div class="word-english" style="font-size:1.5rem;">🔤 {english}</div>
                    <div class="word-hebrew">🇮🇱 {hebrew}</div>
                    <div style="font-size:1rem; margin-top:0.5rem;">
                        ✅ {item['times_correct']} נכון &nbsp;|&nbsp; ❌ {item['times_wrong']} שגוי
                        &nbsp;|&nbsp; 📊 קושי: {item['difficulty_score']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col_speaker:
            st.markdown("<br>", unsafe_allow_html=True)
            play_text(english, key=make_audio_key(english, i), help_text=f"השמיעי: {english}")


def render_learning(words_df: pd.DataFrame, student_id: int | None) -> None:
    st.markdown("## 🧠 הלמידה שלי")
    if student_id is None:
        st.warning("👧 בחרי תלמידה קודם כדי לראות את הלמידה שלך!")
        return

    st.markdown("כאן תראי אילו מילים כבר שולטת בהן — ואילו עדיין צריך לתרגל! 💜")

    metadata = lookup_word_metadata(words_df)
    difficult = db.get_difficult_words(student_id, limit=8)
    mastered = db.get_mastered_words(
        student_id,
        limit=8,
        min_seen=MASTERED_MIN_SEEN,
        min_accuracy=MASTERED_MIN_ACCURACY,
    )
    summary = db.get_learning_summary(student_id)

    st.divider()
    st.markdown("### 😅 מילים שקשה לי")
    if difficult:
        st.caption("המילים האלה מופיעות יותר בתרגול — זה בסדר, כך נלמד!")
        render_word_list_with_speaker(difficult, metadata, "difficult")
    else:
        st.info("עדיין אין מילים קשות — תרגלי קצת ונראה! 🚀")

    st.divider()
    st.markdown("### 🌟 מילים שאני כבר יודעת")
    if mastered:
        st.caption("כל הכבוד! המילים האלה כבר בטוחות אצלך.")
        render_word_list_with_speaker(mastered, metadata, "mastered")
    else:
        st.info("תרגלי עוד קצת — בקרוב יופיעו כאן מילים שאת כבר יודעת! 💪")

    st.divider()
    st.markdown("### 👨‍👩‍👧 סיכום להורים")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("מילים שתורגלו", summary["practiced_words"])
    c2.metric("מילים חזקות", summary["strong_words"])
    c3.metric("מילים קשות", summary["difficult_words"])
    accuracy_label = (
        f"{round(summary['total_correct'] / summary['total_seen'] * 100)}%"
        if summary["total_seen"]
        else "—"
    )
    c4.metric("דיוק כללי", accuracy_label)

    recommendation = build_practice_recommendation(words_df, student_id)
    st.info(f"💡 **המלצה לתרגול הבא:** {recommendation}")


def render_teacher_mode(words_df: pd.DataFrame) -> None:
    st.markdown("## 👩‍🏫 מצב מורה")
    st.markdown(
        "הוסיפי מילים חדשות עם עדיפות. מילים ל**מבחן** 📝 ו**עדיפות גבוהה** מופיעות ראשונות בתרגול."
    )

    if not st.session_state.teacher_authenticated:
        st.info("🔒 הכניסי סיסמה כדי להיכנס למצב מורה.")
        st.caption("סיסמת מורה: teacher123 (ראו README)")
        password = st.text_input("סיסמת מורה:", type="password", key="teacher_password_input")
        if st.button("🔑 כניסה"):
            if password == TEACHER_PASSWORD:
                st.session_state.teacher_authenticated = True
                st.success("ברוכה הבאה, מורה! 🎉")
                st.rerun()
            else:
                st.error("סיסמה שגויה. נסי שוב.")
        return

    st.success("✅ את מחוברת כמורה")
    if st.button("🚪 יציאה ממצב מורה"):
        st.session_state.teacher_authenticated = False
        st.rerun()

    st.divider()
    st.markdown("### ➕ הוספת מילה חדשה")

    existing_lessons = get_lessons(words_df)
    lesson_options = {f"שיעור {n}": n for n in existing_lessons}

    with st.form("add_word_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            english = st.text_input("מילה באנגלית *", placeholder="wonderful")
            example_en = st.text_input("משפט לדוגמה (אנגלית) *", placeholder="It was a wonderful day.")
            lesson_name = st.text_input("שם שיעור *", placeholder="יחידה 3 — חיות")
        with col2:
            hebrew = st.text_input("תרגום לעברית *", placeholder="נפלא")
            example_he = st.text_input("משפט לדוגמה (עברית)", placeholder="זה היה יום נפלא.")
            lesson_pick = st.selectbox("שיוך לשיעור (מספר) *", options=list(lesson_options.keys()))
            priority = st.selectbox(
                "עדיפות *",
                options=["normal", "high", "test"],
                format_func=lambda p: PRIORITY_LABELS[p],
            )
            test_date = st.date_input("תאריך מבחן (אופציונלי)", value=None)

        submitted = st.form_submit_button("💾 שמרי מילה", use_container_width=True)
        if submitted:
            if not english.strip() or not hebrew.strip() or not example_en.strip() or not lesson_name.strip():
                st.error("נא למלא: מילה באנגלית, תרגום, משפט לדוגמה, ושם שיעור.")
            else:
                lesson_num = lesson_options[lesson_pick]
                test_date_str = test_date.isoformat() if test_date else None
                db.add_teacher_word(
                    lesson=lesson_num,
                    lesson_name=lesson_name,
                    english=english,
                    hebrew=hebrew,
                    example_en=example_en,
                    example_he=example_he,
                    priority=priority,
                    test_date=test_date_str,
                )
                st.session_state.words_version += 1
                reset_practice()
                st.success(f"המילה **{english.strip()}** נוספה! 🌟")
                st.rerun()

    st.divider()
    st.markdown("### 📋 מילים שהמורה הוסיפה")
    teacher_words = db.get_teacher_words()
    if not teacher_words:
        st.info("עדיין לא הוספת מילים. השתמשי בטופס למעלה.")
    else:
        table_rows = []
        for word in teacher_words:
            table_rows.append(
                {
                    "מזהה": word["id"],
                    "מילה": word["english"],
                    "תרגום": word["hebrew"],
                    "שם שיעור": word.get("lesson_name") or f"שיעור {word['lesson']}",
                    "שיעור #": word["lesson"],
                    "עדיפות": PRIORITY_LABELS.get(word.get("priority", "normal"), "רגיל"),
                    "תאריך מבחן": word.get("test_date") or "—",
                    "משפט לדוגמה": word["example_en"],
                }
            )
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

        st.markdown("#### 🗑️ מחיקת מילה")
        delete_options = {
            f"{w['english']} — {w.get('lesson_name') or 'שיעור ' + str(w['lesson'])}": w["id"]
            for w in teacher_words
        }
        to_delete_label = st.selectbox("בחרי מילה למחיקה:", list(delete_options.keys()))
        if st.button("🗑️ מחקי מילה נבחרת", type="secondary"):
            db.delete_teacher_word(delete_options[to_delete_label])
            st.session_state.words_version += 1
            reset_practice()
            st.success("המילה נמחקה.")
            st.rerun()

    st.divider()
    st.markdown("### 👧 ניהול תלמידות")

    students = db.get_students()
    if students:
        overview_rows = []
        for student in students:
            overview = db.get_student_overview(student["id"])
            accuracy = (
                f"{round(overview['total_correct'] / overview['total_seen'] * 100)}%"
                if overview["total_seen"]
                else "—"
            )
            overview_rows.append(
                {
                    "אווטאר": student.get("avatar", db.DEFAULT_AVATAR),
                    "שם": student["name"],
                    "כיתה": student.get("grade", db.DEFAULT_GRADE),
                    "מילים שתורגלו": overview["practiced_words"],
                    "מילים חזקות": overview["strong_words"],
                    "מילים קשות": overview["difficult_words"],
                    "דיוק": accuracy,
                }
            )
        st.dataframe(pd.DataFrame(overview_rows), use_container_width=True, hide_index=True)
    else:
        st.info("אין תלמידות עדיין — הוסיפי תלמידה למטה.")

    st.markdown("#### ➕ הוספת תלמידה")
    st.caption("סיסמת ברירת מחדל לתלמידה חדשה: שם + 123 (למשל נועה123)")
    if render_teacher_add_student_form():
        st.rerun()

    if students:
        st.markdown("#### ✏️ עריכת תלמידה")
        edit_labels = {
            f"{s.get('avatar', db.DEFAULT_AVATAR)} {s['name']} (כיתה {s.get('grade', db.DEFAULT_GRADE)})": s
            for s in students
        }
        edit_label = st.selectbox("בחרי תלמידה לעריכה:", list(edit_labels.keys()))
        edit_student = edit_labels[edit_label]

        with st.form("edit_student_form"):
            new_name = st.text_input("שם", value=edit_student["name"])
            new_grade = st.selectbox(
                "כיתה",
                GRADE_OPTIONS,
                index=GRADE_OPTIONS.index(edit_student.get("grade", db.DEFAULT_GRADE)),
            )
            st.markdown("**אווטאר:**")
            current_avatar = edit_student.get("avatar", db.DEFAULT_AVATAR)
            new_avatar = st.radio(
                "avatar_pick",
                AVATAR_OPTIONS,
                index=AVATAR_OPTIONS.index(current_avatar) if current_avatar in AVATAR_OPTIONS else 0,
                horizontal=True,
                label_visibility="collapsed",
            )
            new_password = st.text_input(
                "סיסמה",
                value=edit_student.get("password", ""),
                help="ברירת מחדל: שם123. אפשר לשנות כאן.",
            )
            if st.form_submit_button("💾 שמרי שינויים", use_container_width=True):
                try:
                    db.update_student(
                        edit_student["id"],
                        name=new_name,
                        grade=new_grade,
                        avatar=new_avatar,
                        password=new_password,
                    )
                    if get_student_id() == edit_student["id"]:
                        sync_current_student_from_db()
                    st.success("הפרופיל עודכן! 🌟")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

        st.markdown("#### 🗑️ מחיקת תלמידה")
        delete_labels = {
            f"{s.get('avatar', db.DEFAULT_AVATAR)} {s['name']}": s["id"] for s in students
        }
        delete_label = st.selectbox("בחרי תלמידה למחיקה:", list(delete_labels.keys()))
        if st.button("🗑️ מחקי תלמידה נבחרת", type="secondary"):
            deleted_id = delete_labels[delete_label]
            db.delete_student(deleted_id)
            if get_student_id() == deleted_id:
                clear_student()
            st.success("התלמידה נמחקה (כולל כל ההתקדמות שלה).")
            st.rerun()


def render_progress(words_df: pd.DataFrame, student_id: int | None) -> None:
    st.markdown("## 📊 ההתקדמות שלי")
    if student_id is None:
        st.warning("👧 בחרי תלמידה קודם כדי לראות את ההתקדמות!")
        return

    stats = db.get_summary_stats(student_id)

    c1, c2, c3 = st.columns(3)
    c1.metric("📝 סה״כ תשובות", stats["total_answers"])
    c2.metric("✅ תשובות נכונות", stats["correct_answers"])
    c3.metric("❌ תשובות שגויות", stats["incorrect_answers"])

    if stats["total_answers"] > 0:
        accuracy = round(stats["correct_answers"] / stats["total_answers"] * 100)
        st.progress(accuracy / 100, text=f"🎯 דיוק כללי: {accuracy}%")

    st.divider()
    st.markdown("### 📚 התקדמות לפי שיעור")

    lesson_stats = db.get_lesson_stats(student_id)
    lessons = get_lessons(words_df)

    if not lesson_stats:
        st.info("עדיין אין נתונים — התחילי לתרגל כדי לראות התקדמות! 🚀")
    else:
        stats_by_lesson = {row["lesson"]: row for row in lesson_stats}
        for lesson in lessons:
            if lesson in stats_by_lesson:
                row = stats_by_lesson[lesson]
                total = row["total_answers"]
                correct = row["correct_answers"]
                pct = round(correct / total * 100) if total else 0
                st.markdown(f"**שיעור {lesson}** — {correct}/{total} נכון ({pct}%)")
                st.progress(pct / 100)
            else:
                st.markdown(f"**שיעור {lesson}** — עדיין לא תורגל")

    st.divider()
    st.markdown("### 🕐 תרגולים אחרונים")
    sessions = db.get_recent_sessions(student_id)
    if sessions:
        session_rows = []
        section_names = {"practice": "תרגול", "story": "סיפור", "daily": "משימה יומית"}
        for s in sessions:
            section_label = section_names.get(s["section"], s["section"])
            session_rows.append(
                {
                    "שיעור": s["lesson"] if s["lesson"] else "יומי",
                    "סוג": section_label,
                    "ניקוד": f"{s['score']}/{s['total']}",
                    "תאריך": s["completed_at"][:16].replace("T", " "),
                }
            )
        st.dataframe(pd.DataFrame(session_rows), use_container_width=True, hide_index=True)
    else:
        st.info("עדיין אין תרגולים שהושלמו.")

    st.divider()
    st.markdown("### 🔤 מילים שתרגלת")
    word_stats = db.get_word_stats(student_id)
    if word_stats:
        word_rows = []
        for w in word_stats:
            attempts = w["attempts"]
            correct = w["correct_count"]
            word_rows.append(
                {
                    "מילה": w["english_word"],
                    "ניסיונות": attempts,
                    "נכון": correct,
                    "דיוק": f"{round(correct / attempts * 100)}%" if attempts else "0%",
                }
            )
        st.dataframe(pd.DataFrame(word_rows), use_container_width=True, hide_index=True)

    st.divider()
    if st.button("🗑️ אפסי התקדמות (זהירות!)", type="secondary"):
        db.reset_progress(student_id)
        reset_practice()
        reset_story()
        reset_daily_flow()
        st.success("ההתקדמות אופסה. אפשר להתחיל מחדש! 🌱")
        st.rerun()


def main() -> None:
    db.init_db()
    init_session_state()

    words_df = load_words()
    stories_df = load_stories()
    student_id = get_student_id()

    render_header()

    if student_id is None:
        with st.sidebar:
            st.markdown("## 🔐 כניסה")
            guest_page = st.radio(
                " ",
                ["🏠 בחירת תלמידה", "👩‍🏫 מצב מורה"],
                label_visibility="collapsed",
            )
            st.divider()
            st.caption("נוצר באהבה ללימוד אנגלית 💜")

        if guest_page == "👩‍🏫 מצב מורה":
            render_teacher_mode(words_df)
        else:
            render_student_login()
        return

    with st.sidebar:
        st.markdown("## 🎯 תפריט")

        avatar = st.session_state.current_student_avatar
        name = st.session_state.current_student_name
        st.markdown(f"### {avatar} שלום {name} 👋")
        st.caption(f"כיתה {st.session_state.current_student_grade}")
        if st.button("🔄 החלפת תלמידה", use_container_width=True):
            clear_student()
            st.rerun()
        st.divider()

        page = st.radio(
            "לאן הולכים?",
            [
                "🌟 המשימה היומית שלי",
                "📚 סיפורים",
                "📖 סיפורים שלמדתי",
                "📖 כל המילים",
                "🧠 הלמידה שלי",
                "📊 התקדמות",
                "👩‍🏫 מצב מורה",
            ],
            label_visibility="collapsed",
        )

        st.divider()
        stats = db.get_summary_stats(student_id)
        st.markdown("### 🏅 הסטטיסטיקה שלך")
        if stats["total_answers"] > 0:
            accuracy = round(stats["correct_answers"] / stats["total_answers"] * 100)
            st.markdown(f"✅ **{stats['correct_answers']}** נכון")
            st.markdown(f"❌ **{stats['incorrect_answers']}** שגוי")
            st.markdown(f"🎯 **{accuracy}%** דיוק")
        else:
            st.markdown("התחילי לתרגל! 🚀")

        st.divider()
        st.caption("נוצר באהבה ללימוד אנגלית 💜")

    render_personal_greeting()

    grade = st.session_state.current_student_grade
    if page == "🌟 המשימה היומית שלי":
        render_daily_mission(words_df, student_id, grade)
    elif page == "📚 סיפורים":
        render_stories_page(words_df, stories_df, student_id, grade)
    elif page == "📖 סיפורים שלמדתי":
        render_story_history(student_id, words_df)
    elif page == "📖 כל המילים":
        render_vocabulary(words_df, grade)
    elif page == "🧠 הלמידה שלי":
        render_learning(words_df, student_id)
    elif page == "📊 התקדמות":
        render_progress(words_df, student_id)
    elif page == "👩‍🏫 מצב מורה":
        render_teacher_mode(words_df)


if __name__ == "__main__":
    main()
