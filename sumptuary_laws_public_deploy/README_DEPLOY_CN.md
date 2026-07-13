# 英国禁奢法数据库公网部署说明

这个文件夹是可部署版本，用于把本地 Streamlit 数据库发布成一个所有人都能打开的网址。

## 文件说明

- `app.py`：数据库网页应用
- `sumptuary_laws.db`：SQLite 数据库
- `requirements.txt`：Python 依赖
- `packages.txt`：云端系统依赖，主要用于 PDF 页面渲染
- `.streamlit/config.toml`：Streamlit 云端配置

## 推荐方式：Streamlit Community Cloud

1. 新建一个 GitHub 仓库。
2. 把本文件夹里的所有文件上传到仓库根目录。
3. 打开 https://share.streamlit.io/ 或 Streamlit Community Cloud。
4. 选择该 GitHub 仓库。
5. Main file path 填：

```text
app.py
```

6. 点击 Deploy。
7. 部署成功后，会得到一个 `https://...streamlit.app` 链接，其他人可以直接打开。

## 重要限制

当前数据库主体、检索、年度分析、表格导出都可以随应用一起上线。

但是“原文图文浏览”里的 PDF 原页截图依赖原始 PDF 文件。当前数据库中部分 PDF 路径仍指向你电脑本地的 `D:\download\Zotero\...`，云端无法访问这些本地路径。因此：

- OCR/文本层内容可以显示；
- 已经保存到项目内的截图可以显示；
- 没有随项目上传的 PDF 原页，云端无法重新渲染截图。

如果你希望在线版也完整显示 PDF 原页截图，需要把相关 PDF 或预渲染截图一并放入部署文件夹，并更新数据库中的路径。

## 本地测试命令

```powershell
cd path\to\sumptuary_laws_public_deploy
python -m streamlit run app.py --server.port 8501
```

