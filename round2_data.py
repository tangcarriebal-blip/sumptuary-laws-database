"""Read-only presentation and aggregation for the audited release."""
from pathlib import Path
import sqlite3,re,io,zipfile
import pandas as pd

VERSION='round2-2026-10-17'
LABELS={'research_threshold':'研究采用门槛','french_threshold':'法文原始门槛摘录','english_threshold':'英译门槛读数','threshold_adoption_basis':'采用依据','variant_note':'异文说明','threshold_text_status':'门槛校勘状态','text_verification_status':'全记录核验状态','field_check_status':'字段检查状态','verification_scope':'核验范围','source_text_locator':'原文定位','record_active':'对象有效标记','record_role':'记录用途','relation_id':'关系证据编号','source_family_research':'研究来源类型','source_type_research':'研究文书类型','source_scope_strict':'严格来源口径纳入','source_type_status':'来源类型核验状态','source_family_legacy':'旧来源分类（追溯）','source_type_legacy':'旧文书类型（追溯）','rule_function_legacy':'旧主功能（追溯）','legal_action_research':'研究法律行为','object_classes':'正式对象分类','garment_part_explicit':'明示衣物部件','body_part_explicit':'明示人体部位','body_location':'旧身体部位（含推断）','body_location_inferred':'旧部位／衣名推断','eligibility_threshold_normalized':'旧门槛规范化（追溯）','eligibility_threshold_original':'旧门槛原读数（追溯）','cn_law_id':'中文规则编号','cn_item_id':'中文对象编号','construction_process':'制作处理方式（非部位）','eligibility_limit_separated':'分离的资格门槛','cloth_price_separated':'分离的布价','object_price_separated':'分离的对象价格','quantity_limit_separated':'分离的用量或尺寸'}

def stamp(db):
    s=Path(db).stat();return (VERSION,s.st_mtime_ns,s.st_size)

def read(db,table,include_inactive=False):
    with sqlite3.connect(db) as con:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():raise ValueError('Unknown table: '+table)
        df=pd.read_sql_query('SELECT * FROM "'+table.replace('"','""')+'"',con)
    con.close()
    if table=='regulated_items' and not include_inactive:df=df[pd.to_numeric(df.record_active,errors='coerce').eq(1)].copy()
    for col in ['source_family','source_type']:
        research=col+'_research'
        if research in df:
            df[col+'_legacy']=df[col] if col in df else '';df[col]=df[research]
    return df

def tokens(value):
    return [s.strip() for s in re.split(r';|；',str(value or '')) if s.strip().lower() not in {'','none','nan','not specified','unclear','not_applicable'}]

def filter_values(df,col,selected,multiple=False):
    if not selected:return df
    wanted=set(selected)
    return df[df[col].map(lambda x:bool(wanted.intersection(tokens(x))))] if multiple else df[df[col].astype(str).isin(selected)]

def metrics(db):
    laws=read(db,'law_rules');items=read(db,'regulated_items');raw=read(db,'regulated_items',True);rel=read(db,'audit_relations')
    return {'source_units':len(read(db,'sources')),'rule_records':len(laws),'active_objects':len(items),'all_objects':len(raw),'inactive_objects':len(raw)-len(items),'verified_relation_fragments':int(rel.status.eq('原文已核验').sum()),'pending_rules':int(laws.text_verification_status.ne('原文已核验').sum()),'pending_active_objects':int(items.text_verification_status.ne('原文已核验').sum())}

def network_frames(items):
    base=items[['law_id','regulated_group_standardized','item_name_normalized']].dropna().drop_duplicates()
    base=base[base.regulated_group_standardized.astype(str).str.strip().ne('') & base.item_name_normalized.astype(str).str.strip().ne('')]
    edges=base.groupby(['regulated_group_standardized','item_name_normalized']).law_id.nunique().reset_index(name='Weight')
    edges['Source']='group:'+edges.regulated_group_standardized.astype(str);edges['Target']='item:'+edges.item_name_normalized.astype(str);edges['Type']='Undirected'
    nodes=pd.DataFrame([{'Id':'group:'+str(x),'Label':str(x),'Kind':'group'} for x in sorted(base.regulated_group_standardized.unique())]+[{'Id':'item:'+str(x),'Label':str(x),'Kind':'item'} for x in sorted(base.item_name_normalized.unique())])
    return nodes,edges[['Source','Target','Weight','Type']]

def feature_counts(items,features,code):
    selected=features[features.item_id.isin(items.item_id) & features.class_code.eq(code)]
    return selected.drop_duplicates(['item_id','原字段值']).groupby('原字段值').item_id.nunique().sort_values(ascending=False).head(20).rename_axis('value').reset_index(name='count')

def zip_frames(frames):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for name,df in frames.items():z.writestr(name,df.to_csv(index=False).encode('utf-8-sig'))
    return stream.getvalue()

def voyant_bytes(sources):
    buf=io.BytesIO();rows=[]
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for row in sources.itertuples():
            name=f'{row.source_id}.txt';text=str(row.full_text or '')
            z.writestr('rule_excerpts/'+name,text)
            rows.append({'source_id':row.source_id,'year':row.law_year,'source_family':row.source_family,'file':name,'scope':'规则摘录汇集，非原法令全文'})
        meta=pd.DataFrame(rows);z.writestr('voyant_metadata.csv',meta.to_csv(index=False).encode('utf-8-sig'))
    return meta,buf.getvalue()
