(function () {
  const storageKey = "oas_annotator_layout_v3";
  const themeKey = "oas_annotator_theme_v1";

  const leftWindow = document.getElementById("leftWindow");
  const rightWindow = document.getElementById("rightWindow");
  const leftContent = document.getElementById("leftContent");
  const rightContent = document.getElementById("rightContent");
  const leftStack = document.getElementById("leftStack");
  const rightStack = document.getElementById("rightStack");
  const leftSplitter = document.getElementById("leftSplitter");
  const rightSplitter = document.getElementById("rightSplitter");
  const leftPanelSplitter = document.getElementById("leftPanelSplitter");
  const rightPanelSplitter = document.getElementById("rightPanelSplitter");
  const themeSelect = document.getElementById("themeSelect");
  const appRoot = document.querySelector(".app");
  const ruleEditorPanel = document.getElementById("ruleEditorPanel");
  const ruleList = document.getElementById("ruleList");
  const ruleListSplitter = document.getElementById("ruleListSplitter");

  const outputDockToggle = document.getElementById("outputDockToggle");
  const bottomOutputDock = document.getElementById("bottomOutputDock");
  const bottomOutputResize = document.getElementById("bottomOutputResize");

  if (
    !leftWindow ||
    !rightWindow ||
    !leftContent ||
    !rightContent ||
    !leftStack ||
    !rightStack ||
    !leftSplitter ||
    !rightSplitter ||
    !leftPanelSplitter ||
    !rightPanelSplitter
  ) {
    return;
  }

  const minLeftWidth = 280;
  const maxLeftWidth = 760;
  const minRightWidth = 320;
  const maxRightWidth = 760;
  const minPanelHeight = 140;
  const minDockHeight = 140;
  const minRuleListHeight = 220;

  const leftButtons = Array.from(document.querySelectorAll(".rail-btn[data-window='left']"));
  const rightButtons = Array.from(document.querySelectorAll(".rail-btn[data-window='right']"));

  const leftOrder = leftButtons.map((btn) => btn.dataset.panelId).filter(Boolean);
  const rightOrder = rightButtons.map((btn) => btn.dataset.panelId).filter(Boolean);

  const defaultState = {
    leftWidth: 360,
    rightWidth: 460,
    leftPanels: leftOrder.slice(),
    rightPanels: rightOrder.slice(),
    leftSplitRatio: 0.5,
    rightSplitRatio: 0.5,
    outputDockOpen: false,
    outputDockHeight: 220,
    ruleListHeight: minRuleListHeight,
  };

  const state = loadState();
  normalizeState();

  applyTheme(loadTheme());
  applyWidths();
  applySide("left");
  applySide("right");
  applyBottomDock();
  updateRuleEditorCompactMode();
  applyRuleListHeight();

  if (ruleEditorPanel && typeof ResizeObserver !== "undefined") {
    const observer = new ResizeObserver(() => {
      updateRuleEditorCompactMode();
    });
    observer.observe(ruleEditorPanel);
  }

  leftButtons.forEach((button) => {
    button.addEventListener("click", () => {
      togglePanel("left", button.dataset.panelId || "");
    });
  });

  rightButtons.forEach((button) => {
    button.addEventListener("click", () => {
      togglePanel("right", button.dataset.panelId || "");
    });
  });

  leftSplitter.addEventListener("mousedown", (event) => {
    if (!state.leftPanels.length) {
      return;
    }
    startSideDrag("left", event);
  });

  rightSplitter.addEventListener("mousedown", (event) => {
    if (!state.rightPanels.length) {
      return;
    }
    startSideDrag("right", event);
  });

  leftPanelSplitter.addEventListener("mousedown", (event) => {
    if (!leftStack.classList.contains("stack-two-open")) {
      return;
    }
    startPanelDrag("left", event);
  });

  rightPanelSplitter.addEventListener("mousedown", (event) => {
    if (!rightStack.classList.contains("stack-two-open")) {
      return;
    }
    startPanelDrag("right", event);
  });

  if (ruleListSplitter && ruleList) {
    ruleListSplitter.addEventListener("mousedown", (event) => {
      startRuleListDrag(event);
    });
  }

  if (outputDockToggle && bottomOutputDock) {
    outputDockToggle.addEventListener("click", () => {
      state.outputDockOpen = !state.outputDockOpen;
      applyBottomDock();
      saveState();
      requestStageReflow();
    });
  }

  if (bottomOutputResize && bottomOutputDock) {
    bottomOutputResize.addEventListener("mousedown", (event) => {
      if (!state.outputDockOpen) {
        return;
      }
      startBottomDockDrag(event);
    });
  }

  if (themeSelect) {
    themeSelect.addEventListener("change", () => {
      const theme = normalizeTheme(themeSelect.value);
      applyTheme(theme);
      saveTheme(theme);
    });
  }

  window.addEventListener("resize", () => {
    updatePanelHeights("left", false);
    updatePanelHeights("right", false);
    updateRuleEditorCompactMode();
    applyRuleListHeight();
    if (state.outputDockOpen) {
      state.outputDockHeight = clamp(state.outputDockHeight, minDockHeight, getDockMaxHeight());
      applyBottomDock();
    }
  });

  function updateRuleEditorCompactMode() {
    if (!ruleEditorPanel) {
      return;
    }
    const compact = ruleEditorPanel.clientWidth > 0 && ruleEditorPanel.clientWidth < 430;
    ruleEditorPanel.classList.toggle("rule-editor-compact", compact);
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function normalizeTheme(theme) {
    return theme === "light" ? "light" : "dark";
  }

  function loadTheme() {
    try {
      const raw = window.localStorage.getItem(themeKey);
      return normalizeTheme(raw || "dark");
    } catch (_error) {
      return "dark";
    }
  }

  function saveTheme(theme) {
    try {
      window.localStorage.setItem(themeKey, normalizeTheme(theme));
    } catch (_error) {
      // ignore
    }
  }

  function applyTheme(theme) {
    const normalized = normalizeTheme(theme);
    document.documentElement.setAttribute("data-theme", normalized);
    if (themeSelect) {
      themeSelect.value = normalized;
    }
  }

  function loadState() {
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (!raw) {
        return { ...defaultState };
      }
      const parsed = JSON.parse(raw);
      return {
        leftWidth: Number(parsed.leftWidth) || defaultState.leftWidth,
        rightWidth: Number(parsed.rightWidth) || defaultState.rightWidth,
        leftPanels: Array.isArray(parsed.leftPanels) ? parsed.leftPanels.slice() : defaultState.leftPanels.slice(),
        rightPanels: Array.isArray(parsed.rightPanels) ? parsed.rightPanels.slice() : defaultState.rightPanels.slice(),
        leftSplitRatio: Number(parsed.leftSplitRatio),
        rightSplitRatio: Number(parsed.rightSplitRatio),
        outputDockOpen: Boolean(parsed.outputDockOpen),
        outputDockHeight: Number(parsed.outputDockHeight),
        ruleListHeight: Number(parsed.ruleListHeight),
      };
    } catch (_error) {
      return { ...defaultState };
    }
  }

  function saveState() {
    try {
      window.localStorage.setItem(
        storageKey,
        JSON.stringify({
          leftWidth: state.leftWidth,
          rightWidth: state.rightWidth,
          leftPanels: state.leftPanels,
          rightPanels: state.rightPanels,
          leftSplitRatio: state.leftSplitRatio,
          rightSplitRatio: state.rightSplitRatio,
          outputDockOpen: state.outputDockOpen,
          outputDockHeight: state.outputDockHeight,
          ruleListHeight: state.ruleListHeight,
        }),
      );
    } catch (_error) {
      // ignore
    }
  }

  function normalizeState() {
    state.leftWidth = clamp(state.leftWidth, minLeftWidth, maxLeftWidth);
    state.rightWidth = clamp(state.rightWidth, minRightWidth, maxRightWidth);
    state.leftPanels = leftOrder.filter((id) => state.leftPanels.includes(id));
    state.rightPanels = rightOrder.filter((id) => state.rightPanels.includes(id));

    if (state.leftPanels.length === 0) {
      state.leftPanels = leftOrder.slice();
    }
    if (state.rightPanels.length === 0) {
      state.rightPanels = rightOrder.slice();
    }

    state.leftSplitRatio = Number.isFinite(state.leftSplitRatio) ? clamp(state.leftSplitRatio, 0.2, 0.8) : 0.5;
    state.rightSplitRatio = Number.isFinite(state.rightSplitRatio) ? clamp(state.rightSplitRatio, 0.2, 0.8) : 0.5;
    state.outputDockHeight = Number.isFinite(state.outputDockHeight) ? clamp(state.outputDockHeight, minDockHeight, getDockMaxHeight()) : 220;
    state.ruleListHeight = Number.isFinite(state.ruleListHeight) ? clamp(state.ruleListHeight, minRuleListHeight, getRuleListMaxHeight()) : minRuleListHeight;
  }

  function applyWidths() {
    leftContent.style.width = `${state.leftWidth}px`;
    rightContent.style.width = `${state.rightWidth}px`;
  }

  function getDockMaxHeight() {
    return Math.max(minDockHeight, Math.floor(window.innerHeight * 0.72));
  }

  function getRuleListMaxHeight() {
    if (!ruleEditorPanel) {
      return 1200;
    }
    const panelHeight = Math.max(0, ruleEditorPanel.clientHeight || 0);
    if (panelHeight <= 0) {
      return 1200;
    }
    return Math.max(minRuleListHeight, Math.min(1200, Math.floor(panelHeight * 1.2)));
  }

  function applyRuleListHeight() {
    if (!ruleList) {
      return;
    }
    state.ruleListHeight = clamp(state.ruleListHeight, minRuleListHeight, getRuleListMaxHeight());
    ruleList.style.height = `${Math.round(state.ruleListHeight)}px`;
  }

  function applyBottomDockInset(open) {
    const dockOpen = Boolean(open);
    const inset = dockOpen ? Math.max(minDockHeight, state.outputDockHeight) : 0;
    document.documentElement.style.setProperty("--bottom-dock-space", `${inset}px`);
    if (appRoot) {
      appRoot.classList.toggle("dock-open", dockOpen);
    }
  }

  function applyBottomDock() {
    if (!bottomOutputDock || !outputDockToggle) {
      return;
    }

    const open = Boolean(state.outputDockOpen);
    outputDockToggle.classList.toggle("active", open);
    bottomOutputDock.classList.toggle("hidden", !open);
    applyBottomDockInset(open);

    if (!open) {
      return;
    }

    state.outputDockHeight = clamp(state.outputDockHeight, minDockHeight, getDockMaxHeight());
    bottomOutputDock.style.height = `${state.outputDockHeight}px`;
    applyBottomDockInset(true);
  }

  function togglePanel(side, panelId) {
    if (!panelId) {
      return;
    }

    const key = side === "left" ? "leftPanels" : "rightPanels";
    const order = side === "left" ? leftOrder : rightOrder;
    const values = state[key].slice();
    const index = values.indexOf(panelId);

    if (index >= 0) {
      values.splice(index, 1);
    } else {
      values.push(panelId);
    }

    state[key] = order.filter((id) => values.includes(id));
    applySide(side);
    updateRuleEditorCompactMode();
    requestStageReflow();
    saveState();
  }

  function applySide(side) {
    const stack = side === "left" ? leftStack : rightStack;
    const windowEl = side === "left" ? leftWindow : rightWindow;
    const splitter = side === "left" ? leftSplitter : rightSplitter;
    const buttons = side === "left" ? leftButtons : rightButtons;
    const panelSplitter = side === "left" ? leftPanelSplitter : rightPanelSplitter;
    const key = side === "left" ? "leftPanels" : "rightPanels";

    const activePanels = state[key];
    const activeSet = new Set(activePanels);
    const open = activePanels.length > 0;

    windowEl.classList.toggle("collapsed", !open);
    splitter.classList.toggle("disabled", !open);
    stack.classList.toggle("stack-icon-mode", open);

    buttons.forEach((button) => {
      const id = button.dataset.panelId || "";
      button.classList.toggle("active", activeSet.has(id));
    });

    const panelList = Array.from(stack.children).filter((node) => node.classList && node.classList.contains("panel"));
    panelList.forEach((panel) => {
      const isActive = activeSet.has(panel.id);
      panel.classList.toggle("panel-slot-hidden", !isActive);
      panel.classList.toggle("panel-slot-active", isActive);
      panel.classList.remove("top-slot", "bottom-slot");
      panel.style.removeProperty("height");
      panel.style.removeProperty("order");
    });

    panelSplitter.classList.add("disabled");
    panelSplitter.style.removeProperty("order");
    stack.classList.remove("stack-two-open");

    if (!open) {
      requestStageReflow();
      return;
    }

    if (activePanels.length === 1) {
      const panel = document.getElementById(activePanels[0]);
      if (panel) {
        panel.style.order = "1";
      }
      return;
    }

    const topPanel = document.getElementById(activePanels[0]);
    const bottomPanel = document.getElementById(activePanels[1]);

    if (!topPanel || !bottomPanel) {
      return;
    }

    stack.classList.add("stack-two-open");
    panelSplitter.classList.remove("disabled");

    topPanel.classList.add("top-slot");
    bottomPanel.classList.add("bottom-slot");

    topPanel.style.order = "1";
    panelSplitter.style.order = "2";
    bottomPanel.style.order = "3";

    updatePanelHeights(side, false);
  }

  function updatePanelHeights(side, shouldReflow) {
    const stack = side === "left" ? leftStack : rightStack;
    const panelSplitter = side === "left" ? leftPanelSplitter : rightPanelSplitter;
    const ratioKey = side === "left" ? "leftSplitRatio" : "rightSplitRatio";

    if (!stack.classList.contains("stack-two-open")) {
      return;
    }

    const topPanel = stack.querySelector(".panel-slot-active.top-slot");
    const bottomPanel = stack.querySelector(".panel-slot-active.bottom-slot");
    if (!topPanel || !bottomPanel) {
      return;
    }

    const splitterHeight = panelSplitter.offsetHeight || 8;
    const totalHeight = stack.clientHeight;
    const available = Math.max(minPanelHeight * 2, totalHeight - splitterHeight);

    let ratio = Number(state[ratioKey]);
    ratio = Number.isFinite(ratio) ? clamp(ratio, 0.2, 0.8) : 0.5;

    let topHeight = Math.round(available * ratio);
    topHeight = clamp(topHeight, minPanelHeight, available - minPanelHeight);
    const bottomHeight = available - topHeight;

    state[ratioKey] = topHeight / available;

    topPanel.style.height = `${topHeight}px`;
    bottomPanel.style.height = `${bottomHeight}px`;

    if (shouldReflow) {
      requestStageReflow();
    }
  }

  function startSideDrag(side, event) {
    event.preventDefault();

    const startX = event.clientX;
    const startWidth = side === "left" ? state.leftWidth : state.rightWidth;

    document.body.classList.add("layout-resizing");

    const onMove = (moveEvent) => {
      const delta = moveEvent.clientX - startX;
      if (side === "left") {
        state.leftWidth = clamp(startWidth + delta, minLeftWidth, maxLeftWidth);
        leftContent.style.width = `${state.leftWidth}px`;
      } else {
        state.rightWidth = clamp(startWidth - delta, minRightWidth, maxRightWidth);
        rightContent.style.width = `${state.rightWidth}px`;
      }
      updateRuleEditorCompactMode();
    };

    const onUp = () => {
      document.body.classList.remove("layout-resizing");
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      saveState();
      requestStageReflow();
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  function startPanelDrag(side, event) {
    event.preventDefault();

    const stack = side === "left" ? leftStack : rightStack;
    const panelSplitter = side === "left" ? leftPanelSplitter : rightPanelSplitter;
    const ratioKey = side === "left" ? "leftSplitRatio" : "rightSplitRatio";

    document.body.classList.add("layout-resizing");

    const onMove = (moveEvent) => {
      const rect = stack.getBoundingClientRect();
      const splitterHeight = panelSplitter.offsetHeight || 8;
      const available = Math.max(minPanelHeight * 2, rect.height - splitterHeight);

      const cursorY = clamp(moveEvent.clientY - rect.top, 0, rect.height);
      const ratio = clamp(cursorY / Math.max(1, available), 0.2, 0.8);

      state[ratioKey] = ratio;
      updatePanelHeights(side, false);
    };

    const onUp = () => {
      document.body.classList.remove("layout-resizing");
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      saveState();
      requestStageReflow();
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  function startRuleListDrag(event) {
    if (!ruleList) {
      return;
    }

    event.preventDefault();

    const startY = event.clientY;
    const startHeight = ruleList.getBoundingClientRect().height || state.ruleListHeight || minRuleListHeight;

    document.body.classList.add("rule-list-resizing");

    const onMove = (moveEvent) => {
      const delta = moveEvent.clientY - startY;
      state.ruleListHeight = clamp(startHeight + delta, minRuleListHeight, getRuleListMaxHeight());
      ruleList.style.height = `${Math.round(state.ruleListHeight)}px`;
    };

    const onUp = () => {
      document.body.classList.remove("rule-list-resizing");
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      saveState();
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  function startBottomDockDrag(event) {
    if (!bottomOutputDock) {
      return;
    }

    event.preventDefault();

    const startY = event.clientY;
    const startHeight = state.outputDockHeight;

    document.body.classList.add("bottom-dock-resizing");

    const onMove = (moveEvent) => {
      const delta = startY - moveEvent.clientY;
      state.outputDockHeight = clamp(startHeight + delta, minDockHeight, getDockMaxHeight());
      bottomOutputDock.style.height = `${state.outputDockHeight}px`;
      applyBottomDockInset(true);
    };

    const onUp = () => {
      document.body.classList.remove("bottom-dock-resizing");
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      saveState();
      requestStageReflow();
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  function requestStageReflow() {
    window.requestAnimationFrame(() => {
      window.dispatchEvent(new Event("resize"));
    });
  }
})();







