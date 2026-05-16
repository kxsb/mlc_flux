import json
import re
import unicodedata
from datetime import datetime, timezone

from server.database import get_connection


CATEGORY_LABELS = {
    "bug": "Bug / problème technique",
    "data_question": "Question sur les données",
    "methodology": "Question méthodologique",
    "suggestion": "Suggestion d’amélioration",
    "data_correction": "Correction ou enrichissement de données",
    "other": "Autre retour",
}

STATUS_LABELS = {
    "new": "Nouveau",
    "acknowledged": "Pris en compte",
    "in_progress": "En cours",
    "needs_clarification": "Besoin de précision",
    "resolved": "Résolu",
    "closed": "Clos",
}

ALLOWED_CATEGORIES = set(CATEGORY_LABELS)
ALLOWED_STATUSES = set(STATUS_LABELS)

MAX_AUTHOR_NAME_LENGTH = 120
MAX_AUTHOR_EMAIL_LENGTH = 254
MAX_TITLE_LENGTH = 180
MAX_MESSAGE_LENGTH = 20_000
MAX_SOURCE_PAGE_LENGTH = 255
MAX_CONTEXT_JSON_LENGTH = 10_000
MAX_SEARCH_LENGTH = 200


class TicketValidationError(ValueError):
    """Erreur de validation fonctionnelle d'un ticket ou d'un message."""


class TicketNotFoundError(LookupError):
    """Ticket public introuvable."""


class TicketClosedError(ValueError):
    """Impossible de répondre à un ticket clos."""


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_required_text(value, *, field_label, max_length):
    if not isinstance(value, str):
        raise TicketValidationError(
            f"Le champ '{field_label}' doit être une chaîne."
        )

    cleaned = value.strip()

    if not cleaned:
        raise TicketValidationError(
            f"Le champ '{field_label}' est obligatoire."
        )

    if len(cleaned) > max_length:
        raise TicketValidationError(
            f"Le champ '{field_label}' dépasse {max_length} caractères."
        )

    return cleaned


def _clean_optional_text(value, *, field_label, max_length):
    if value is None:
        return None

    if not isinstance(value, str):
        raise TicketValidationError(
            f"Le champ '{field_label}' doit être une chaîne."
        )

    cleaned = value.strip()

    if not cleaned:
        return None

    if len(cleaned) > max_length:
        raise TicketValidationError(
            f"Le champ '{field_label}' dépasse {max_length} caractères."
        )

    return cleaned


def _clean_email(value):
    email = _clean_required_text(
        value,
        field_label="author_email",
        max_length=MAX_AUTHOR_EMAIL_LENGTH,
    )

    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise TicketValidationError(
            "Le champ 'author_email' ne ressemble pas à une adresse email valide."
        )

    return email


def _clean_optional_email(value):
    email = _clean_optional_text(
        value,
        field_label="author_email",
        max_length=MAX_AUTHOR_EMAIL_LENGTH,
    )

    if email is None:
        return ""

    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise TicketValidationError(
            "Le champ 'author_email' ne ressemble pas à une adresse email valide."
        )

    return email


def _clean_category(value):
    category = _clean_required_text(
        value,
        field_label="category",
        max_length=80,
    )

    if category not in ALLOWED_CATEGORIES:
        allowed = ", ".join(sorted(ALLOWED_CATEGORIES))
        raise TicketValidationError(
            f"Catégorie inconnue. Valeurs possibles : {allowed}."
        )

    return category


def _serialize_context(context):
    if context is None:
        return None

    if not isinstance(context, dict):
        raise TicketValidationError(
            "Le champ 'context' doit être un objet JSON."
        )

    raw = json.dumps(
        context,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    if len(raw) > MAX_CONTEXT_JSON_LENGTH:
        raise TicketValidationError(
            f"Le contexte dépasse {MAX_CONTEXT_JSON_LENGTH} caractères JSON."
        )

    return raw


def _deserialize_context(raw):
    if not raw:
        return None

    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None

    return value if isinstance(value, dict) else None


def _slugify(value):
    normalized = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char
        for char in normalized
        if not unicodedata.combining(char)
    )
    asciiish = without_marks.lower()
    asciiish = re.sub(r"[^a-z0-9]+", "-", asciiish)
    asciiish = re.sub(r"-{2,}", "-", asciiish).strip("-")
    return asciiish or "ticket"


