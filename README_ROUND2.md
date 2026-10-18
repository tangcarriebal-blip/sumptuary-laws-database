# 第二轮线上更新说明

目标入口为仓库根目录 `app.py`，分支 `main`。代码链接本身不等于 Streamlit Cloud 的主文件配置；上线时必须确认该配置并检查页面版本标记 `round2-2026-10-17`。未看到版本标记前，不宣称线上更新已生效。

## 数据与追溯

- 输入六份交付资料保存在 `data/round2/`，文件SHA256、实际工作表及迁移前后数量见 `manifest.json`。
- 版本库以`release_chunks/`保存数据库和六份资料的离线分块包。`bootstrap_round2.py`在启动时校验SHA256并重建原字节文件，不从互联网临时下载，也不改写Excel；重建文件被Git忽略，原二进制资料仍完整包含在发布包中。重建损坏会报错，不回退到旧数据。
- SQLite主表：`sources` 28行、`law_rules` 749行、`regulated_items` 1060行。其中 `record_active=1` 的1058行进入正式检索、图表和当前网络导出，另外2行在数据质量页保留。
- `legacy_sources`、`legacy_law_rules`、`legacy_regulated_items`、`legacy_notes_or_uncertain_records`完整保留迁移前数据。原子目录及其数据库和程序未覆盖。
- `preambles`和`original_text_pages`继续使用原编号并关联旧来源；没有猜测映射到新28来源。旧版原文页面、序言的逐条对应仍待核验。
- 原门槛字段保留含义和值；正式显示和收入筛选优先使用`research_threshold`。1363法文、英译、采用理由和状态分别保留，不自动换算英镑和马克。
- 来源展示使用`source_family_research`／`source_type_research`；原值显示为追溯字段。No493枢密院执行条款与No496法令摘要不并作同质王室公告。
- 表3为字段层库存；表5严格口径的78／26／27是保守已核下限，分别涉及13／9／10来源单元，不是全库最终总数。扩展来源的86／29／30另列。184是原文关系片段数，不能当作184条独立法规。

## 程序和功能

保持原12个页面：检索、浏览、序言、原文页面、分析、关系图、网络导出、Voyant和数据质量。收入筛选用研究采用值；材料等多值字段按分号拆分匹配。分类图使用正式分类特征，衣物部件、饰物和非人体对象不回流为服装形制；身体部位筛选仅明示人体字段。

旧网络图默认隐藏，说明旧版口径；历史查看选项保留原交互显示。当前网络CSV按群体—对象的不同law_id去重。Voyant导出为当前规则摘录汇集，明确标为非原文全文。资料下载包含全部六份输入文件和迁移前SQLite快照。

缓存键包含明确数据版本、SQLite修改时间（纳秒）和文件大小；表存在性直接检查，避免旧缓存隐藏新表。依赖在根`requirements.txt`，PDF系统依赖在`packages.txt`。

## 重建和测试

```text
python migrate_round2.py --input /path/to/second_round_files --legacy sumptuary_laws_public_deploy/sumptuary_laws_public_deploy_updated_1463_1482_title/sumptuary_laws.db
python test_round2.py
streamlit run app.py
```

迁移使用SQLite备份及原子文件替换，不调用旧Word自动导入器；失败不把半成品覆盖为正式库。所有新规则、对象字段与修订Excel逐列比较；测试从关系证据重建表5集合，并测试12页面、收入／材料／空结果、中英文标签、法文印本图、下载和导出ZIP。

只有修改过迁移结果或六份输入资料时才运行`python build_release.py`重新生成分块包，随后重新执行测试。应用和测试启动时均自动离线重建；不需要先运行旧导入脚本。

本地已验证 Streamlit 1.66.0、pandas 3.0.6、Plotly 7.1.0、Python 3.12。测试输出保存在随交付提供的本地测试日志。

## 发布及回退

只在测试通过后推送。应用须配置为该仓库`main`分支、根`app.py`。发布后检查版本标记、首页28／749／1058、1363三条门槛、No493／496及表5下限；缺少任何在线检查结果均只能写“待线上验证”。

迁移前Git版本：`349c6e80a2bba25a5cbc9a51b8101c06ed8b5d10`。优先使用`git revert <本次发布提交>`生成回退提交，保留历史；原子目录也始终保留迁移前SQLite。恢复旧版时还应恢复其原Streamlit入口配置，不能假定旧根入口旁原本存在数据库。
