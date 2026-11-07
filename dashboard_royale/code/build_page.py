"""Rebuild the dashboard: python build_data.py <repo>/data/ data.json && python build_page.py"""
import pathlib
here = pathlib.Path(__file__).parent
t = (here / 'template.html').read_text(encoding='utf-8')
d = (here / 'data.json').read_text(encoding='utf-8').replace('</', '<\\/')
page = t.replace('__DATA__', d)
(here / 'dashboard_royale.html').write_text('<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
    + page.replace('<div class="filters"', '</head><body>\n<div class="filters"', 1) + '\n</body></html>\n', encoding='utf-8')
print('wrote dashboard_royale.html')
