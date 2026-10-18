from pathlib import Path
from streamlit.testing.v1 import AppTest
app=Path(__file__).resolve().parent / 'sumptuary_laws_public_deploy' / 'app.py'
a=AppTest.from_file(str(app),default_timeout=45).run()
assert not a.exception, str(a.exception)
assert [x.value for x in a.metric][:3]==['28','749','1058'], [x.value for x in a.metric]
menu=next(x for x in a.sidebar.radio if x.label=='页面')
assert len(menu.options)==11
for page in menu.options:
 a=AppTest.from_file(str(app),default_timeout=45).run()
 next(x for x in a.sidebar.radio if x.label=='页面').set_value(page).run()
 assert not a.exception, (page,str(a.exception))
print('PASS: nested Cloud entry, 11 pages, version and 28/749/1058')

