python3 - <<'PY'
from pypdf import PdfReader
p='/root/submission/pdfwf_005_closeout_binder_page_labels_and_bookmarks_seed.pdf'
r=PdfReader(p)
print('pages', len(r.pages))
print('page_labels', r.page_labels)
print('outline entries:')
for item in r.outline:
    if isinstance(item, list):
        print('  nested:', [str(x.title) for x in item])
    else:
        print(' ', repr(item.title), 'page_index', r.get_destination_page_number(item))
print('named_destinations', list(r.named_destinations))
PY