from django import template
from django.template.defaultfilters import linebreaks
from django.utils.safestring import mark_safe


register = template.Library()

RICH_TEXT_HINTS = (
    "<p",
    "<div",
    "<br",
    "<ul",
    "<ol",
    "<li",
    "<table",
    "<img",
    "<blockquote",
    "<h1",
    "<h2",
    "<h3",
    "<h4",
    "<h5",
    "<h6",
)


@register.filter(name="richtext")
def richtext(value):
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if any(hint in lowered for hint in RICH_TEXT_HINTS):
        return mark_safe(text)
    return mark_safe(linebreaks(text))
