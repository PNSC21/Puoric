import re
import unicodedata

from flask import request


def slugify(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-")


def form_value(name, required=False, maximum=255):
    value = request.form.get(name, "").strip()
    if required and not value:
        raise ValueError(f"{name.replace('_', ' ').capitalize()} is required.")
    if len(value) > maximum:
        raise ValueError(f"{name.replace('_', ' ').capitalize()} is too long.")
    return value or None


def positive_int(name, default=0):
    value = request.form.get(name, str(default)).strip()
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(
            f"{name.replace('_', ' ').capitalize()} must be a whole number."
        ) from exc
    if parsed < 0:
        raise ValueError(f"{name.replace('_', ' ').capitalize()} cannot be negative.")
    return parsed


def parse_pairs(value):
    pairs = []
    for line in value.splitlines():
        if not line.strip():
            continue
        name, separator, detail = line.partition("=")
        if not separator or not name.strip() or not detail.strip():
            raise ValueError("Enter one name=value pair on each line.")
        pairs.append((name.strip(), detail.strip()))
    return pairs