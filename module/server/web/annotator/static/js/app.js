(function () {
  const API_PREFIX = "/tool/annotator";
  const AllowedRuleTypes = new Set();

  const state = {
    sessionId: "",
    sourceMode: "local",

    images: [],
    imageMap: new Map(),
    imageElementMap: new Map(),
    currentImageId: "",
    selectedImageIds: new Set(),
    roiViewport: {
      left: 0,
      top: 0,
      width: 1,
      height: 1,
      naturalWidth: 1280,
      naturalHeight: 720,
    },

    sourceDirs: [],
    sourceLeafHasDirs: false,
    sourceLeafJsonFiles: [],
    currentDirPath: "",
    jsonFileName: "",
    taskName: "",
    jsonRelPath: "",

    ruleType: "image",
    ruleTypeLocked: false,
    ruleSchemas: [],
    ruleSchemaMap: new Map(),
    rules: [],
    activeRuleIndex: -1,
    ruleSearchKeyword: "",
    listMeta: {
      name: "list_name",
      direction: "vertical",
      type: "image",
      roiBack: "0,0,100,100",
      description: "",
    },

    dirty: false,

    testOverlayActive: false,
    testRoiFront: "",
    testRoiBack: "",

    imagePreviewCache: new Map(),
    activeRuleImageExists: false,
    imageCheckToken: 0,

    ws: null,
    wsImageUrl: "",
    wsCloseExpected: false,
    emulatorStatus: { state: "stopped" },
    statusTimer: null,
    sessionRecovering: false,
    sessionClosing: false,
  };

  const el = {
    sessionId: document.getElementById("sessionId"),
    message: document.getElementById("globalMessage"),

    sourceMode: document.getElementById("sourceMode"),
    localControls: document.getElementById("localControls"),
    emulatorControls: document.getElementById("emulatorControls"),

    imageUpload: document.getElementById("imageUpload"),
    uploadBtn: document.getElementById("uploadBtn"),
    refreshImagesBtn: document.getElementById("refreshImagesBtn"),
    removeImagesBtn: document.getElementById("removeImagesBtn"),
    clearImagesBtn: document.getElementById("clearImagesBtn"),
    imageList: document.getElementById("imageList"),
    selectedImageCount: document.getElementById("selectedImageCount"),

    configName: document.getElementById("configName"),
    frameRate: document.getElementById("frameRate"),
    startEmulatorBtn: document.getElementById("startEmulatorBtn"),
    stopEmulatorBtn: document.getElementById("stopEmulatorBtn"),
    captureBtn: document.getElementById("captureBtn"),
    emulatorPreview: document.getElementById("emulatorPreview"),
    emulatorStatus: document.getElementById("emulatorStatus"),

    stageWrap: document.getElementById("stageWrap"),
    imageStage: document.getElementById("imageStage"),
    mainImage: document.getElementById("mainImage"),
    noImagePlaceholder: document.getElementById("noImagePlaceholder"),
    roiFront: document.getElementById("roiFront"),
    roiBack: document.getElementById("roiBack"),
    roiFrontValue: document.getElementById("roiFrontValue"),
    roiBackValue: document.getElementById("roiBackValue"),
    testRoiFront: document.getElementById("testRoiFront"),
    testRoiBack: document.getElementById("testRoiBack"),
    outputLog: document.getElementById("outputLog"),
    clearOutputBtn: document.getElementById("clearOutputBtn"),

    dirSelectors: document.getElementById("dirSelectors"),
    currentDir: document.getElementById("currentDir"),
    newJsonName: document.getElementById("newJsonName"),
    createJsonBtn: document.getElementById("createJsonBtn"),
    deleteJsonBtn: document.getElementById("deleteJsonBtn"),

    ruleType: document.getElementById("ruleType"),
    ruleTypeLockTip: document.getElementById("ruleTypeLockTip"),

    listMetaBox: document.getElementById("listMetaBox"),
    listMetaFields: document.getElementById("listMetaFields"),
    listName: null,
    listDirection: null,
    listType: null,
    listDescription: null,

    ruleSearchBox: document.getElementById("ruleSearchBox"),
    ruleSearchInput: document.getElementById("ruleSearchInput"),
    ruleList: document.getElementById("ruleList"),
    addRuleBtn: document.getElementById("addRuleBtn"),
    deleteRuleBtn: document.getElementById("deleteRuleBtn"),
    refreshRulesBtn: document.getElementById("refreshRulesBtn"),

    ruleFields: document.getElementById("ruleFields"),
    itemName: null,
    imageNameWrap: null,
    imageName: null,
    methodWrap: null,
    method: null,
    thresholdWrap: null,
    threshold: null,
    modeWrap: null,
    mode: null,
    keywordWrap: null,
    keyword: null,
    durationWrap: null,
    duration: null,
    descriptionWrap: null,
    description: null,

    testRuleBtn: document.getElementById("testRuleBtn"),
    saveImageBtn: document.getElementById("saveImageBtn"),
    saveRulesBtn: document.getElementById("saveRulesBtn"),
  };

  function getRuleSchema(type = state.ruleType) {
    return state.ruleSchemaMap.get(type) || null;
  }

  function getRuleFields(type = state.ruleType) {
    const schema = getRuleSchema(type);
    return schema && Array.isArray(schema.fields) ? schema.fields : [];
  }

  function getListMetaFields() {
    const schema = getRuleSchema("list");
    return schema && Array.isArray(schema.meta_fields) ? schema.meta_fields : [];
  }

  function getFieldDefault(type, key, fallback = "") {
    const fields = type === "list"
      ? [...getRuleFields(type), ...getListMetaFields()]
      : getRuleFields(type);
    const field = fields.find((item) => item.key === key);
    if (!field) {
      return fallback;
    }
    return field.default ?? fallback;
  }

  function getListMetaDefaults() {
    const defaults = {
      name: "list_name",
      direction: "vertical",
      type: "image",
      roiBack: "0,0,100,100",
      description: "",
    };
    for (const field of getListMetaFields()) {
      defaults[field.key] = field.default ?? defaults[field.key] ?? "";
    }
    return defaults;
  }

  function getRuleFieldDomId(key) {
    return key;
  }

  function getRuleFieldWrapId(key) {
    return `${key}Wrap`;
  }

  function getListMetaFieldDomId(key) {
    if (key === "name") {
      return "listName";
    }
    if (key === "direction") {
      return "listDirection";
    }
    if (key === "type") {
      return "listType";
    }
    if (key === "description") {
      return "listDescription";
    }
    return `list${key}`;
  }

  function createFieldControl(field, domId, wrapId = "") {
    const label = document.createElement("label");
    if (wrapId) {
      label.id = wrapId;
    }
    if (field.full) {
      label.classList.add("full");
    }
    label.append(document.createTextNode(field.label));

    let control = null;
    if (field.control === "textarea") {
      control = document.createElement("textarea");
    } else if (field.control === "select") {
      control = document.createElement("select");
      for (const optionValue of field.options || []) {
        createOption(control, optionValue, optionValue);
      }
    } else {
      control = document.createElement("input");
      control.type = field.control === "number" ? "number" : "text";
    }

    control.id = domId;
    if (field.step !== undefined && "step" in control) {
      control.step = String(field.step);
    }
    if (field.min !== undefined && "min" in control) {
      control.min = String(field.min);
    }
    if (field.max !== undefined && "max" in control) {
      control.max = String(field.max);
    }
    label.appendChild(control);
    return label;
  }

  function renderFieldGroup(container, fields, domIdResolver, wrapIdResolver = null) {
    if (!container) {
      return;
    }
    container.innerHTML = "";
    for (const field of fields) {
      const domId = domIdResolver(field.key);
      const wrapId = wrapIdResolver ? wrapIdResolver(field.key) : "";
      container.appendChild(createFieldControl(field, domId, wrapId));
    }
  }

  function refreshDynamicFieldRefs() {
    el.itemName = document.getElementById("itemName");
    el.imageNameWrap = document.getElementById("imageNameWrap");
    el.imageName = document.getElementById("imageName");
    el.methodWrap = document.getElementById("methodWrap");
    el.method = document.getElementById("method");
    el.thresholdWrap = document.getElementById("thresholdWrap");
    el.threshold = document.getElementById("threshold");
    el.modeWrap = document.getElementById("modeWrap");
    el.mode = document.getElementById("mode");
    el.keywordWrap = document.getElementById("keywordWrap");
    el.keyword = document.getElementById("keyword");
    el.durationWrap = document.getElementById("durationWrap");
    el.duration = document.getElementById("duration");
    el.descriptionWrap = document.getElementById("descriptionWrap");
    el.description = document.getElementById("description");

    el.listName = document.getElementById("listName");
    el.listDirection = document.getElementById("listDirection");
    el.listType = document.getElementById("listType");
    el.listDescription = document.getElementById("listDescription");
  }

  function bindRuleFieldChange(element, fieldKey) {
    if (!element) {
      return;
    }
    const eventName = element.tagName === "SELECT" ? "change" : "input";
    element.addEventListener(eventName, () => updateRuleFromForm(fieldKey));
  }

  function bindDynamicFieldEvents() {
    bindRuleFieldChange(el.itemName, "itemName");
    bindRuleFieldChange(el.imageName, "imageName");
    bindRuleFieldChange(el.method, "method");
    bindRuleFieldChange(el.threshold, "threshold");
    bindRuleFieldChange(el.mode, "mode");
    bindRuleFieldChange(el.keyword, "keyword");
    bindRuleFieldChange(el.duration, "duration");
    bindRuleFieldChange(el.description, "description");

    if (el.listName) {
      el.listName.addEventListener("input", () => {
        updateListMetaFromForm();
        markDirty();
      });
    }
    if (el.listDirection) {
      el.listDirection.addEventListener("change", () => {
        updateListMetaFromForm();
        markDirty();
        updateFieldVisibility();
      });
    }
    if (el.listType) {
      el.listType.addEventListener("change", () => {
        updateListMetaFromForm();
        clearTestOverlay();
        renderRuleList();
        markDirty();
        updateFieldVisibility();
      });
    }
    if (el.listDescription) {
      el.listDescription.addEventListener("input", () => {
        updateListMetaFromForm();
        markDirty();
      });
    }
  }

  function renderDynamicFieldGroups() {
    renderFieldGroup(el.ruleFields, getRuleFields(), getRuleFieldDomId, getRuleFieldWrapId);
    renderFieldGroup(el.listMetaFields, getListMetaFields(), getListMetaFieldDomId);
    refreshDynamicFieldRefs();
    bindDynamicFieldEvents();
  }

  function populateRuleTypeOptions() {
    el.ruleType.innerHTML = "";
    for (const schema of state.ruleSchemas) {
      createOption(el.ruleType, schema.type, schema.label || schema.type);
    }
  }

  async function loadRuleSchemas() {
    const res = await api(`${API_PREFIX}/api/rules/schema`);
    const schemas = res.schemas || {};
    const ruleTypes = Array.isArray(res.rule_types) ? res.rule_types : Object.keys(schemas);
    state.ruleSchemas = ruleTypes.map((type) => schemas[type]).filter(Boolean);
    state.ruleSchemaMap = new Map(state.ruleSchemas.map((schema) => [schema.type, schema]));
    AllowedRuleTypes.clear();
    for (const schema of state.ruleSchemas) {
      AllowedRuleTypes.add(schema.type);
    }
    populateRuleTypeOptions();
    if (!AllowedRuleTypes.has(state.ruleType)) {
      state.ruleType = state.ruleSchemas[0] ? state.ruleSchemas[0].type : "image";
    }
    renderDynamicFieldGroups();
  }

  function setElementValue(element, value) {
    if (!element) {
      return;
    }
    element.value = value ?? "";
  }

  function readFieldValue(field, element) {
    if (!element) {
      return field.default ?? "";
    }
    if (field.control === "number") {
      const raw = String(element.value || "").trim();
      if (field.integer) {
        const parsed = Number.parseInt(raw, 10);
        return Number.isFinite(parsed) ? parsed : (field.default ?? 0);
      }
      const parsed = Number.parseFloat(raw);
      return Number.isFinite(parsed) ? parsed : (field.default ?? 0);
    }
    const value = String(element.value || "").trim();
    if (!value && field.default !== undefined) {
      return field.default;
    }
    return value;
  }

  function showMessage(text, type = "") {
    const message = String(text || "").trim();
    if (!message) {
      if (el.message) {
        el.message.textContent = "";
        el.message.classList.remove("error", "ok");
      }
      return;
    }

    if (el.message) {
      el.message.textContent = message;
      el.message.classList.remove("error", "ok");
      if (type) {
        el.message.classList.add(type);
      }
      return;
    }

    return;
  }

  function formatTime() {
    const now = new Date();
    return now.toLocaleTimeString("zh-CN", { hour12: false });
  }

  function appendOutput(title, payload) {
    const lines = [];
    lines.push(`[${formatTime()}] ${title}`);
    if (payload !== undefined) {
      if (typeof payload === "string") {
        lines.push(payload);
      } else {
        lines.push(JSON.stringify(payload, null, 2));
      }
    }
    const entry = `${lines.join("\n")}\n\n`;
    el.outputLog.textContent = `${entry}${el.outputLog.textContent || ""}`;
  }

  function clearOutput() {
    el.outputLog.textContent = "";
  }

  function clearSaveStatus() {
    el.saveRulesBtn.classList.remove("save-ok", "save-fail");
  }

  function setSaveStatus(ok) {
    el.saveRulesBtn.classList.remove("save-ok", "save-fail");
    if (ok) {
      el.saveRulesBtn.classList.add("save-ok");
    } else {
      el.saveRulesBtn.classList.add("save-fail");
    }
  }

  function setUploadButtonLoading(loading) {
    if (!el.uploadBtn) {
      return;
    }
    el.uploadBtn.disabled = Boolean(loading);
    el.uploadBtn.classList.toggle("btn-loading", Boolean(loading));
    el.uploadBtn.textContent = loading ? "上传中..." : "上传";
  }

  function isInvalidSessionError(error) {
    return Boolean(error && error.code === "invalid_session");
  }

  async function recoverSessionAfterInvalid() {
    if (state.sessionRecovering) {
      return true;
    }

    state.sessionRecovering = true;
    try {
      closeFrameSocket();
      state.images = [];
      state.currentImageId = "";
      state.selectedImageIds.clear();
      state.imageMap = new Map();
      state.imageElementMap = new Map();
      renderImageList();
      clearTestOverlay();
      setMainImage("");
      updateTestButtonVisibility();
      updateEmulatorStatusView({ state: "stopped", message: "session_invalid" });
      showMessage("会话已失效，正在重建会话...", "error");

      await createSession();
      await refreshImages();
      if (state.sourceMode === "emulator") {
        await refreshEmulatorStatus();
      }

      showMessage("会话已重新创建，请重试刚才的操作", "ok");
      return true;
    } catch (recoverError) {
      console.error(recoverError);
      showMessage("会话失效且自动重建失败，请刷新页面后重试", "error");
      return false;
    } finally {
      state.sessionRecovering = false;
    }
  }

  function withError(fn) {
    return async (...args) => {
      try {
        await fn(...args);
      } catch (error) {
        console.error(error);
        if (isInvalidSessionError(error)) {
          const recovered = await recoverSessionAfterInvalid();
          if (recovered) {
            return;
          }
        }
        showMessage(error.message || String(error), "error");
      }
    };
  }

  async function api(path, options = {}) {
    const request = { ...options };
    request.headers = { ...(options.headers || {}) };

    if (request.body !== undefined && !(request.body instanceof FormData) && !request.headers["Content-Type"]) {
      request.headers["Content-Type"] = "application/json";
    }

    const response = await fetch(path, request);
    const contentType = response.headers.get("content-type") || "";
    const rawText = await response.text();
    let payload = rawText;

    if (contentType.includes("application/json")) {
      payload = rawText ? JSON.parse(rawText) : {};
    }

    if (!response.ok) {
      let message = "请求失败";
      let code = "";
      if (payload && payload.detail) {
        if (typeof payload.detail === "string") {
          message = payload.detail;
        } else {
          code = String(payload.detail.code || "");
          message = payload.detail.message || payload.detail.code || JSON.stringify(payload.detail);
        }
      }
      const error = new Error(message);
      error.code = code;
      error.status = response.status;
      throw error;
    }

    return payload;
  }

  async function closeSession(reason = "client_close", useUnloadTransport = false) {
    if (!state.sessionId || state.sessionClosing) {
      return;
    }

    const sessionId = encodeURIComponent(state.sessionId);
    const reasonQuery = `reason=${encodeURIComponent(reason)}`;
    const closeUrl = `${API_PREFIX}/api/session/${sessionId}?${reasonQuery}`;

    if (useUnloadTransport) {
      state.sessionClosing = true;
      const beaconUrl = `${API_PREFIX}/api/session/${sessionId}/close?${reasonQuery}`;
      if (navigator.sendBeacon) {
        navigator.sendBeacon(beaconUrl, "");
        return;
      }
      fetch(closeUrl, {
        method: "DELETE",
        keepalive: true,
      }).catch(() => {
        // 页面卸载场景忽略错误
      });
      return;
    }

    state.sessionClosing = true;
    try {
      await api(closeUrl, { method: "DELETE" });
    } finally {
      state.sessionClosing = false;
    }
  }

  function createOption(select, value, label) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    select.appendChild(option);
  }

  function fillSelect(select, values, placeholder) {
    select.innerHTML = "";
    createOption(select, "", placeholder);
    for (const value of values) {
      createOption(select, value, value);
    }
  }

  function splitPath(pathText) {
    return String(pathText || "")
      .split("/")
      .map((x) => x.trim())
      .filter(Boolean);
  }

  function joinPath(parts) {
    return parts.filter(Boolean).join("/");
  }

  function sanitizeImageNameBase(text) {
    const value = String(text || "").trim();
    const safe = value.replace(/[^\w\-\u4e00-\u9fa5]/g, "_");
    return safe || "image";
  }

  function getRuleImageNamePrefix() {
    const parts = splitPath(state.currentDirPath);
    if (parts.length > 0) {
      return sanitizeImageNameBase(parts[parts.length - 1]);
    }
    if (state.taskName) {
      return sanitizeImageNameBase(state.taskName);
    }
    return "image";
  }

  function defaultImageNameForItem(itemName) {
    const prefix = getRuleImageNamePrefix();
    return `${prefix}_${sanitizeImageNameBase(itemName)}.png`;
  }

  function listImageNameForItem(itemName) {
    const value = String(itemName || "").trim();
    return value ? `${value}.png` : "";
  }

  function getRuleSubtype() {
    if (state.ruleType === "list") {
      return state.listMeta.type || "image";
    }
    return state.ruleType;
  }

  function isListImageRule() {
    return state.ruleType === "list" && getRuleSubtype() === "image";
  }

  function isListOcrRule() {
    return state.ruleType === "list" && getRuleSubtype() === "ocr";
  }

  function isImagePreviewRule() {
    return state.ruleType === "image" || isListImageRule();
  }

  function parseRoi(text) {
    const parts = String(text || "")
      .split(",")
      .map((item) => Number.parseFloat(item.trim()));
    if (parts.length !== 4 || parts.some((x) => Number.isNaN(x))) {
      return [0, 0, 100, 100];
    }
    const [x, y, w, h] = parts;
    return [x, y, Math.max(1, w), Math.max(1, h)];
  }

  function parseRoiStrict(text) {
    const parts = String(text || "")
      .split(",")
      .map((item) => Number.parseFloat(item.trim()));
    if (parts.length !== 4 || parts.some((x) => !Number.isFinite(x))) {
      return null;
    }
    const [x, y, w, h] = parts;
    return formatRoiFromNumbers(x, y, w, h);
  }

  function getStageSize() {
    return {
      width: Math.max(1, el.imageStage.clientWidth || 1),
      height: Math.max(1, el.imageStage.clientHeight || 1),
    };
  }

  function computeRoiViewport() {
    const stage = getStageSize();
    const naturalWidth = Math.max(1, el.mainImage.naturalWidth || state.roiViewport.naturalWidth || 1280);
    const naturalHeight = Math.max(1, el.mainImage.naturalHeight || state.roiViewport.naturalHeight || 720);

    const scale = Math.min(stage.width / naturalWidth, stage.height / naturalHeight);
    const width = Math.max(1, naturalWidth * scale);
    const height = Math.max(1, naturalHeight * scale);

    return {
      left: (stage.width - width) / 2,
      top: (stage.height - height) / 2,
      width,
      height,
      naturalWidth,
      naturalHeight,
    };
  }

  function updateRoiViewport() {
    state.roiViewport = computeRoiViewport();
    return state.roiViewport;
  }

  function getRoiViewport() {
    return updateRoiViewport();
  }

  function naturalToStageX(value, viewport) {
    return viewport.left + (value * viewport.width) / viewport.naturalWidth;
  }

  function naturalToStageY(value, viewport) {
    return viewport.top + (value * viewport.height) / viewport.naturalHeight;
  }

  function naturalToStageW(value, viewport) {
    return (value * viewport.width) / viewport.naturalWidth;
  }

  function naturalToStageH(value, viewport) {
    return (value * viewport.height) / viewport.naturalHeight;
  }

  function stageToNaturalX(value, viewport) {
    return ((value - viewport.left) * viewport.naturalWidth) / viewport.width;
  }

  function stageToNaturalY(value, viewport) {
    return ((value - viewport.top) * viewport.naturalHeight) / viewport.height;
  }

  function stageToNaturalW(value, viewport) {
    return (value * viewport.naturalWidth) / viewport.width;
  }

  function stageToNaturalH(value, viewport) {
    return (value * viewport.naturalHeight) / viewport.height;
  }

  function formatRoiFromNumbers(x, y, w, h) {
    return `${Math.round(x)},${Math.round(y)},${Math.max(1, Math.round(w))},${Math.max(1, Math.round(h))}`;
  }

  function applyBoxFromRoi(box, roiText) {
    const viewport = getRoiViewport();
    const [x, y, w, h] = parseRoi(roiText);
    box.style.left = `${Math.round(naturalToStageX(x, viewport))}px`;
    box.style.top = `${Math.round(naturalToStageY(y, viewport))}px`;
    box.style.width = `${Math.max(8, Math.round(naturalToStageW(w, viewport)))}px`;
    box.style.height = `${Math.max(8, Math.round(naturalToStageH(h, viewport)))}px`;
  }

  function renderTestOverlay() {
    if (!state.testOverlayActive || !state.testRoiFront || !state.testRoiBack) {
      el.testRoiFront.classList.add("hidden");
      el.testRoiBack.classList.add("hidden");
      return;
    }
    applyBoxFromRoi(el.testRoiFront, state.testRoiFront);
    applyBoxFromRoi(el.testRoiBack, state.testRoiBack);
    el.testRoiFront.classList.remove("hidden");
    el.testRoiBack.classList.remove("hidden");
  }

  function clearTestOverlay() {
    state.testOverlayActive = false;
    state.testRoiFront = "";
    state.testRoiBack = "";
    el.testRoiFront.classList.add("hidden");
    el.testRoiBack.classList.add("hidden");
    updateTestButtonVisibility();
  }

  function setTestOverlay(front, back) {
    state.testRoiFront = String(front || "").trim();
    state.testRoiBack = String(back || "").trim();
    state.testOverlayActive = Boolean(state.testRoiFront && state.testRoiBack);
    renderTestOverlay();
    updateTestButtonVisibility();
  }

  function boxToRoi(box) {
    const viewport = getRoiViewport();
    const left = Number.parseFloat(box.style.left || "0");
    const top = Number.parseFloat(box.style.top || "0");
    const width = Number.parseFloat(box.style.width || "1");
    const height = Number.parseFloat(box.style.height || "1");

    return formatRoiFromNumbers(
      stageToNaturalX(left, viewport),
      stageToNaturalY(top, viewport),
      stageToNaturalW(width, viewport),
      stageToNaturalH(height, viewport),
    );
  }

  function clampBox(box) {
    const viewport = getRoiViewport();
    const minSize = 8;
    const maxWidth = Math.max(minSize, viewport.width);
    const maxHeight = Math.max(minSize, viewport.height);
    const maxLeft = viewport.left + maxWidth;
    const maxTop = viewport.top + maxHeight;

    let left = Number.parseFloat(box.style.left || "0");
    let top = Number.parseFloat(box.style.top || "0");
    let width = Number.parseFloat(box.style.width || "1");
    let height = Number.parseFloat(box.style.height || "1");

    width = Math.max(minSize, Math.min(width, maxWidth));
    height = Math.max(minSize, Math.min(height, maxHeight));
    left = Math.max(viewport.left, Math.min(left, maxLeft - width));
    top = Math.max(viewport.top, Math.min(top, maxTop - height));

    box.style.left = `${left}px`;
    box.style.top = `${top}px`;
    box.style.width = `${width}px`;
    box.style.height = `${height}px`;
  }

  function setMainImage(url) {
    if (!url) {
      el.mainImage.removeAttribute("src");
      el.noImagePlaceholder.classList.remove("hidden");
      el.roiFront.classList.add("hidden");
      el.roiBack.classList.add("hidden");
      el.testRoiFront.classList.add("hidden");
      el.testRoiBack.classList.add("hidden");
      updateRoiViewport();
      return;
    }
    el.mainImage.src = url;
    el.noImagePlaceholder.classList.add("hidden");
    el.roiFront.classList.remove("hidden");
    el.roiBack.classList.remove("hidden");
    renderTestOverlay();
  }

  function updateSelectedImageCount() {
    el.selectedImageCount.textContent = String(state.selectedImageIds.size);
    updateRemoveImagesButtonState();
  }

  function updateRemoveImagesButtonState() {
    if (!el.removeImagesBtn) {
      return;
    }
    el.removeImagesBtn.disabled = state.selectedImageIds.size === 0;
  }

  function markDirty() {
    state.dirty = true;
    clearSaveStatus();
    updateTestButtonVisibility();
  }

  function clearDirty() {
    state.dirty = false;
    updateTestButtonVisibility();
  }

  function updateImageSelectionClass(imageId) {
    const item = state.imageElementMap.get(imageId);
    if (!item) {
      return;
    }
    item.classList.toggle("selected", state.selectedImageIds.has(imageId));
    const checkbox = item.querySelector("input[type='checkbox']");
    if (checkbox) {
      checkbox.checked = state.selectedImageIds.has(imageId);
    }
  }

  function updateCurrentImageHighlight() {
    for (const [imageId, item] of state.imageElementMap.entries()) {
      item.classList.toggle("active", imageId === state.currentImageId);
    }
  }

  function selectImage(imageId, showToast = true) {
    const image = state.imageMap.get(imageId);
    if (!image) {
      return;
    }
    state.currentImageId = imageId;
    clearTestOverlay();
    setMainImage(`${image.url}?t=${Date.now()}`);
    updateCurrentImageHighlight();
    updateTestButtonVisibility();
    if (showToast) {
      showMessage(`当前图片: ${image.name}`, "ok");
    }
  }

  function toggleImageSelected(imageId, checked) {
    if (checked) {
      state.selectedImageIds.add(imageId);
    } else {
      state.selectedImageIds.delete(imageId);
    }
    updateImageSelectionClass(imageId);
    updateSelectedImageCount();
  }

  function normalizeImages(images) {
    if (!Array.isArray(images)) {
      return [];
    }
    return images.filter((image) => image && image.id);
  }

  function syncSelectedImageIds() {
    const keepSelected = new Set();
    for (const image of state.images) {
      if (state.selectedImageIds.has(image.id)) {
        keepSelected.add(image.id);
      }
    }
    state.selectedImageIds = keepSelected;
  }

  function rebuildImageMap() {
    state.imageMap = new Map(state.images.map((image) => [image.id, image]));
  }

  function ensureCurrentImageId() {
    const hasCurrent = state.images.some((item) => item.id === state.currentImageId);
    if (hasCurrent) {
      return false;
    }
    state.currentImageId = state.images.length ? state.images[state.images.length - 1].id : "";
    return true;
  }

  function clearImageListElements() {
    state.imageElementMap.clear();
    el.imageList.innerHTML = "";
  }

  function updateImageItemContent(image) {
    const item = state.imageElementMap.get(image.id);
    if (!item) {
      return;
    }

    const thumb = item.querySelector("img");
    if (thumb) {
      thumb.alt = image.name;
    }

    const name = item.querySelector(".image-name");
    if (name) {
      name.textContent = `${image.name} (${image.source})`;
    }
  }

  function applyEmptyImageListState() {
    state.images = [];
    state.currentImageId = "";
    state.selectedImageIds.clear();
    rebuildImageMap();
    clearImageListElements();
    clearTestOverlay();
    setMainImage("");
    updateSelectedImageCount();
    updateTestButtonVisibility();
  }

  function buildImageItem(image) {
    const item = document.createElement("div");
    item.className = "image-item";
    item.dataset.imageId = image.id;

    const selector = document.createElement("label");
    selector.className = "selector";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleImageSelected(image.id, checkbox.checked);
    });
    selector.appendChild(checkbox);

    const thumb = document.createElement("img");
    thumb.src = `${image.thumb_url}?t=${Date.now()}`;
    thumb.alt = image.name;

    const name = document.createElement("div");
    name.className = "image-name";
    name.textContent = `${image.name} (${image.source})`;

    item.appendChild(selector);
    item.appendChild(thumb);
    item.appendChild(name);

    item.addEventListener("click", () => selectImage(image.id));
    return item;
  }

  function renderImageList() {
    syncSelectedImageIds();
    rebuildImageMap();
    clearImageListElements();

    for (const image of state.images) {
      const item = buildImageItem(image);
      state.imageElementMap.set(image.id, item);
      el.imageList.appendChild(item);
      updateImageSelectionClass(image.id);
    }

    updateCurrentImageHighlight();
    updateSelectedImageCount();
  }

  function replaceImages(images) {
    state.images = normalizeImages(images);

    if (state.images.length === 0) {
      applyEmptyImageListState();
      return;
    }

    syncSelectedImageIds();
    ensureCurrentImageId();
    renderImageList();

    const image = state.imageMap.get(state.currentImageId);
    if (image) {
      setMainImage(`${image.url}?t=${Date.now()}`);
    }
    updateTestButtonVisibility();
  }

  function appendImages(images) {
    const incoming = normalizeImages(images);
    if (!incoming.length) {
      return;
    }

    const imageIndexMap = new Map(state.images.map((image, index) => [image.id, index]));
    const appended = [];

    for (const image of incoming) {
      const existingIndex = imageIndexMap.get(image.id);
      if (existingIndex !== undefined) {
        state.images[existingIndex] = image;
      } else {
        imageIndexMap.set(image.id, state.images.length);
        state.images.push(image);
        appended.push(image);
      }
    }

    syncSelectedImageIds();
    rebuildImageMap();

    for (const image of incoming) {
      updateImageItemContent(image);
    }

    for (const image of appended) {
      const item = buildImageItem(image);
      state.imageElementMap.set(image.id, item);
      el.imageList.appendChild(item);
      updateImageSelectionClass(image.id);
    }

    const currentChanged = ensureCurrentImageId();
    if (currentChanged) {
      const image = state.imageMap.get(state.currentImageId);
      if (image) {
        setMainImage(`${image.url}?t=${Date.now()}`);
      }
    }

    updateCurrentImageHighlight();
    updateSelectedImageCount();
    updateTestButtonVisibility();
  }

  async function refreshImages() {
    if (!state.sessionId) {
      return;
    }

    const res = await api(`${API_PREFIX}/api/images?session_id=${encodeURIComponent(state.sessionId)}`);
    replaceImages(res.images);
  }
  async function uploadImages() {
    if (!state.sessionId) {
      return;
    }

    if (!el.imageUpload.files || el.imageUpload.files.length === 0) {
      throw new Error("请选择至少一张图片");
    }

    setUploadButtonLoading(true);
    try {
      const files = Array.from(el.imageUpload.files);
      const images = await Promise.all(
        files.map(
          (file) =>
            new Promise((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => resolve({ name: file.name, content_base64: reader.result });
              reader.onerror = () => reject(new Error(`读取文件失败: ${file.name}`));
              reader.readAsDataURL(file);
            }),
        ),
      );

      const payload = await api(`${API_PREFIX}/api/images/upload`, {
        method: "POST",
        body: JSON.stringify({ session_id: state.sessionId, images }),
      });

      el.imageUpload.value = "";
      const appendedImages = normalizeImages(payload.images);
      appendImages(appendedImages);
      showMessage(`上传成功，共 ${appendedImages.length} 张`, "ok");
    } finally {
      setUploadButtonLoading(false);
    }
  }

  async function removeSelectedImages() {
    if (!state.sessionId || state.selectedImageIds.size === 0) {
      throw new Error("请先勾选图片");
    }

    const ids = Array.from(state.selectedImageIds);
    const res = await api(`${API_PREFIX}/api/images/delete-batch`, {
      method: "POST",
      body: JSON.stringify({ session_id: state.sessionId, image_ids: ids }),
    });

    await refreshImages();
    showMessage(`已移除 ${res.removed_count || 0} 张图片`, "ok");
  }

  async function clearImages() {
    if (!state.sessionId || state.images.length === 0) {
      return;
    }

    const confirmed = window.confirm("确认清空当前会话的全部图片吗？");
    if (!confirmed) {
      return;
    }

    const res = await api(`${API_PREFIX}/api/images/clear`, {
      method: "POST",
      body: JSON.stringify({ session_id: state.sessionId }),
    });

    await refreshImages();
    showMessage(`已清空图片，共 ${res.removed_count || 0} 张`, "ok");
  }

  function getCurrentRule() {
    if (state.activeRuleIndex < 0 || state.activeRuleIndex >= state.rules.length) {
      return null;
    }
    return state.rules[state.activeRuleIndex];
  }

  function syncRoiToRule() {
    const rule = getCurrentRule();
    if (!rule) {
      return;
    }

    const front = boxToRoi(el.roiFront);
    const back = boxToRoi(el.roiBack);

    rule.roiFront = front;
    if (state.ruleType === "list") {
      state.listMeta.roiBack = back;
    } else {
      rule.roiBack = back;
    }

    el.roiFrontValue.value = front;
    el.roiBackValue.value = back;
    markDirty();
  }

  function captureCurrentCanvasRois() {
    const rule = getCurrentRule();
    if (!rule) {
      return null;
    }

    clampBox(el.roiFront);
    clampBox(el.roiBack);

    return {
      front: boxToRoi(el.roiFront),
      back: boxToRoi(el.roiBack),
    };
  }

  function createRuleFromCurrentCanvas(type) {
    const rule = defaultRuleByType(type);
    const roi = captureCurrentCanvasRois();
    if (!roi) {
      return rule;
    }

    rule.roiFront = roi.front;
    if (type !== "list") {
      rule.roiBack = roi.back;
    } else {
      state.listMeta.roiBack = roi.back;
    }
    return rule;
  }

  function applyRoiInputToRule(target) {
    const rule = getCurrentRule();
    if (!rule) {
      return;
    }

    const isFront = target === "front";
    const input = isFront ? el.roiFrontValue : el.roiBackValue;
    const box = isFront ? el.roiFront : el.roiBack;
    const parsed = parseRoiStrict(input.value);

    if (!parsed) {
      const fallback = isFront
        ? (rule.roiFront || "0,0,100,100")
        : (state.ruleType === "list" ? (state.listMeta.roiBack || "0,0,100,100") : (rule.roiBack || "0,0,100,100"));
      input.value = fallback;
      showMessage(`${isFront ? "roiFront" : "roiBack"} 格式无效，应为 x,y,w,h`, "error");
      return;
    }

    applyBoxFromRoi(box, parsed);
    clampBox(box);
    const normalized = boxToRoi(box);
    input.value = normalized;
    if (normalized !== parsed) {
      showMessage(`${isFront ? "roiFront" : "roiBack"} 超出图像显示范围，已自动规范化`, "ok");
    }

    if (isFront) {
      rule.roiFront = normalized;
    } else if (state.ruleType === "list") {
      state.listMeta.roiBack = normalized;
    } else {
      rule.roiBack = normalized;
    }

    markDirty();
  }

  function refreshRoiLayoutFromRule() {
    const rule = getCurrentRule();
    updateRoiViewport();
    if (!rule) {
      applyBoxFromRoi(el.roiFront, "0,0,100,100");
      applyBoxFromRoi(el.roiBack, "0,0,100,100");
      clampBox(el.roiFront);
      clampBox(el.roiBack);
      renderTestOverlay();
      return;
    }
    const front = rule.roiFront || "0,0,100,100";
    const back = state.ruleType === "list" ? (state.listMeta.roiBack || "0,0,100,100") : (rule.roiBack || "0,0,100,100");
    applyBoxFromRoi(el.roiFront, front);
    applyBoxFromRoi(el.roiBack, back);
    clampBox(el.roiFront);
    clampBox(el.roiBack);
    renderTestOverlay();
  }

  function setupRoiBox(box) {
    const handles = Array.from(box.querySelectorAll(".resize-handle"));
    let mode = "";
    let resizeDir = "";
    let startX = 0;
    let startY = 0;
    let origin = { left: 0, top: 0, width: 0, height: 0 };

    const onMove = (event) => {
      if (!mode) {
        return;
      }
      const dx = event.clientX - startX;
      const dy = event.clientY - startY;
      if (mode === "drag") {
        box.style.left = `${origin.left + dx}px`;
        box.style.top = `${origin.top + dy}px`;
      } else if (mode === "resize") {
        const minSize = 8;
        const right = origin.left + origin.width;
        const bottom = origin.top + origin.height;
        let left = origin.left;
        let top = origin.top;
        let width = origin.width;
        let height = origin.height;

        if (resizeDir.includes("w")) {
          left = Math.min(origin.left + dx, right - minSize);
          width = right - left;
        } else {
          width = Math.max(minSize, origin.width + dx);
        }

        if (resizeDir.includes("n")) {
          top = Math.min(origin.top + dy, bottom - minSize);
          height = bottom - top;
        } else {
          height = Math.max(minSize, origin.height + dy);
        }

        box.style.left = `${left}px`;
        box.style.top = `${top}px`;
        box.style.width = `${width}px`;
        box.style.height = `${height}px`;
      }
      clampBox(box);
      syncRoiToRule();
    };

    const onUp = () => {
      mode = "";
      resizeDir = "";
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };

    box.addEventListener("mousedown", (event) => {
      if (event.target.closest(".resize-handle")) {
        return;
      }
      event.preventDefault();
      mode = "drag";
      startX = event.clientX;
      startY = event.clientY;
      origin = {
        left: Number.parseFloat(box.style.left || "0"),
        top: Number.parseFloat(box.style.top || "0"),
        width: Number.parseFloat(box.style.width || "1"),
        height: Number.parseFloat(box.style.height || "1"),
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });

    for (const handle of handles) {
      handle.addEventListener("mousedown", (event) => {
        event.preventDefault();
        event.stopPropagation();
        mode = "resize";
        resizeDir = handle.dataset.resizeDir || "se";
        startX = event.clientX;
        startY = event.clientY;
        origin = {
          left: Number.parseFloat(box.style.left || "0"),
          top: Number.parseFloat(box.style.top || "0"),
          width: Number.parseFloat(box.style.width || "1"),
          height: Number.parseFloat(box.style.height || "1"),
        };
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
      });
    }
  }

  function adjustStageByImage() {
    const naturalW = el.mainImage.naturalWidth || 1280;
    const naturalH = el.mainImage.naturalHeight || 720;

    const containerW = el.stageWrap && el.stageWrap.parentElement
      ? (el.stageWrap.parentElement.clientWidth - 28)
      : 940;

    const stageBaseH = window.innerWidth <= 1320
      ? 520
      : Math.min(window.innerHeight * 0.62, 640);

    const maxW = Math.max(320, containerW);
    const maxH = Math.max(240, stageBaseH - 20);
    const scale = Math.min(maxW / naturalW, maxH / naturalH, 1);

    const stageScale = scale || 1;
    el.imageStage.style.width = `${Math.round(naturalW * stageScale)}px`;
    el.imageStage.style.height = `${Math.round(naturalH * stageScale)}px`;

    fillRuleForm();
  }

  function resetListMeta() {
    state.listMeta = getListMetaDefaults();
  }

  function defaultRuleByType(type) {
    const rule = {};
    for (const field of getRuleFields(type)) {
      rule[field.key] = field.default ?? "";
    }
    rule.itemName = String(rule.itemName || "new");
    rule.roiFront = "0,0,100,100";
    if (type !== "list") {
      rule.roiBack = "0,0,100,100";
    }
    if (type === "image") {
      rule.imageName = String(rule.imageName || "").trim() || defaultImageNameForItem(rule.itemName || "new");
      rule.__autoImageName = true;
    }
    if (type === "list") {
      delete rule.description;
    }
    return rule;
  }

  function normalizeLoadedRules(type, rules) {
    const result = [];
    for (const raw of rules || []) {
      const item = { ...defaultRuleByType(type), ...(raw || {}) };
      if (type === "image") {
        const autoName = defaultImageNameForItem(item.itemName || "");
        item.__autoImageName = !item.imageName || item.imageName === autoName;
      }
      if (type === "list") {
        delete item.description;
      }
      result.push(item);
    }
    return result;
  }

  function cloneRules(rules) {
    return (rules || []).map((rule) => ({ ...rule }));
  }

  function updateFieldVisibility() {
    const type = state.ruleType;
    el.listMetaBox.classList.toggle("hidden", type !== "list");

    const showSaveImage = type === "image" || isListImageRule();
    el.saveImageBtn.classList.toggle("hidden", !showSaveImage);

    refreshActiveRuleImageExists().catch(() => {
      // ignore
    });
  }

  function getRulePreviewImageName(rule) {
    if (!rule) {
      return "";
    }
    if (state.ruleType === "image") {
      return String(rule.imageName || "").trim();
    }
    if (isListImageRule()) {
      return listImageNameForItem(rule.itemName);
    }
    return "";
  }

  function getRuleDeleteImageName(rule) {
    if (!rule) {
      return "";
    }
    if (state.ruleType === "image") {
      const imageName = String(rule.imageName || "").trim();
      return imageName || defaultImageNameForItem(rule.itemName || "image");
    }
    if (isListImageRule()) {
      return listImageNameForItem(rule.itemName);
    }
    return "";
  }

  function canDeleteRuleLinkedImage(rule) {
    if (!rule) {
      return false;
    }
    return state.ruleType === "image" || isListImageRule();
  }

  function currentRulePreviewUrl(rule) {
    if (!isImagePreviewRule()) {
      return "";
    }
    const imageName = getRulePreviewImageName(rule);
    if (!imageName || !state.taskName || !state.jsonRelPath) {
      return "";
    }
    const query = new URLSearchParams({
      task_name: state.taskName,
      json_relpath: state.jsonRelPath,
      image_name: imageName,
    }).toString();
    return `${API_PREFIX}/api/rules/image-preview?${query}`;
  }

  function getRuleImageCacheKeyFromImageName(imageName) {
    const value = String(imageName || "").trim();
    if (!value || !state.taskName || !state.jsonRelPath) {
      return "";
    }
    return `${state.taskName}|${state.jsonRelPath}|${value}`;
  }

  function getRuleImageCacheKey(rule) {
    return getRuleImageCacheKeyFromImageName(getRulePreviewImageName(rule));
  }

  async function checkRuleImageExists(rule) {
    const key = getRuleImageCacheKey(rule);
    if (!key) {
      return false;
    }
    if (state.imagePreviewCache.has(key)) {
      return Boolean(state.imagePreviewCache.get(key));
    }
    const url = currentRulePreviewUrl(rule);
    if (!url) {
      state.imagePreviewCache.set(key, false);
      return false;
    }
    try {
      const response = await fetch(`${url}&t=${Date.now()}`, { method: "GET", cache: "no-store" });
      const exists = response.ok;
      state.imagePreviewCache.set(key, exists);
      return exists;
    } catch (_error) {
      state.imagePreviewCache.set(key, false);
      return false;
    }
  }

  function clearRuleImageCacheByImageName(imageName) {
    const key = getRuleImageCacheKeyFromImageName(imageName);
    if (key) {
      state.imagePreviewCache.delete(key);
    }
  }

  function clearRuleImageCache(rule) {
    clearRuleImageCacheByImageName(getRulePreviewImageName(rule));
  }

  async function refreshActiveRuleImageExists() {
    const token = ++state.imageCheckToken;
    if (!isImagePreviewRule()) {
      state.activeRuleImageExists = true;
      updateTestButtonVisibility();
      return;
    }
    const rule = getCurrentRule();
    if (!rule) {
      state.activeRuleImageExists = false;
      updateTestButtonVisibility();
      return;
    }
    const exists = await checkRuleImageExists(rule);
    if (token !== state.imageCheckToken) {
      return;
    }
    state.activeRuleImageExists = exists;
    updateTestButtonVisibility();
  }

  function buildRuleItem(rule, index, displayIndex) {
    const item = document.createElement("div");
    item.className = "rule-item";
    item.dataset.index = String(index);
    item.dataset.displayIndex = String(displayIndex);

    if (isImagePreviewRule()) {
      const thumbWrap = document.createElement("div");
      thumbWrap.className = "rule-thumb-wrap";

      const thumb = document.createElement("img");
      thumb.className = "rule-thumb";
      thumb.alt = "";

      const empty = document.createElement("span");
      empty.className = "rule-thumb-empty";
      empty.textContent = "空";

      thumb.onload = () => {
        thumbWrap.classList.add("has-image");
      };

      thumb.onerror = () => {
        thumb.removeAttribute("src");
        thumbWrap.classList.remove("has-image");
      };

      const url = currentRulePreviewUrl(rule);
      if (url) {
        thumb.src = `${url}&t=${Date.now()}`;
      } else {
        thumbWrap.classList.remove("has-image");
      }

      thumbWrap.appendChild(thumb);
      thumbWrap.appendChild(empty);
      item.appendChild(thumbWrap);
    }

    const text = document.createElement("div");
    text.className = "rule-item-text";
    text.textContent = `${displayIndex}. ${rule.itemName || "unnamed"}`;
    item.appendChild(text);

    item.addEventListener("click", () => {
      state.activeRuleIndex = index;
      updateRuleActiveHighlight();
      fillRuleForm();
      clearTestOverlay();
      refreshActiveRuleImageExists().catch(() => {
        // ignore
      });
    });

    return item;
  }

  function buildRuleListEmptyState(message) {
    const empty = document.createElement("div");
    empty.className = "rule-list-empty";
    empty.textContent = message;
    return empty;
  }

  function getVisibleRuleEntries() {
    const keyword = getNormalizedRuleSearchKeyword();
    return state.rules
      .map((rule, actualIndex) => ({ rule, actualIndex }))
      .filter(({ rule }) => {
        if (!keyword) {
          return true;
        }
        return String(rule.itemName || "").toLowerCase().includes(keyword);
      })
      .map((entry, offset) => ({
        ...entry,
        displayIndex: offset + 1,
      }));
  }

  function updateRuleActiveHighlight() {
    const items = el.ruleList.querySelectorAll(".rule-item");
    for (const item of items) {
      const idx = Number.parseInt(item.dataset.index || "-1", 10);
      item.classList.toggle("active", idx === state.activeRuleIndex);
    }
  }

  function renderRuleList() {
    el.ruleList.innerHTML = "";

    if (state.rules.length === 0) {
      state.activeRuleIndex = -1;
      clearRuleForm();
      fillListMetaForm();
      return;
    }

    const visibleEntries = getVisibleRuleEntries();

    if (visibleEntries.length === 0) {
      state.activeRuleIndex = -1;
      el.ruleList.appendChild(buildRuleListEmptyState("未找到匹配的规则项"));
      clearRuleForm();
      fillListMetaForm();
      return;
    }

    if (state.activeRuleIndex < 0 || !visibleEntries.some((entry) => entry.actualIndex === state.activeRuleIndex)) {
      state.activeRuleIndex = visibleEntries[0].actualIndex;
    }

    visibleEntries.forEach(({ rule, actualIndex, displayIndex }) => {
      el.ruleList.appendChild(buildRuleItem(rule, actualIndex, displayIndex));
    });

    updateRuleActiveHighlight();
    fillRuleForm();
  }

  function refreshActiveRuleItem() {
    const active = el.ruleList.querySelector(`.rule-item[data-index="${state.activeRuleIndex}"]`);
    if (!active) {
      return;
    }
    const rule = getCurrentRule();
    if (!rule) {
      return;
    }
    const text = active.querySelector(".rule-item-text");
    if (text) {
      const displayIndex = Number.parseInt(active.dataset.displayIndex || "1", 10) || 1;
      text.textContent = `${displayIndex}. ${rule.itemName || "unnamed"}`;
    }
    const thumbWrap = active.querySelector(".rule-thumb-wrap");
    const thumb = active.querySelector(".rule-thumb");
    if (thumb && isImagePreviewRule()) {
      const url = currentRulePreviewUrl(rule);
      if (url) {
        if (thumbWrap) {
          thumbWrap.classList.remove("has-image");
        }
        thumb.src = `${url}&t=${Date.now()}`;
      } else {
        thumb.removeAttribute("src");
        if (thumbWrap) {
          thumbWrap.classList.remove("has-image");
        }
      }
    }
  }

  function clearRuleForm() {
    for (const field of getRuleFields()) {
      const element = document.getElementById(getRuleFieldDomId(field.key));
      setElementValue(element, field.default ?? "");
    }
    el.roiFrontValue.value = "";
    el.roiBackValue.value = "";
    refreshRoiLayoutFromRule();
    clearTestOverlay();
    updateFieldVisibility();
  }

  function fillListMetaForm() {
    const defaults = getListMetaDefaults();
    for (const field of getListMetaFields()) {
      const element = document.getElementById(getListMetaFieldDomId(field.key));
      setElementValue(element, state.listMeta[field.key] ?? defaults[field.key] ?? "");
    }
  }

  function updateListMetaFromForm() {
    const defaults = getListMetaDefaults();
    for (const field of getListMetaFields()) {
      const element = document.getElementById(getListMetaFieldDomId(field.key));
      state.listMeta[field.key] = readFieldValue(field, element) ?? defaults[field.key] ?? "";
    }
  }

  function fillRuleForm() {
    const rule = getCurrentRule();
    if (!rule) {
      clearRuleForm();
      return;
    }

    for (const field of getRuleFields()) {
      const element = document.getElementById(getRuleFieldDomId(field.key));
      setElementValue(element, rule[field.key] ?? field.default ?? "");
    }

    const front = rule.roiFront || "0,0,100,100";
    const back = state.ruleType === "list" ? (state.listMeta.roiBack || "0,0,100,100") : (rule.roiBack || "0,0,100,100");
    el.roiFrontValue.value = front;
    el.roiBackValue.value = back;

    refreshRoiLayoutFromRule();

    fillListMetaForm();
    updateFieldVisibility();
  }

  function updateRuleFromForm(changedField = "") {
    const rule = getCurrentRule();
    if (!rule) {
      return;
    }

    const oldPreviewImageName = getRulePreviewImageName(rule);
    for (const field of getRuleFields()) {
      if (state.ruleType === "image" && field.key === "imageName" && changedField === "itemName") {
        continue;
      }
      const element = document.getElementById(getRuleFieldDomId(field.key));
      rule[field.key] = readFieldValue(field, element);
    }

    const newItemName = String(rule.itemName || "").trim() || "unnamed";
    rule.itemName = newItemName;

    if (state.ruleType === "image") {
      if (changedField === "itemName") {
        rule.imageName = defaultImageNameForItem(newItemName);
        rule.__autoImageName = true;
        setElementValue(el.imageName, rule.imageName);
      } else {
        const imageNameInput = String(el.imageName && el.imageName.value || "").trim();
        if (imageNameInput) {
          rule.imageName = imageNameInput;
          rule.__autoImageName = imageNameInput === defaultImageNameForItem(newItemName);
        } else {
          rule.imageName = defaultImageNameForItem(newItemName);
          rule.__autoImageName = true;
          setElementValue(el.imageName, rule.imageName);
        }
      }

      const nextImageName = String(rule.imageName || "").trim();
      if (oldPreviewImageName !== nextImageName || changedField === "itemName") {
        clearRuleImageCacheByImageName(oldPreviewImageName);
        clearRuleImageCache(rule);
        state.activeRuleImageExists = false;
      }
    }

    if (state.ruleType === "list") {
      updateListMetaFromForm();
      delete rule.description;
      if (isListImageRule() && changedField === "itemName") {
        clearRuleImageCacheByImageName(oldPreviewImageName);
        clearRuleImageCache(rule);
        state.activeRuleImageExists = false;
      }
    }

    const searchKeyword = getNormalizedRuleSearchKeyword();
    const activeStillVisible = !searchKeyword || String(rule.itemName || "").toLowerCase().includes(searchKeyword);
    if (changedField === "itemName" && !activeStillVisible) {
      renderRuleList();
    } else {
      refreshActiveRuleItem();
    }
    markDirty();
    refreshActiveRuleImageExists().catch(() => {
      // ignore
    });
  }

  async function refreshRulesList() {
    if (!state.jsonFileName) {
      throw new Error("请先选择规则 JSON");
    }
    clearOutput();
    clearSaveStatus();
    clearTestOverlay();
    await loadRulesFromSelectedFile();
  }

  function updateRuleTypeLockView() {
    el.ruleType.disabled = state.ruleTypeLocked;
    if (el.ruleTypeLockTip) {
      el.ruleTypeLockTip.classList.toggle("hidden", !state.ruleTypeLocked);
    }
  }

  function setRuleType(nextType) {
    state.ruleType = AllowedRuleTypes.has(nextType) ? nextType : (state.ruleSchemas[0] ? state.ruleSchemas[0].type : "image");
    el.ruleType.value = state.ruleType;
    renderDynamicFieldGroups();
    updateFieldVisibility();
  }

  function resolveTaskAndJson(dirPath, jsonName) {
    const parts = splitPath(dirPath);
    if (parts.length === 0) {
      throw new Error("请先选择规则目录");
    }
    if (!jsonName) {
      throw new Error("请先选择规则 JSON");
    }
    const taskName = parts[0];
    const relParts = parts.slice(1);
    relParts.push(jsonName);
    return {
      taskName,
      jsonRelPath: joinPath(relParts),
    };
  }

  async function fetchRuleSource(dirPath) {
    const query = new URLSearchParams({ dir_path: dirPath || "" }).toString();
    return api(`${API_PREFIX}/api/rules/source?${query}`);
  }

  function updateCurrentDirText() {
    if (!el.currentDir) {
      return;
    }
    const text = state.currentDirPath ? state.currentDirPath : "";
    el.currentDir.textContent = text;
  }

  function hasLoadedRuleSource() {
    return Boolean(state.taskName && state.jsonRelPath);
  }

  function getNormalizedRuleSearchKeyword() {
    return String(state.ruleSearchKeyword || "").trim().toLowerCase();
  }

  function resetRuleSearch() {
    state.ruleSearchKeyword = "";
    if (el.ruleSearchInput) {
      el.ruleSearchInput.value = "";
    }
  }

  function updateRuleSearchVisibility() {
    const visible = hasLoadedRuleSource();
    if (el.ruleSearchBox) {
      el.ruleSearchBox.classList.toggle("hidden", !visible);
    }
    if (el.ruleSearchInput) {
      el.ruleSearchInput.disabled = !visible;
      if (!visible) {
        el.ruleSearchInput.value = "";
      }
    }
  }

  function clearRuleBinding() {
    state.taskName = "";
    state.jsonRelPath = "";
    resetRuleSearch();
    updateRuleSearchVisibility();
  }

  function updateRuleSourceActionVisibility() {
    const canCreate = !state.sourceLeafHasDirs && !state.jsonFileName;
    const canDelete = Boolean(state.jsonFileName);

    el.newJsonName.classList.toggle("hidden", !canCreate);
    el.createJsonBtn.classList.toggle("hidden", !canCreate);
    el.deleteJsonBtn.classList.toggle("hidden", !canDelete);
  }

  function createBreadcrumbSelect(values, selected, placeholder) {
    const select = document.createElement("select");
    select.className = "breadcrumb-select";
    createOption(select, "", placeholder);
    for (const name of values) {
      createOption(select, name, name);
    }
    if (selected && values.includes(selected)) {
      select.value = selected;
    }
    return select;
  }

  async function rebuildDirSelectors(targetPath = "", targetJson = "", autoLoad = false) {
    const preferredDirs = splitPath(targetPath);
    const preferredJson = String(targetJson || "").trim();

    state.sourceDirs = [];
    state.sourceLeafHasDirs = false;
    state.sourceLeafJsonFiles = [];
    state.currentDirPath = "";
    state.jsonFileName = "";

    el.dirSelectors.innerHTML = "";

    const rootPrefix = document.createElement("span");
    rootPrefix.className = "breadcrumb-root-prefix";
    rootPrefix.textContent = "/";
    el.dirSelectors.appendChild(rootPrefix);

    let currentPath = "";
    let data = await fetchRuleSource(currentPath);
    let depth = 0;

    while (true) {
      const dirs = Array.isArray(data.directories) ? data.directories : [];
      const expected = preferredDirs[depth] || "";
      const selectedDir = expected && dirs.includes(expected) ? expected : "";

      if (dirs.length > 0) {
        if (depth > 0) {
          const sep = document.createElement("span");
          sep.className = "breadcrumb-sep";
          sep.textContent = "/";
          el.dirSelectors.appendChild(sep);
        }

        const dirSelect = createBreadcrumbSelect(dirs, selectedDir, "选择目录");
        dirSelect.dataset.depth = String(depth);
        dirSelect.addEventListener(
          "change",
          withError(async () => {
            const changeDepth = Number.parseInt(dirSelect.dataset.depth || "0", 10);
            const nextDirs = state.sourceDirs.slice(0, changeDepth);
            if (dirSelect.value) {
              nextDirs.push(dirSelect.value);
            }
            clearRuleBinding();
            await rebuildDirSelectors(joinPath(nextDirs), "", false);
          }),
        );
        el.dirSelectors.appendChild(dirSelect);
      }

      if (dirs.length === 0 || !selectedDir) {
        state.sourceDirs = preferredDirs.slice(0, depth);
        state.currentDirPath = joinPath(state.sourceDirs);
        state.sourceLeafHasDirs = dirs.length > 0 && !selectedDir;
        state.sourceLeafJsonFiles = state.sourceLeafHasDirs ? [] : (Array.isArray(data.json_files) ? data.json_files : []);
        break;
      }

      state.sourceDirs.push(selectedDir);
      currentPath = joinPath(state.sourceDirs);
      data = await fetchRuleSource(currentPath);
      depth += 1;
    }

    if (!state.sourceLeafHasDirs) {
      if (state.sourceDirs.length > 0) {
        const sep = document.createElement("span");
        sep.className = "breadcrumb-sep";
        sep.textContent = "/";
        el.dirSelectors.appendChild(sep);
      }

      const jsonSelect = createBreadcrumbSelect(state.sourceLeafJsonFiles, preferredJson, "选择 JSON");
      if (preferredJson && state.sourceLeafJsonFiles.includes(preferredJson)) {
        state.jsonFileName = preferredJson;
        jsonSelect.value = preferredJson;
      } else {
        state.jsonFileName = "";
      }

      jsonSelect.addEventListener(
        "change",
        withError(async () => {
          state.jsonFileName = jsonSelect.value || "";
          if (!state.jsonFileName) {
            clearRuleBinding();
            updateRuleSourceActionVisibility();
            updateTestButtonVisibility();
            return;
          }
          await loadRulesFromSelectedFile();
          updateRuleSourceActionVisibility();
        }),
      );
      el.dirSelectors.appendChild(jsonSelect);
    }

    updateCurrentDirText();
    updateRuleSourceActionVisibility();

    if (autoLoad && state.jsonFileName) {
      await loadRulesFromSelectedFile();
    }
  }

  async function createJsonFile() {
    const fileName = el.newJsonName.value.trim();
    if (!fileName) {
      throw new Error("请输入新 JSON 名称");
    }
    if (state.sourceLeafHasDirs) {
      throw new Error("当前路径下还有子目录，请继续选择到最终目录");
    }

    const res = await api(`${API_PREFIX}/api/rules/source/create`, {
      method: "POST",
      body: JSON.stringify({
        dir_path: state.currentDirPath,
        file_name: fileName,
      }),
    });

    const parts = splitPath(res.file || "");
    if (parts.length === 0) {
      throw new Error("新增 JSON 返回路径异常");
    }
    const created = parts.pop() || "";
    const dirPath = joinPath(parts);

    el.newJsonName.value = "";
    await rebuildDirSelectors(dirPath, created, true);
    showMessage(`已新增规则文件: ${created}`, "ok");
  }

  async function deleteJsonFile() {
    const jsonName = state.jsonFileName;
    if (!jsonName) {
      throw new Error("请先选择要删除的 JSON 文件");
    }

    const confirmed = window.confirm(`确认删除 ${jsonName} ?`);
    if (!confirmed) {
      return;
    }

    await api(`${API_PREFIX}/api/rules/source/delete`, {
      method: "POST",
      body: JSON.stringify({
        dir_path: state.currentDirPath,
        file_name: jsonName,
      }),
    });

    state.jsonFileName = "";
    clearRuleBinding();
    await rebuildDirSelectors(state.currentDirPath, "", false);
    showMessage(`已删除规则文件: ${jsonName}`, "ok");
  }

  async function loadRulesFromSelectedFile() {
    if (!state.jsonFileName) {
      throw new Error("请先选择规则 JSON");
    }

    const pair = resolveTaskAndJson(state.currentDirPath, state.jsonFileName);
    const previousTaskName = state.taskName;
    const previousJsonRelPath = state.jsonRelPath;
    state.taskName = pair.taskName;
    state.jsonRelPath = pair.jsonRelPath;
    if (state.taskName !== previousTaskName || state.jsonRelPath !== previousJsonRelPath) {
      resetRuleSearch();
    }
    updateRuleSearchVisibility();

    const query = new URLSearchParams({
      task_name: state.taskName,
      json_relpath: state.jsonRelPath,
    }).toString();

    const res = await api(`${API_PREFIX}/api/rules/load?${query}`);
    const loadedType = res.rule_type;
    const validType = AllowedRuleTypes.has(loadedType) ? loadedType : "image";

    state.ruleTypeLocked = Boolean(res.rule_type_locked);
    setRuleType(validType);
    updateRuleTypeLockView();

    if (state.ruleType === "list") {
      resetListMeta();
      state.listMeta = {
        ...state.listMeta,
        ...(res.list_meta || {}),
      };
      state.listMeta.roiBack = state.listMeta.roiBack || "0,0,100,100";
    } else {
      resetListMeta();
    }

    state.rules = normalizeLoadedRules(state.ruleType, res.rules || []);
    if (state.rules.length === 0) {
      state.ruleTypeLocked = false;
      updateRuleTypeLockView();
      state.rules = [defaultRuleByType(state.ruleType)];
    }
    state.activeRuleIndex = 0;

    renderRuleList();
    clearDirty();
    clearTestOverlay();
    clearSaveStatus();
    showMessage(`已加载 ${state.taskName}/${state.jsonRelPath} (${state.ruleType})`, "ok");

    await refreshActiveRuleImageExists();
  }

  function collectRulesPayload() {
    if (!state.sessionId) {
      throw new Error("会话不存在，请刷新页面重试");
    }
    if (!state.taskName || !state.jsonRelPath) {
      throw new Error("请先选择规则 JSON");
    }

    syncRoiToRule();


    const rules = state.rules.map((rule) => {
      const cleaned = { ...rule };
      delete cleaned.__autoImageName;
      if (state.ruleType === "list") {
        delete cleaned.description;
      }
      return cleaned;
    });

    const payload = {
      session_id: state.sessionId,
      task_name: state.taskName,
      json_relpath: state.jsonRelPath,
      rule_type: state.ruleType,
      rules,
    };

    if (state.ruleType === "list") {
      payload.list_meta = {
        name: state.listMeta.name,
        direction: state.listMeta.direction,
        type: state.listMeta.type,
        roiBack: state.listMeta.roiBack,
        description: state.listMeta.description,
      };
    }

    return payload;
  }

  async function persistRules() {
    try {
      const payload = collectRulesPayload();
      const result = await api(`${API_PREFIX}/api/rules/save`, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      const ok = result.generate_status === "success";
      setSaveStatus(ok);
      const outputTitle = ok
        ? "保存成功"
        : (result.save_status === "success" ? "规则已保存，生成失败" : "保存失败");
      appendOutput(outputTitle, result);

      clearDirty();
      await rebuildDirSelectors(state.currentDirPath, state.jsonFileName, false);
      await refreshActiveRuleImageExists();
      return { ok, result };
    } catch (error) {
      setSaveStatus(false);
      appendOutput("保存失败", error?.message || String(error));
      throw error;
    }
  }

  async function saveRules() {
    const { ok, result } = await persistRules();
    const assetsFile = String(result.assets_file || "").trim();
    if (ok) {
      const suffix = assetsFile ? `，已生成 ${assetsFile}` : "";
      showMessage(`已保存规则，共 ${result.rule_count || 0} 条${suffix}`, "ok");
      return;
    }
    const targetText = assetsFile ? `，目标文件: ${assetsFile}` : "";
    showMessage(`规则已保存，但 assets.py 生成失败: ${result.error || "未知错误"}${targetText}`, "error");
  }
  async function saveImageCrop() {
    const rule = getCurrentRule();
    if (!rule) {
      throw new Error("请先选择规则项");
    }
    if (!state.currentImageId) {
      throw new Error("请先选择图片");
    }
    if (!state.taskName || !state.jsonRelPath) {
      throw new Error("请先选择规则 JSON");
    }

    syncRoiToRule();

    let imageName = "";
    if (state.ruleType === "image") {
      imageName = String(rule.imageName || "").trim();
      if (!imageName) {
        imageName = defaultImageNameForItem(rule.itemName || "image");
        rule.imageName = imageName;
      }
    } else if (isListImageRule()) {
      imageName = listImageNameForItem(rule.itemName || "");
      if (!imageName) {
        throw new Error("list 项缺少 itemName");
      }
    } else {
      imageName = defaultImageNameForItem(rule.itemName || "image");
    }

    const result = await api(`${API_PREFIX}/api/images/crop-save`, {
      method: "POST",
      body: JSON.stringify({
        session_id: state.sessionId,
        image_id: state.currentImageId,
        task_name: state.taskName,
        json_relpath: state.jsonRelPath,
        image_name: imageName,
        roi: rule.roiFront,
      }),
    });

    appendOutput("裁剪图片", result);
    showMessage(`图片已保存: ${result.target_image}`, "ok");

    if (isImagePreviewRule()) {
      const key = getRuleImageCacheKey(rule);
      if (key) {
        state.imagePreviewCache.set(key, true);
      }
    }

    refreshActiveRuleItem();
    await refreshActiveRuleImageExists();
  }

  async function deleteRuleLinkedImage(imageName) {
    return api(`${API_PREFIX}/api/rules/image/delete`, {
      method: "POST",
      body: JSON.stringify({
        task_name: state.taskName,
        json_relpath: state.jsonRelPath,
        image_name: imageName,
      }),
    });
  }

  async function deleteCurrentRule() {
    if (state.activeRuleIndex < 0) {
      return;
    }

    const previousRules = cloneRules(state.rules);
    const previousActiveRuleIndex = state.activeRuleIndex;
    const previousDirty = state.dirty;

    const removedIndex = previousActiveRuleIndex;
    const removed = previousRules[removedIndex];
    const itemName = String(removed?.itemName || "").trim() || `第 ${removedIndex + 1} 项`;
    const imageRule = canDeleteRuleLinkedImage(removed);
    const imageName = imageRule ? getRuleDeleteImageName(removed) : "";

    let deleteLinkedImage = false;
    if (imageRule) {
      const message = [
        "是否同时删除关联图像？",
        "点击“确定”：删除规则配置和关联图像",
        "点击“取消”：仅删除规则配置，保留关联图像",
      ].join("\n");
      deleteLinkedImage = window.confirm(message);
    }

    clearRuleImageCache(removed);
    state.rules.splice(removedIndex, 1);
    if (state.activeRuleIndex >= state.rules.length) {
      state.activeRuleIndex = state.rules.length - 1;
    }
    clearTestOverlay();
    renderRuleList();
    markDirty();

    let message = `已删除规则配置: ${itemName}`;
    let messageType = "ok";

    let saveResult = null;
    try {
      saveResult = await persistRules();
    } catch (_error) {
      state.rules = cloneRules(previousRules);
      state.activeRuleIndex = previousActiveRuleIndex;
      clearTestOverlay();
      renderRuleList();
      if (previousDirty) {
        markDirty();
      } else {
        clearDirty();
      }
      setSaveStatus(false);
      showMessage(`删除规则失败: ${itemName}，规则配置未保存`, "error");
      refreshActiveRuleImageExists().catch(() => {
        // ignore
      });
      return;
    }

    if (!saveResult.ok) {
      message = `已删除规则配置: ${itemName}，但 assets.py 生成失败`;
      if (deleteLinkedImage) {
        message += "，未删除关联图像";
      }
      showMessage(message, "error");
      return;
    }

    if (deleteLinkedImage) {
      if (!imageName || !state.taskName || !state.jsonRelPath) {
        const result = {
          removed: false,
          image_name: imageName,
          message: "缺少关联图像路径，未删除模板图",
        };
        appendOutput("删除规则关联图像", result);
        message = `已删除规则配置: ${itemName}，但未删除关联图像`;
        messageType = "error";
      } else {
        try {
          const result = await deleteRuleLinkedImage(imageName);
          clearRuleImageCacheByImageName(imageName);
          appendOutput("删除规则关联图像", result);
          if (result.removed) {
            message = `已删除规则配置与关联图像: ${itemName}`;
          } else {
            message = `已删除规则配置: ${itemName}，关联图像原本不存在`;
          }
        } catch (error) {
          appendOutput("删除规则关联图像失败", {
            image_name: imageName,
            message: error?.message || String(error),
          });
          message = `已删除规则配置: ${itemName}，但删除关联图像失败`;
          messageType = "error";
        }
      }
    } else if (imageRule) {
      message = `已删除规则配置: ${itemName}，保留关联图像`;
    }

    showMessage(message, messageType);
    refreshActiveRuleImageExists().catch(() => {
      // ignore
    });
  }
  function updateTestButtonVisibility() {
    const hasRule = Boolean(getCurrentRule());
    const subtype = getRuleSubtype();
    const canTestType = state.ruleType === "image"
      || state.ruleType === "ocr"
      || (state.ruleType === "list" && (subtype === "image" || subtype === "ocr"));
    let canUse = canTestType && hasRule && !!state.currentImageId && !!state.taskName && !!state.jsonRelPath;

    if (canUse && isImagePreviewRule()) {
      canUse = state.activeRuleImageExists || state.testOverlayActive;
    }

    if (state.testOverlayActive) {
      canUse = true;
    }

    el.testRuleBtn.classList.toggle("hidden", !canUse);
    el.testRuleBtn.textContent = state.testOverlayActive ? "清除" : "测试";
  }

  async function testCurrentRule() {
    if (state.testOverlayActive) {
      clearTestOverlay();
      appendOutput("清除测试框", "已清除 test_roi_front / test_roi_back");
      return;
    }

    const rule = getCurrentRule();
    if (!rule) {
      throw new Error("请先选择规则项");
    }
    if (!state.currentImageId) {
      throw new Error("请先选择图片");
    }
    if (!state.taskName || !state.jsonRelPath) {
      throw new Error("请先选择规则 JSON");
    }

    const payloadRule = { ...rule };
    delete payloadRule.__autoImageName;
    delete payloadRule.description;

    const payload = {
      session_id: state.sessionId,
      image_id: state.currentImageId,
      task_name: state.taskName,
      json_relpath: state.jsonRelPath,
      rule_type: state.ruleType,
      rule: payloadRule,
    };
    if (state.ruleType === "list") {
      payload.list_meta = {
        name: state.listMeta.name,
        direction: state.listMeta.direction,
        type: state.listMeta.type,
        roiBack: state.listMeta.roiBack,
        description: state.listMeta.description,
      };
    }

    const res = await api(`${API_PREFIX}/api/rules/test`, {
      method: "POST",
      body: JSON.stringify(payload),
    });

    const result = res.result || {};
    setTestOverlay(result.roiFront, result.roiBack);
    appendOutput("测试结果", result);
  }

  function updateEmulatorStatusView(data) {
    const status = data && typeof data === "object" ? { ...data } : {};
    if (!status.state) {
      status.state = "stopped";
    }
    state.emulatorStatus = status;
    el.emulatorStatus.textContent = JSON.stringify(status, null, 2);
  }

  function setEmulatorErrorStatus(message, extra = {}) {
    const text = String(message || extra.error || "模拟器预览出错").trim() || "模拟器预览出错";
    const base = state.emulatorStatus && typeof state.emulatorStatus === "object" ? state.emulatorStatus : {};
    updateEmulatorStatusView({
      ...base,
      ...extra,
      state: extra.state || "error",
      error: text,
    });
    return text;
  }

  async function syncEmulatorStatusAfterSocketIssue(message) {
    const text = setEmulatorErrorStatus(message);
    showMessage(text, "error");
    try {
      await refreshEmulatorStatus();
    } catch (error) {
      if (isInvalidSessionError(error)) {
        const recovered = await recoverSessionAfterInvalid();
        if (recovered) {
          return;
        }
      }
      const finalMessage = setEmulatorErrorStatus(error.message || String(error));
      showMessage(finalMessage, "error");
    }
  }

  function closeFrameSocket(markExpected = true) {
    if (state.ws) {
      state.wsCloseExpected = Boolean(markExpected);
      state.ws.close();
      state.ws = null;
    } else {
      state.wsCloseExpected = false;
    }
    if (state.wsImageUrl) {
      URL.revokeObjectURL(state.wsImageUrl);
      state.wsImageUrl = "";
    }
  }

  function openFrameSocket() {
    if (!state.sessionId) {
      return;
    }
    if (state.ws && (state.ws.readyState === WebSocket.OPEN || state.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    state.wsCloseExpected = false;
    const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = `${wsProtocol}://${window.location.host}${API_PREFIX}/ws/${encodeURIComponent(state.sessionId)}`;
    const socket = new WebSocket(wsUrl);
    socket.binaryType = "blob";

    socket.onmessage = (event) => {
      if (typeof event.data === "string") {
        try {
          const data = JSON.parse(event.data);
          if (data.event === "error") {
            closeFrameSocket();
            syncEmulatorStatusAfterSocketIssue(data.message || "模拟器预览出错").catch((error) => {
              console.error(error);
            });
          }
        } catch (_e) {
          // ignore
        }
        return;
      }

      const url = URL.createObjectURL(event.data);
      if (state.wsImageUrl) {
        URL.revokeObjectURL(state.wsImageUrl);
      }
      state.wsImageUrl = url;
      el.emulatorPreview.src = url;
    };

    socket.onerror = () => {
      closeFrameSocket();
      syncEmulatorStatusAfterSocketIssue("模拟器预览连接异常").catch((error) => {
        console.error(error);
      });
    };

    socket.onclose = () => {
      const expectedClose = state.wsCloseExpected;
      if (state.ws === socket) {
        state.ws = null;
      }
      state.wsCloseExpected = false;
      if (expectedClose || state.sourceMode !== "emulator" || state.sessionClosing) {
        return;
      }
      syncEmulatorStatusAfterSocketIssue("模拟器预览连接已断开").catch((error) => {
        console.error(error);
      });
    };

    state.ws = socket;
  }
  async function refreshEmulatorStatus() {
    if (!state.sessionId) {
      return;
    }
    const res = await api(`${API_PREFIX}/api/emulator/status?session_id=${encodeURIComponent(state.sessionId)}`);
    const status = res.emulator || {};
    updateEmulatorStatusView(status);

    if (state.sourceMode === "emulator" && status.state === "running") {
      openFrameSocket();
    }

    if (status.state !== "running" && status.state !== "starting") {
      closeFrameSocket();
    }
  }

  async function startEmulator() {
    if (!state.sessionId) {
      throw new Error("会话未初始化");
    }
    const configName = el.configName.value;
    if (!configName) {
      throw new Error("请先选择脚本配置");
    }

    const frameRate = Number.parseInt(el.frameRate.value, 10);
    const body = {
      session_id: state.sessionId,
      config_name: configName,
      frame_rate: Number.isFinite(frameRate) ? frameRate : 2,
    };

    const res = await api(`${API_PREFIX}/api/emulator/start`, {
      method: "POST",
      body: JSON.stringify(body),
    });

    updateEmulatorStatusView(res.emulator || {});
    await refreshEmulatorStatus();
    showMessage("模拟器会话已启动", "ok");
  }

  async function stopEmulator() {
    if (!state.sessionId) {
      return;
    }
    const res = await api(`${API_PREFIX}/api/emulator/stop`, {
      method: "POST",
      body: JSON.stringify({ session_id: state.sessionId }),
    });
    closeFrameSocket();
    updateEmulatorStatusView(res.emulator || {});
    showMessage("模拟器会话已停止", "ok");
  }

  async function captureEmulatorFrame() {
    if (!state.sessionId) {
      throw new Error("会话未初始化");
    }
    const result = await api(`${API_PREFIX}/api/emulator/capture`, {
      method: "POST",
      body: JSON.stringify({ session_id: state.sessionId }),
    });
    appendImages(result && result.image ? [result.image] : []);
    showMessage("已将当前帧加入图片列表", "ok");
  }

  function setSourceMode(mode) {
    state.sourceMode = mode;
    el.sourceMode.value = mode;

    const isLocal = mode === "local";
    el.localControls.classList.toggle("hidden", !isLocal);
    el.emulatorControls.classList.toggle("hidden", isLocal);

    if (isLocal) {
      closeFrameSocket();
    } else {
      refreshEmulatorStatus().catch(async (error) => {
        if (isInvalidSessionError(error)) {
          const recovered = await recoverSessionAfterInvalid();
          if (recovered) {
            return;
          }
        }
        showMessage(error.message || String(error), "error");
      });
    }
  }

  async function createSession() {
    const res = await api(`${API_PREFIX}/api/session`, { method: "POST" });
    const session = res.session || {};
    state.sessionId = session.session_id || "";
    state.sessionClosing = false;
    el.sessionId.textContent = state.sessionId || "-";
  }

  async function loadConfigs() {
    const res = await api(`${API_PREFIX}/api/configs`);
    fillSelect(el.configName, res.configs || [], "请选择脚本配置");
  }

  function bindEvents() {
    el.sourceMode.addEventListener("change", () => setSourceMode(el.sourceMode.value));

    el.uploadBtn.addEventListener("click", withError(uploadImages));
    el.refreshImagesBtn.addEventListener("click", withError(refreshImages));
    el.removeImagesBtn.addEventListener("click", withError(removeSelectedImages));
    el.clearImagesBtn.addEventListener("click", withError(clearImages));
    updateRemoveImagesButtonState();

    el.startEmulatorBtn.addEventListener("click", withError(startEmulator));
    el.stopEmulatorBtn.addEventListener("click", withError(stopEmulator));
    el.captureBtn.addEventListener("click", withError(captureEmulatorFrame));

    el.mainImage.addEventListener("load", adjustStageByImage);

    const applyFrontInput = () => applyRoiInputToRule("front");
    const applyBackInput = () => applyRoiInputToRule("back");

    el.roiFrontValue.addEventListener("change", applyFrontInput);
    el.roiFrontValue.addEventListener("blur", applyFrontInput);
    el.roiFrontValue.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        applyFrontInput();
      }
    });

    el.roiBackValue.addEventListener("change", applyBackInput);
    el.roiBackValue.addEventListener("blur", applyBackInput);
    el.roiBackValue.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        applyBackInput();
      }
    });

    el.createJsonBtn.addEventListener("click", withError(createJsonFile));
    el.deleteJsonBtn.addEventListener("click", withError(deleteJsonFile));
    if (el.ruleSearchInput) {
      el.ruleSearchInput.addEventListener("input", () => {
        state.ruleSearchKeyword = el.ruleSearchInput.value || "";
        clearTestOverlay();
        renderRuleList();
      });
    }

    el.ruleType.addEventListener("change", () => {
      if (state.ruleTypeLocked) {
        el.ruleType.value = state.ruleType;
        return;
      }
      setRuleType(el.ruleType.value);
      state.rules = [defaultRuleByType(state.ruleType)];
      state.activeRuleIndex = 0;
      clearTestOverlay();
      renderRuleList();
      markDirty();
      showMessage(`已切换规则类型: ${state.ruleType}`, "ok");
    });

    el.addRuleBtn.addEventListener("click", () => {
      const rule = createRuleFromCurrentCanvas(state.ruleType);
      rule.itemName = `item_${state.rules.length + 1}`;
      if (state.ruleType === "image") {
        rule.imageName = defaultImageNameForItem(rule.itemName);
      }
      state.rules.push(rule);
      state.activeRuleIndex = state.rules.length - 1;
      clearTestOverlay();
      renderRuleList();
      markDirty();
      refreshActiveRuleImageExists().catch(() => {
        // ignore
      });
    });

    el.deleteRuleBtn.addEventListener("click", withError(deleteCurrentRule));

    if (el.refreshRulesBtn) {
      el.refreshRulesBtn.addEventListener("click", withError(refreshRulesList));
    }

    el.testRuleBtn.addEventListener("click", withError(testCurrentRule));
    el.saveImageBtn.addEventListener("click", withError(saveImageCrop));
    el.saveRulesBtn.addEventListener("click", withError(saveRules));
    el.clearOutputBtn.addEventListener("click", clearOutput);
  }


  window.addEventListener("resize", () => {
    adjustStageByImage();
  });

  function cleanup(reason = "page_unload") {
    if (state.statusTimer) {
      clearInterval(state.statusTimer);
      state.statusTimer = null;
    }
    closeFrameSocket();
    closeSession(reason, true).catch(() => {
      // 页面关闭阶段忽略网络错误
    });
  }

  async function init() {
    setupRoiBox(el.roiFront);
    setupRoiBox(el.roiBack);
    await loadRuleSchemas();
    bindEvents();

    resetListMeta();
    state.rules = [defaultRuleByType(state.ruleType)];
    state.activeRuleIndex = 0;
    renderRuleList();

    await createSession();
    await Promise.all([loadConfigs(), rebuildDirSelectors("", "", false)]);
    await refreshImages();

    updateRuleTypeLockView();
    updateFieldVisibility();
    updateRuleSearchVisibility();
    setSourceMode("local");
    updateRuleSourceActionVisibility();
    clearOutput();
    clearSaveStatus();

    state.statusTimer = window.setInterval(() => {
      refreshEmulatorStatus().catch((error) => {
        console.error(error);
        if (isInvalidSessionError(error)) {
          recoverSessionAfterInvalid().catch((recoverError) => {
            console.error(recoverError);
          });
        }
      });
    }, 2500);

    window.addEventListener("pagehide", () => cleanup("pagehide"));
    window.addEventListener("beforeunload", () => cleanup("beforeunload"));
    showMessage("标注会话已就绪", "ok");
  }

  init().catch((error) => {
    console.error(error);
    showMessage(error.message || String(error), "error");
  });
})();
