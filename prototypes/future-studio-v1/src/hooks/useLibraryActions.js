import { patchReceipt, trashItem, uploadReferences } from "../studio-api.js";

/**
 * Library mutations (import, favourite, trash). Each one is guarded by the
 * shared operation counter so a stale response cannot overwrite newer state.
 */
export function useLibraryActions({ ops, setLoading, setError, setLibraryItems, refreshLibrary, onTrashed }) {
  async function run(action) {
    const operationId = ops.begin();
    setLoading(true);
    setError("");
    try {
      await action(operationId);
    } catch (cause) {
      if (ops.isCurrent(operationId)) setError(cause.message || String(cause));
    } finally {
      if (ops.isCurrent(operationId)) setLoading(false);
    }
  }

  function importFiles(files) {
    return run(async (operationId) => {
      await uploadReferences(files);
      if (!ops.isCurrent(operationId, "library")) return;
      await refreshLibrary();
    });
  }

  function toggleFavorite(item) {
    if (!item?.id) return Promise.resolve();
    return run(async (operationId) => {
      const payload = await patchReceipt({ id: item.id, starred: !item.starred });
      if (!ops.isCurrent(operationId, "library")) return;
      const updated = payload.item;
      setLibraryItems((rows) => rows.map((row) => (row.id === updated.id ? updated : row)));
    });
  }

  function removeLibraryItem(item) {
    if (!item?.id) return Promise.resolve();
    return run(async (operationId) => {
      await trashItem(item.id);
      if (!ops.isCurrent(operationId, "library")) return;
      setLibraryItems((rows) => rows.filter((row) => row.id !== item.id));
      onTrashed?.(item);
    });
  }

  return { importFiles, toggleFavorite, removeLibraryItem };
}
