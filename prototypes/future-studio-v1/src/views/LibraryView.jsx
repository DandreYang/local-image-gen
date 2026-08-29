import { useRef, useState } from "react";
import { ArrowsOutSimple, FolderSimple, Star, Trash, UploadSimple, X } from "@phosphor-icons/react";
import { Header } from "../components/Header.jsx";
import { StageLabel } from "../components/StageLabel.jsx";
import { PageAlert } from "../components/PageAlert.jsx";
import { useDialogFocus } from "../hooks/useDialogFocus.js";
import { apiAssetUrl, apiThumbUrl } from "../studio-api.js";
import { groupLibraryItems, imageFactLabel, libraryItemTitle } from "../studio-options.js";
import { cssRatio } from "../studio-helpers.js";

export function LibraryView({ items, loading, onImport, onBack, onOpen, onToggleFavorite, onTrash, ready, backendState, pending, running, fixture, error }) {
  const inputRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const [query, setQuery] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const dialogRef = useRef(null);
  const normalizedQuery = query.trim().toLowerCase();
  const filteredItems = items.filter((item) => {
    if (favoritesOnly && !item.starred) return false;
    if (!normalizedQuery) return true;
    return [libraryItemTitle(item), item.prompt_original, item.prompt_used, item.provider, item.model]
      .some((value) => String(value || "").toLowerCase().includes(normalizedQuery));
  });
  const groups = groupLibraryItems(filteredItems);
  useDialogFocus(() => setPreview(null), dialogRef, Boolean(preview));
  function trash(item) {
    const title = libraryItemTitle(item);
    if (!window.confirm(`把“${title}”移到回收站？原图和生成记录会一起移走，可在本机素材库的 .trash 目录找回。`)) return;
    onTrash(item);
  }
  return (
    <main className="studio-view library-view" data-view="library">
      <div className="library-background" inert={preview ? true : undefined} aria-hidden={preview ? "true" : undefined}>
        <Header onHome={onBack} onLibrary={() => {}} ready={ready} backendState={backendState} pending={pending} running={running} fixture={fixture} disabled={loading} compact />
        <section className="library-stage">
          <div className="library-heading"><div><StageLabel>LOCAL LIBRARY</StageLabel><h1>素材库</h1></div><input ref={inputRef} className="visually-hidden" type="file" accept="image/png,image/jpeg" multiple aria-label="导入图片" onChange={(event) => onImport(event.target.files)} tabIndex={-1} /><button className="secondary-action" type="button" onClick={() => inputRef.current?.click()} disabled={loading}><UploadSimple size={18} aria-hidden="true" />{loading ? "正在导入…" : "导入图片"}</button></div>
          <div className="library-tools">
            <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索提示词、模型或通路" aria-label="搜索素材" />
            <button type="button" className={favoritesOnly ? "active" : ""} aria-pressed={favoritesOnly} onClick={() => setFavoritesOnly((value) => !value)}><Star size={17} weight={favoritesOnly ? "fill" : "regular"} aria-hidden="true" />只看收藏</button>
            <span>{filteredItems.length} / {items.length} 张</span>
          </div>
          {!items.length ? <div className="library-empty"><FolderSimple size={48} weight="light" aria-hidden="true" /><h2>这里还没有作品</h2><p>生成、修改或导入的图片都会安全地留在本机。</p><button className="primary-action" type="button" onClick={onBack}>开始第一张</button></div>
            : !filteredItems.length ? <div className="library-empty"><FolderSimple size={48} weight="light" aria-hidden="true" /><h2>没有匹配的作品</h2><p>换个关键词，或关闭“只看收藏”。</p><button className="secondary-action" type="button" onClick={() => { setQuery(""); setFavoritesOnly(false); }}>清除筛选</button></div>
              : groups.map((group) => (
                <section className="library-group" key={group.key} aria-labelledby={`library-group-${group.key}`}>
                  <h2 id={`library-group-${group.key}`}>{group.title}</h2>
                  <div className="library-grid">{group.items.map((item) => {
                    const title = libraryItemTitle(item);
                    return <article key={item.id}><div className="library-thumb" style={{ aspectRatio: cssRatio(item.aspect_ratio) }}><img src={apiThumbUrl(item.url || item.id)} alt={title} loading="lazy" decoding="async" />{item.parent ? <span className="version-badge" aria-label="改稿版本">改稿版</span> : null}</div><div><strong title={item.prompt_original || title}>{title}</strong><span>{item.provider || "本机"} · {imageFactLabel(item)}</span></div><button className={`favorite-library-item ${item.starred ? "active" : ""}`} type="button" aria-label={`${item.starred ? "取消收藏" : "收藏"}${title}`} aria-pressed={Boolean(item.starred)} onClick={() => onToggleFavorite(item)} disabled={loading}><Star size={18} weight={item.starred ? "fill" : "regular"} aria-hidden="true" /></button><button className="open-library-item" type="button" aria-label={`打开${title}`} onClick={() => onOpen(item)}><ArrowsOutSimple size={18} aria-hidden="true" /></button><button className="preview-library-item" type="button" onClick={() => setPreview(item)}>预览</button><button className="trash-library-item" type="button" aria-label={`移到回收站：${title}`} onClick={() => trash(item)} disabled={loading}><Trash size={18} aria-hidden="true" /></button></article>;
                  })}</div>
                </section>
              ))}
        </section>
        <PageAlert message={error} />
      </div>
      {preview && <div ref={dialogRef} className="library-lightbox" role="dialog" aria-modal="true" aria-label={`预览${libraryItemTitle(preview)}`}><button className="icon-button" type="button" onClick={() => setPreview(null)} aria-label="关闭预览"><X size={22} aria-hidden="true" /></button><img src={apiAssetUrl(preview.url || preview.id)} alt={libraryItemTitle(preview)} /><p>{libraryItemTitle(preview)}</p></div>}
    </main>
  );
}
