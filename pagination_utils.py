from math import ceil


class SimplePagination:
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = max(1, ceil(total / per_page) if total else 1)
        self.has_prev = self.page > 1
        self.has_next = self.page < self.pages
        self.prev_num = self.page - 1 if self.has_prev else None
        self.next_num = self.page + 1 if self.has_next else None


def paginate_items(items, page, per_page):
    page = max(1, page or 1)
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    return SimplePagination(items[start:end], page, per_page, total)
