from pathlib import Path
import sqlite3,json,hashlib,io,zipfile,unittest
import pandas as pd
from streamlit.testing.v1 import AppTest
import round2_data as r2
from bootstrap_round2 import ensure_payload

ROOT=Path(__file__).resolve().parent;DB=ROOT/'sumptuary_laws.db';INPUT=ROOT/'data/round2'
ensure_payload(ROOT)
class MigrationTests(unittest.TestCase):
    def test_offline_payload_reconstruction(self):
        import tempfile,shutil
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp);shutil.copytree(ROOT/'release_chunks',target/'release_chunks')
            ensure_payload(target)
            manifest=json.loads((target/'release_chunks/manifest.json').read_text(encoding='utf8'))
            for name,info in manifest['files'].items():self.assertEqual(hashlib.sha256((target/name).read_bytes()).hexdigest(),info['sha256'])
    def test_counts_and_history(self):
        self.assertEqual(r2.metrics(DB),{'source_units':28,'rule_records':749,'active_objects':1058,'all_objects':1060,'inactive_objects':2,'verified_relation_fragments':184,'pending_rules':749,'pending_active_objects':1058})
        for table,n in [('legacy_sources',67),('legacy_law_rules',808),('legacy_regulated_items',1179),('original_text_pages',1238),('preambles',131)]:self.assertEqual(len(r2.read(DB,table)),n)
    def test_all_excel_cells_and_foreign_keys(self):
        for sheet,table,key in [('Research_Law_Table','law_rules','law_id'),('Research_Item_Table','regulated_items','item_id')]:
            expected=pd.read_excel(INPUT/'English_Research_Database_修订核验版.xlsx',sheet_name=sheet,engine='openpyxl').fillna('').set_index(key)
            with sqlite3.connect(DB) as con:actual=pd.read_sql_query('select * from '+table,con).fillna('').set_index(key)
            self.assertEqual(set(expected.index),set(actual.index))
            for col in expected:
                a=actual.loc[expected.index,col];b=expected[col]
                self.assertTrue(a.eq(b).all(),f'{table}.{col} mismatch')
        with sqlite3.connect(DB) as con:
            self.assertEqual(con.execute('pragma integrity_check').fetchone()[0],'ok')
            for sql in ['select count(*) from regulated_items i left join law_rules l using(law_id) where l.law_id is null','select count(*) from law_rules l left join sources s using(source_id) where s.source_id is null','select count(*) from regulated_items i join law_rules l using(law_id) where i.source_id!=l.source_id or i.law_year!=l.law_year']:
                self.assertEqual(con.execute(sql).fetchone()[0],0)
    def test_thresholds_and_source_types(self):
        laws=r2.read(DB,'law_rules').set_index('law_id');items=r2.read(DB,'regulated_items',True)
        expected={'EDW-III-1363-STAT-04':'land/rent annual income >= GBP 200','EDW-III-1363-STAT-08':'land/rent annual income <= 200 marks','EDW-III-1363-STAT-06':'goods > GBP 1000; comparator annual land/rent GBP 200'}
        for lid,value in expected.items():
            self.assertEqual(laws.loc[lid,'research_threshold'],value)
            self.assertTrue(items.loc[items.law_id.eq(lid),'research_threshold'].eq(value).all())
            self.assertTrue(laws.loc[lid,'french_threshold'])
        sources=r2.read(DB,'sources').set_index('source_id')
        self.assertEqual(sources.loc['ELIZ-I-1562-PROC-493','source_family'],'Privy Council Articles')
        self.assertEqual(sources.loc['ELIZ-I-1562-PC-496','source_family'],'Statutory Abstract')
        self.assertEqual(len(set(sources.source_family)),4)
    def test_active_filters_and_classification(self):
        active=r2.read(DB,'regulated_items');raw=r2.read(DB,'regulated_items',True)
        retired={'EDW-IV-1463-STAT-ITEM-006','HEN-VIII-1510-STAT-ITEM-013'}
        self.assertFalse(retired.intersection(active.item_id));self.assertTrue(retired<=set(raw.item_id))
        silk=r2.filter_values(active,'material',['silk'],True)
        self.assertTrue(all('silk' in r2.tokens(v) for v in silk.material))
        self.assertTrue(any(';' in v for v in silk.material))
        f=r2.read(DB,'audit_t3_features');forms=r2.feature_counts(active,f,'FORM')
        self.assertFalse(forms.value.isin(['girdle','garter','horse harness','lining','sleeve']).any())
    def test_statistics_independently_from_relations(self):
        relations=r2.read(DB,'audit_relations');summ=r2.read(DB,'audit_t5_summary')
        for _,row in summ.iterrows():
            cat=row['组合'];attr=relations.garment_form if cat=='材料与服装形制' else relations.colour if cat=='材料与颜色' else relations.garment_part.fillna('')+relations.body_part.fillna('')
            rr=relations[relations.material.fillna('').ne('') & attr.fillna('').ne('') & relations.nonhuman_object.fillna('').eq('') & relations.source_scope_strict.eq(1)]
            self.assertEqual(row['已核规范单元下限'],len(rr[['source_id','normative_unit_id']].drop_duplicates()))
            self.assertEqual(row['已核来源单元'],rr.source_id.nunique())
            self.assertEqual(row['已核law_id覆盖'],rr.law_id.nunique())
            self.assertTrue(pd.isna(row['最终总数']) or row['最终总数']=='')
        self.assertEqual(summ['已核规范单元下限'].tolist(),[78,26,27])
    def test_download_hashes_and_generated_exports(self):
        m=json.loads((INPUT/'manifest.json').read_text(encoding='utf8'))
        for item in m['inputs']:self.assertEqual(hashlib.sha256((INPUT/item['file']).read_bytes()).hexdigest(),item['sha256'])
        n,e=r2.network_frames(r2.read(DB,'regulated_items'))
        self.assertFalse(e.duplicated(['Source','Target']).any());self.assertTrue(set(e.Source)|set(e.Target)<=set(n.Id))
        for data in [r2.zip_frames({'nodes.csv':n,'edges.csv':e}),r2.voyant_bytes(r2.read(DB,'sources'))[1]]:
            with zipfile.ZipFile(io.BytesIO(data)) as z:self.assertIsNone(z.testzip())

