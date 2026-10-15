(() => {
  "use strict";
  const form = document.getElementById("price-form");
  const owner = document.body.dataset.userId;
  const DB = "wikonomi-contributions-v1";
  const STORE = "drafts";

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/app/sw.js", {scope: "/app/"})
        .catch(() => {}); // Installation is optional; uploads still work without it.
    });
  }

  function openDb() {
    return new Promise((resolve, reject) => {
      if (!window.indexedDB) return reject(new Error("Offline storage unavailable"));
      const req = indexedDB.open(DB, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE, {keyPath: "id"});
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function dbAction(mode, fn) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const request = fn(tx.objectStore(STORE));
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      tx.oncomplete = () => db.close();
      tx.onerror = () => reject(tx.error);
    });
  }

  function owned(draft) { return draft.owner === owner; }
  async function listDrafts() {
    return (await dbAction("readonly", store => store.getAll())).filter(owned);
  }
  async function removeDraft(id) {
    const draft = await dbAction("readonly", store => store.get(id));
    if (draft && owned(draft)) {
      await dbAction("readwrite", store => store.delete(id));
    }
  }

  const completedId = new URLSearchParams(location.search).get("created");
  if (completedId) removeDraft(completedId).catch(() => {});

  const draftCount = document.getElementById("draft-count");
  const draftList = document.getElementById("drafts-list");
  if (draftCount && draftList) {
    listDrafts().then(drafts => {
      draftCount.textContent = drafts.length;
      draftList.replaceChildren();
      if (!drafts.length) {
        const message = document.createElement("p");
        message.className = "muted";
        message.textContent = "No saved drafts.";
        draftList.append(message);
      }
      for (const draft of drafts) {
        const row = document.createElement("div");
        row.className = "draft-row";
        const text = document.createElement("div");
        const strong = document.createElement("strong");
        strong.textContent = draft.productLabel || "Untitled price";
        const small = document.createElement("small");
        small.textContent = "K" + (draft.price || "—") + " · " + (draft.branchLabel || "No shop");
        text.append(strong, small);
        const actions = document.createElement("div");
        actions.className = "draft-actions";
        const edit = document.createElement("button");
        edit.type = "button";
        edit.textContent = "Open";
        edit.addEventListener("click", () => {
          location.href = "/app/submit/?draft=" + encodeURIComponent(draft.id);
        });
        const remove = document.createElement("button");
        remove.type = "button";
        remove.textContent = "Delete";
        remove.addEventListener("click", async () => {
          await removeDraft(draft.id);
          row.remove();
          draftCount.textContent = String(Math.max(0, Number(draftCount.textContent) - 1));
        });
        actions.append(edit, remove);
        row.append(text, actions);
        draftList.append(row);
      }
    }).catch(() => {
      draftCount.textContent = "—";
      draftList.textContent = "Offline drafts are unavailable on this browser.";
    });
  }

  if (!form) return;
  const uuidInput = document.getElementById("id_client_submission_id");
  const observedInput = document.getElementById("id_observed_at");
  const photoInput = document.getElementById("id_photo");
  const preview = document.getElementById("photo-preview");
  const status = document.getElementById("draft-status");
  let previewUrl;
  if (!observedInput.value) observedInput.value = new Date().toISOString();

  function showPreview(file) {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    if (file) {
      previewUrl = URL.createObjectURL(file);
      preview.src = previewUrl;
      preview.hidden = false;
    } else {
      preview.hidden = true;
    }
  }

  async function compressPhoto(input) {
    const original = input.files[0];
    if (!original || !("createImageBitmap" in window)) return;
    try {
      const bitmap = await createImageBitmap(original);
      const scale = Math.min(1, 1400 / Math.max(bitmap.width, bitmap.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(bitmap.width * scale);
      canvas.height = Math.round(bitmap.height * scale);
      canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      bitmap.close();
      const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.79));
      if (!blob || blob.size >= original.size) return;
      const dt = new DataTransfer();
      dt.items.add(new File([blob], "price-evidence.jpg", {type: "image/jpeg"}));
      input.files = dt.files;
    } catch (_) {
      // Keep the original image if conversion isn't supported.
    }
  }

  photoInput.addEventListener("change", async () => {
    if (photoInput.files[0]) {
      observedInput.value = new Date().toISOString();
      await compressPhoto(photoInput);
    }
    showPreview(photoInput.files[0]);
  });

  document.querySelectorAll(".autocomplete").forEach(wrapper => {
    const input = wrapper.querySelector("input");
    const results = wrapper.querySelector(".suggestions");
    const hidden = document.getElementById(wrapper.dataset.hiddenId);
    let timer = null;
    let controller = null;

    input.addEventListener("input", () => {
      hidden.value = "";
      results.hidden = true;
      clearTimeout(timer);
      if (controller) controller.abort();
      const query = input.value.trim();
      if (query.length < 2) return;
      timer = setTimeout(async () => {
        controller = new AbortController();
        try {
          const response = await fetch(
            wrapper.dataset.searchUrl + "?q=" + encodeURIComponent(query),
            {signal: controller.signal, credentials: "same-origin"}
          );
          if (!response.ok || !response.headers.get("content-type")?.includes("json")) return;
          const body = await response.json();
          results.replaceChildren();
          if (!body.results.length) {
            const p = document.createElement("p");
            p.textContent = "No matches. Try a different name.";
            results.append(p);
          }
          for (const item of body.results) {
            const button = document.createElement("button");
            button.type = "button";
            button.setAttribute("role", "option");
            button.textContent = item.name;
            button.addEventListener("click", () => {
              hidden.value = item.id;
              input.value = item.name;
              results.hidden = true;
            });
            results.append(button);
          }
          results.hidden = false;
        } catch (err) {
          if (err.name !== "AbortError") results.hidden = true;
        }
      }, 220);
    });
    input.addEventListener("blur", () => setTimeout(() => { results.hidden = true; }, 170));
  });

  function currentDraft() {
    return {
      id: uuidInput.value,
      owner,
      product: document.getElementById("id_product").value,
      productLabel: document.getElementById("product-search").value,
      branch: document.getElementById("id_business_branch").value,
      branchLabel: document.getElementById("branch-search").value,
      price: document.getElementById("id_price").value,
      observedAt: observedInput.value,
      photo: photoInput.files[0] || null,
      savedAt: new Date().toISOString(),
    };
  }

  async function saveDraft() {
    const draft = currentDraft();
    await dbAction("readwrite", store => store.put(draft));
    status.textContent = "✓ Draft saved on this device. Submit when connected.";
  }

  document.getElementById("save-draft").addEventListener("click", async () => {
    try { await saveDraft(); }
    catch (_) { status.textContent = "Could not save draft on this device."; }
  });

  const requestedDraft = new URLSearchParams(location.search).get("draft");
  if (requestedDraft) {
    dbAction("readonly", store => store.get(requestedDraft)).then(draft => {
      if (!draft || !owned(draft)) return;
      uuidInput.value = draft.id;
      observedInput.value = draft.observedAt || new Date().toISOString();
      document.getElementById("id_product").value = draft.product;
      document.getElementById("product-search").value = draft.productLabel;
      document.getElementById("id_business_branch").value = draft.branch;
      document.getElementById("branch-search").value = draft.branchLabel;
      document.getElementById("id_price").value = draft.price;
      if (draft.photo) {
        const dt = new DataTransfer();
        dt.items.add(new File([draft.photo], draft.photo.name || "price-evidence.jpg",
          {type: draft.photo.type || "image/jpeg"}));
        photoInput.files = dt.files;
        showPreview(photoInput.files[0]);
      }
      status.textContent = "Draft loaded. Review and submit when ready.";
    }).catch(() => {});
  }

  form.addEventListener("submit", async event => {
    if (!document.getElementById("id_product").value ||
        !document.getElementById("id_business_branch").value) {
      event.preventDefault();
      status.textContent = "Select a product and a shop from the suggestions.";
      return;
    }
    if (!navigator.onLine) {
      event.preventDefault();
      try { await saveDraft(); }
      catch (_) { status.textContent = "Offline storage unavailable; keep this page open."; }
      return;
    }
    document.getElementById("submit-price").disabled = true;
  });
})();
