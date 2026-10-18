"""Deterministic Excel -> SQLite migration. Never re-seeds from the old Word importer."""
from pathlib import Path
import argparse,hashlib,json,sqlite3,shutil,os
import pandas as pd

ROOT=Path(__file__).resolve().parent
FILES=['English_Research_Database_修订核验版.xlsx','Chinese_Analytical_Table_修订核验版.xlsx','表3表5_原文核验与统计明细.xlsx','第二轮数据修订记录.xlsx','第二轮中文史料与数据审计报告.md','第二轮复算与证据包.zip']
def load(path,sheet):
    return pd.read_excel(path,sheet_name=sheet,engine='openpyxl').fillna('')
def migrate(input_dir,legacy_path):
    input_dir=input_dir.resolve();legacy_path=legacy_path.resolve()
    dest=ROOT/'data/round2';dest.mkdir(parents=True,exist_ok=True)
    manifest={'version':'round2-2026-10-17','rollback_commit':'349c6e80a2bba25a5cbc9a51b8101c06ed8b5d10','inputs':[],'sheets':{},'legacy_database':str(legacy_path.relative_to(ROOT))}
    for name in FILES:
        src=input_dir/name;target=dest/name
        if src.resolve()!=target.resolve():shutil.copy2(src,target)
        manifest['inputs'].append({'file':name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size})
    en,cn,stats,revisions=[dest/name for name in FILES[:4]]
    laws=load(en,'Research_Law_Table');items=load(en,'Research_Item_Table')
    cl=load(cn,'中文法令总表');ci=load(cn,'中文服饰对象表')
    assert laws.law_id.is_unique and items.item_id.is_unique
    assert set(items.law_id)<=set(laws.law_id)
    assert set(cl.law_id)==set(laws.law_id) and ci.English_item_id.is_unique
    assert set(ci.English_item_id)==set(items.item_id)
    laws=laws.merge(cl[['law_id','编号','中文概述']],on='law_id',validate='one_to_one').rename(columns={'编号':'cn_law_id','中文概述':'chinese_summary'})
    items=items.merge(ci[['English_item_id','编号','中文说明']],left_on='item_id',right_on='English_item_id',validate='one_to_one').rename(columns={'编号':'cn_item_id','中文说明':'chinese_translation'}).drop(columns=['English_item_id'])
    features=load(stats,'表3分类特征')
    classes=features.groupby('item_id')['类别'].agg(lambda x:'; '.join(dict.fromkeys(x)))
    items['object_classes']=items.item_id.map(classes).fillna('')
    if 'penalty_type' not in items:items['penalty_type']=items.law_id.map(laws.set_index('law_id').penalty_type)
    sources=laws.drop_duplicates('source_id')[['source_id','source_family','law_year','monarch','source_title','source_type','source_family_research','source_type_research','source_scope_strict','source_type_status']].copy()
    sources['source_reference']=sources.source_id.map(laws.groupby('source_id').source_text_locator.agg(lambda x:'; '.join(dict.fromkeys(v for v in x if v))))
    for col in ['regnal_year','issue_date','place_of_issue','text_language','chinese_translation']:sources[col]=''
    sources['full_text']=sources.source_id.map(laws.groupby('source_id').source_excerpt.agg(lambda x:'数据库规则摘录汇集（不是法令全文）：\n\n'+'\n\n'.join(dict.fromkeys(v for v in x if v))))
    sources['cleaned_text']=sources['full_text'];sources['notes']='来源类型用research字段；原始来源字段保留；来源单元不自动等于独立新法律。'
    temp=ROOT/'sumptuary_laws.round2.tmp.db'
    if temp.exists():temp.unlink()
    with sqlite3.connect(legacy_path) as original,sqlite3.connect(temp) as con:
        original.backup(con)
        manifest['before']={t:con.execute('select count(*) from '+t).fetchone()[0] for t in ['sources','law_rules','regulated_items','preambles','original_text_pages']}
        con.execute('PRAGMA foreign_keys=OFF')
        for table in ['sources','law_rules','regulated_items','notes_or_uncertain_records']:
            con.execute(f'ALTER TABLE {table} RENAME TO legacy_{table}')
        for name,frame in [('sources',sources),('law_rules',laws),('regulated_items',items),('chinese_law_records',cl),('chinese_item_records',ci)]:frame.to_sql(name,con,index=False,if_exists='fail')
        mapping={'audit_relations':'原文关系证据','audit_t3_features':'表3分类特征','audit_t3_rules':'表3规则明细','audit_t3_summary':'表3汇总','audit_t5_decisions':'表5规则判定','audit_t5_units':'表5规范单元','audit_t5_summary':'表5汇总','audit_t5_extended':'表5扩展来源汇总','audit_codebook':'分类代码表'}
        for table,sheet in mapping.items():
            load(stats,sheet).to_sql(table,con,index=False);manifest['sheets'][table]={'file':FILES[2],'sheet':sheet}
        for table,sheet in [('audit_revision_log','修改记录'),('audit_missing_objects','108条缺对象复核')]:
            load(revisions,sheet).to_sql(table,con,index=False);manifest['sheets'][table]={'file':FILES[3],'sheet':sheet}
        pending=laws[laws.text_verification_status!='原文已核验']
        notes=pd.DataFrame({'record_id':['R2-PENDING-'+str(n+1) for n in range(len(pending))],'related_table':'law_rules','related_id':pending.law_id.values,'issue_type':pending.text_verification_status.values,'description':pending.verification_scope.values,'recommended_action':'按原文定位逐字段核验；关系已核不表示全条通过','priority':'待核验'})
        notes.to_sql('notes_or_uncertain_records',con,index=False)
        for table,key in [('sources','source_id'),('law_rules','law_id'),('regulated_items','item_id')]:con.execute(f'CREATE UNIQUE INDEX r2_{table}_id ON {table}({key})')
        # Old supporting evidence retains old IDs, explicitly linked to legacy_sources.
        manifest['auxiliary_scope']='preambles/original_text_pages保留旧版ID与内容，关联legacy_sources；未自动对应第二轮28个来源。'
        manifest['after']={'source_units':len(sources),'rule_records':len(laws),'all_object_records':len(items),'active_object_records':int((pd.to_numeric(items.record_active)==1).sum()),'verified_relation_fragments':con.execute('select count(*) from audit_relations').fetchone()[0],'pending_rule_records':len(pending)}
        con.commit();assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        for table,foreign,parent,key in [('law_rules','source_id','sources','source_id'),('regulated_items','law_id','law_rules','law_id'),('regulated_items','source_id','sources','source_id')]:
            assert con.execute(f'SELECT count(*) FROM {table} a LEFT JOIN {parent} b ON a.{foreign}=b.{key} WHERE b.{key} IS NULL').fetchone()[0]==0
    con.close();original.close()
    os.replace(temp,ROOT/'sumptuary_laws.db')
    manifest['sheets'].update({'law_rules':{'file':FILES[0],'sheet':'Research_Law_Table'},'regulated_items':{'file':FILES[0],'sheet':'Research_Item_Table'},'chinese_law_records':{'file':FILES[1],'sheet':'中文法令总表'},'chinese_item_records':{'file':FILES[1],'sheet':'中文服饰对象表'}})
    manifest['database_sha256']=hashlib.sha256((ROOT/'sumptuary_laws.db').read_bytes()).hexdigest()
    (dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(manifest['after'],ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--legacy',type=Path,required=True);args=p.parse_args();migrate(args.input,args.legacy)