class PageTests(unittest.TestCase):
    def app(self,page='首页'):
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60).run()
        if page!='首页':at.sidebar.radio[0].set_value(page).run()
        self.assertEqual([e.message for e in at.exception],[],page)
        return at
    def test_all_existing_pages(self):
        for page in ['首页','关键词检索','高级检索','浏览来源','浏览服饰/材料对象','序言证据','原文图文浏览','分析面板','关系网络图','网络文件导出','Voyant 语料导出','数据质量']:
            with self.subTest(page=page):self.app(page)
    def test_home_distinguishes_units(self):
        at=self.app();self.assertEqual({m.label:m.value for m in at.metric},{'来源单元数':'28','规则记录数':'749','有效对象记录数':'1058','已核原文关系片段（含辅助来源）':'184','待核验规则记录数':'749','待核验有效对象记录数':'1058'})
    def test_key_record_search_and_language(self):
        at=self.app('关键词检索');at.text_input[0].set_value('EDW-III-1363-STAT-04').run()
        self.assertEqual(len(at.exception),0)
        self.assertTrue(any('research_threshold' in x.value.columns or '研究采用门槛' in x.value.columns for x in at.dataframe))
        at.sidebar.selectbox[0].set_value('English').run();self.assertEqual(len(at.exception),0)
        law=at.dataframe[0].value
        self.assertEqual(law.iloc[0].research_threshold,'land/rent annual income >= GBP 200')
    def test_income_material_filter_and_empty_results(self):
        at=self.app('高级检索')
        income=next(w for w in at.text_input if w.label=='研究采用门槛关键词');income.set_value('GBP 200').run()
        self.assertEqual(len(at.exception),0)
        data=at.dataframe[0].value
        col='研究采用门槛' if '研究采用门槛' in data else 'research_threshold'
        self.assertTrue(data[col].str.contains('GBP 200',case=False,regex=False).all())
        next(w for w in at.text_input if w.label=='研究采用门槛关键词').set_value('NO_SUCH_THRESHOLD').run()
        self.assertEqual(len(at.exception),0);self.assertTrue(at.dataframe[0].value.empty)
        at=self.app('高级检索')
        next(w for w in at.multiselect if w.label=='材料').set_value(['silk']).run()
        self.assertEqual(len(at.exception),0)
        df=at.dataframe[0].value
        self.assertTrue(all('silk' in r2.tokens(x) for x in df['材料']))
    def test_original_french_image_and_downloads(self):
        at=self.app('浏览来源')
        next(w for w in at.selectbox if w.label=='打开来源记录').set_value('EDW-III-1363-STAT').run()
        self.assertEqual(len(at.exception),0);self.assertTrue(len(at.get('imgs')) or any('p381' in x.value for x in at.caption))
        at=self.app('数据质量');self.assertGreaterEqual(len(at.get('download_button')),8)

if __name__=='__main__':unittest.main(verbosity=2)