def _public_ticket_from_row(row, *, opening_message=None):
    opening_excerpt = None

    if opening_message:
        normalized = " ".join(opening_message.split())
        opening_excerpt = (
            normalized[:217] + "..."
            if len(normalized) > 220
            else normalized
        )

    return {
        "public_ref": row["public_ref"],
        "slug": row["slug"],
        "title": row["title"],
        "category": row["category"],
        "category_label": CATEGORY_LABELS.get(row["category"], row["category"]),
        "status": row["status"],
        "status_label": STATUS_LABELS.get(row["status"], row["status"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_activity_at": row["last_activity_at"],
        "resolved_at": row["resolved_at"],
        "closed_at": row["closed_at"],
        "author_name": row["author_name"],
        "source_page": row["source_page"],
        "context": _deserialize_context(row["context_json"]),
        "official_message_id": row["official_message_id"],
        "message_count": row["message_count"] if "message_count" in row.keys() else None,
        "team_reply_count": row["team_reply_count"] if "team_reply_count" in row.keys() else None,
        "opening_excerpt": opening_excerpt,
    }


def create_ticket(
    *,
    author_name,
    author_email,
    title,
    category,
    body_markdown,
    source_page=None,
    context=None,
):
    clean_author_name = _clean_required_text(
        author_name,
        field_label="author_name",
        max_length=MAX_AUTHOR_NAME_LENGTH,
    )
    clean_author_email = _clean_optional_email(author_email)
    clean_title = _clean_required_text(
        title,
        field_label="title",
        max_length=MAX_TITLE_LENGTH,
    )
    clean_category = _clean_category(category)
    clean_body = _clean_required_text(
        body_markdown,
        field_label="body_markdown",
        max_length=MAX_MESSAGE_LENGTH,
    )
    clean_source_page = _clean_optional_text(
        source_page,
        field_label="source_page",
        max_length=MAX_SOURCE_PAGE_LENGTH,
    )
    context_json = _serialize_context(context)

    now = _now_iso()

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO tickets (
                public_ref,
                slug,
                title,
                category,
                status,
                visibility,
                created_at,
                updated_at,
                last_activity_at,
                resolved_at,
                closed_at,
                author_name,
                author_email,
                source_page,
                context_json,
                official_message_id
            )
            VALUES (
                NULL,
                NULL,
                ?,
                ?,
                'new',
                'public',
                ?,
                ?,
                ?,
                NULL,
                NULL,
                ?,
                ?,
                ?,
                ?,
                NULL
            )
        """, (
            clean_title,
            clean_category,
            now,
            now,
            now,
            clean_author_name,
            clean_author_email,
            clean_source_page,
            context_json,
        ))

        ticket_id = cur.lastrowid
        public_ref = f"T-{ticket_id:05d}"
        slug = f"{public_ref.lower()}-{_slugify(clean_title)}"

        cur.execute("""
            UPDATE tickets
            SET public_ref = ?, slug = ?
            WHERE id = ?
        """, (
            public_ref,
            slug,
            ticket_id,
        ))

        cur.execute("""
            INSERT INTO ticket_messages (
                ticket_id,
                author_name,
                author_email,
                author_role,
                body_markdown,
                visibility,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'public', ?, 'public', ?, NULL)
        """, (
            ticket_id,
            clean_author_name,
            clean_author_email,
            clean_body,
            now,
        ))

        cur.execute("""
            INSERT INTO ticket_events (
                ticket_id,
                event_type,
                actor_role,
                old_value,
                new_value,
                created_at
            )
            VALUES (?, 'created', 'public', NULL, 'new', ?)
        """, (
            ticket_id,
            now,
        ))

        conn.commit()
    finally:
        conn.close()

    return get_public_ticket(slug)


def list_public_tickets(
    *,
    category=None,
    status=None,
    search=None,
    sort="last_activity",
    limit=50,
    offset=0,
):
    params = []
    where_clauses = ["t.visibility = 'public'"]

    if category:
        clean_category = _clean_category(category)
        where_clauses.append("t.category = ?")
        params.append(clean_category)

    if status:
        clean_status = _clean_required_text(
            status,
            field_label="status",
            max_length=80,
        )

        if clean_status == "open":
            where_clauses.append("t.status NOT IN ('resolved', 'closed')")
        elif clean_status in ALLOWED_STATUSES:
            where_clauses.append("t.status = ?")
            params.append(clean_status)
        else:
            allowed = ", ".join(["open", *sorted(ALLOWED_STATUSES)])
            raise TicketValidationError(
                f"Statut inconnu. Valeurs possibles : {allowed}."
            )

    if search:
        clean_search = _clean_required_text(
            search,
            field_label="q",
            max_length=MAX_SEARCH_LENGTH,
        )
        like = f"%{clean_search}%"
        where_clauses.append("""
            (
                t.title LIKE ?
                OR EXISTS (
                    SELECT 1
                    FROM ticket_messages search_messages
                    WHERE search_messages.ticket_id = t.id
                      AND search_messages.visibility = 'public'
                      AND search_messages.body_markdown LIKE ?
                )
            )
        """)
        params.extend([like, like])

    try:
        clean_limit = int(limit)
    except (TypeError, ValueError):
        clean_limit = 50

    try:
        clean_offset = int(offset)
    except (TypeError, ValueError):
        clean_offset = 0

    clean_limit = max(1, min(clean_limit, 100))
    clean_offset = max(0, clean_offset)

    sort_sql = {
        "last_activity": "t.last_activity_at DESC, t.id DESC",
        "newest": "t.created_at DESC, t.id DESC",
        "oldest": "t.created_at ASC, t.id ASC",
    }.get(sort)

    if sort_sql is None:
        raise TicketValidationError(
            "Tri inconnu. Valeurs possibles : last_activity, newest, oldest."
        )

    where_sql = " AND ".join(where_clauses)

    conn = get_connection()
    cur = conn.cursor()

    try:
        total_row = cur.execute(f"""
            SELECT COUNT(*) AS total
            FROM tickets t
            WHERE {where_sql}
        """, params).fetchone()

        rows = cur.execute(f"""
            SELECT
                t.*,
                (
                    SELECT COUNT(*)
                    FROM ticket_messages tm
                    WHERE tm.ticket_id = t.id
                      AND tm.visibility = 'public'
                ) AS message_count,
                (
                    SELECT COUNT(*)
                    FROM ticket_messages tm
                    WHERE tm.ticket_id = t.id
                      AND tm.visibility = 'public'
                      AND tm.author_role = 'admin'
                ) AS team_reply_count,
                (
                    SELECT tm.body_markdown
                    FROM ticket_messages tm
                    WHERE tm.ticket_id = t.id
                      AND tm.visibility = 'public'
                    ORDER BY tm.created_at ASC, tm.id ASC
                    LIMIT 1
                ) AS opening_message
            FROM tickets t
            WHERE {where_sql}
            ORDER BY {sort_sql}
            LIMIT ? OFFSET ?
        """, [
            *params,
            clean_limit,
            clean_offset,
        ]).fetchall()
    finally:
        conn.close()

    items = [
        _public_ticket_from_row(
            row,
            opening_message=row["opening_message"],
        )
        for row in rows
    ]

    total = total_row["total"] if total_row else 0

    return {
        "items": items,
        "pagination": {
            "total": total,
            "limit": clean_limit,
            "offset": clean_offset,
            "returned": len(items),
        },
        "available_categories": CATEGORY_LABELS,
        "available_statuses": STATUS_LABELS,
    }


def get_public_ticket(slug):
    clean_slug = _clean_required_text(
        slug,
        field_label="slug",
        max_length=255,
    )

    conn = get_connection()
    cur = conn.cursor()

    try:
        ticket_row = cur.execute("""
            SELECT
                t.*,
                (
                    SELECT COUNT(*)
                    FROM ticket_messages tm
                    WHERE tm.ticket_id = t.id
                      AND tm.visibility = 'public'
                ) AS message_count,
                (
                    SELECT COUNT(*)
                    FROM ticket_messages tm
                    WHERE tm.ticket_id = t.id
                      AND tm.visibility = 'public'
                      AND tm.author_role = 'admin'
                ) AS team_reply_count
            FROM tickets t
            WHERE t.slug = ?
              AND t.visibility = 'public'
            LIMIT 1
        """, (
            clean_slug,
        )).fetchone()

        if ticket_row is None:
            raise TicketNotFoundError("Ticket public introuvable.")

        message_rows = cur.execute("""
            SELECT
                id,
                author_name,
                author_role,
                body_markdown,
                visibility,
                created_at,
                updated_at
            FROM ticket_messages
            WHERE ticket_id = ?
              AND visibility = 'public'
            ORDER BY created_at ASC, id ASC
        """, (
            ticket_row["id"],
        )).fetchall()
    finally:
        conn.close()

    ticket = _public_ticket_from_row(ticket_row)

    messages = [
        {
            "id": row["id"],
            "author_name": row["author_name"],
            "author_role": row["author_role"],
            "is_team_response": row["author_role"] == "admin",
            "is_official_answer": row["id"] == ticket_row["official_message_id"],
            "body_markdown": row["body_markdown"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in message_rows
    ]

    return {
        "ticket": ticket,
        "messages": messages,
    }


def add_public_message(
    *,
    slug,
    author_name,
    author_email,
    body_markdown,
):
    clean_slug = _clean_required_text(
        slug,
        field_label="slug",
        max_length=255,
    )
    clean_author_name = _clean_required_text(
        author_name,
        field_label="author_name",
        max_length=MAX_AUTHOR_NAME_LENGTH,
    )
    clean_author_email = _clean_email(author_email)
    clean_body = _clean_required_text(
        body_markdown,
        field_label="body_markdown",
        max_length=MAX_MESSAGE_LENGTH,
    )

    now = _now_iso()

    conn = get_connection()
    cur = conn.cursor()

    try:
        ticket_row = cur.execute("""
            SELECT id, status
            FROM tickets
            WHERE slug = ?
              AND visibility = 'public'
            LIMIT 1
        """, (
            clean_slug,
        )).fetchone()

        if ticket_row is None:
            raise TicketNotFoundError("Ticket public introuvable.")

        if ticket_row["status"] == "closed":
            raise TicketClosedError(
                "Ce ticket est clos et ne peut plus recevoir de réponse publique."
            )

        cur.execute("""
            INSERT INTO ticket_messages (
                ticket_id,
                author_name,
                author_email,
                author_role,
                body_markdown,
                visibility,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'public', ?, 'public', ?, NULL)
        """, (
            ticket_row["id"],
            clean_author_name,
            clean_author_email,
            clean_body,
            now,
        ))

        cur.execute("""
            UPDATE tickets
            SET updated_at = ?,
                last_activity_at = ?
            WHERE id = ?
        """, (
            now,
            now,
            ticket_row["id"],
        ))

        conn.commit()
    finally:
        conn.close()

    return get_public_ticket(clean_slug)
