from django import template


register = template.Library()


@register.filter
def vnd(value):
    try:
        amount = int(value or 0)
    except (TypeError, ValueError):
        return "0 đ"

    return f"{amount:,}".replace(",", ".") + " đ"
