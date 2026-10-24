// Read-only view over the host's material records; never writes or duplicates originals.
export function visibleDoc(state,doc,projectId=state.currentProject){return doc.projectId===projectId||(state.libraryRefs||[]).some(ref=>ref.projectId===projectId&&ref.materialId===(doc.materialId||doc.id));}
export function latestDocs(state){return (state.docs||[]).filter(doc=>!doc.supersededBy);}
