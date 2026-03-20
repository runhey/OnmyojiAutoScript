(function () {
  const STATIC_PREFIX = "/tool/annotator/static";

  const widgets = [
    { mountId: "topbarMount", name: "topbar", script: "topbar.js" },
    { mountId: "leftWindowMount", name: "left-window", script: "left-window.js" },
    { mountId: "centerPanelMount", name: "center-panel", script: "center-panel.js" },
    { mountId: "rightWindowMount", name: "right-window", script: "right-window.js" },
  ];

  function ensureRegistry() {
    if (!window.OASAnnotatorWidgets) {
      window.OASAnnotatorWidgets = {};
    }
    return window.OASAnnotatorWidgets;
  }

  async function fetchWidget(name) {
    const response = await fetch(`${STATIC_PREFIX}/widget/${name}.html`, { cache: "no-cache" });
    if (!response.ok) {
      throw new Error(`加载组件失败: ${name} (${response.status})`);
    }
    return response.text();
  }

  async function mountWidgets() {
    for (const widget of widgets) {
      const mount = document.getElementById(widget.mountId);
      if (!mount) {
        throw new Error(`缺少组件挂载点: ${widget.mountId}`);
      }
      mount.innerHTML = await fetchWidget(widget.name);
    }
  }

  function loadScript(path) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = path;
      script.async = false;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error(`脚本加载失败: ${path}`));
      document.body.appendChild(script);
    });
  }

  async function loadComponentScripts() {
    for (const widget of widgets) {
      await loadScript(`${STATIC_PREFIX}/js/${widget.script}`);
    }

    const registry = ensureRegistry();
    for (const widget of widgets) {
      const component = registry[widget.name];
      if (component && typeof component.mount === "function") {
        component.mount();
      }
    }
  }

  async function loadRuntimeScripts() {
    // 保持原有初始化顺序：先布局脚本，再业务脚本。
    await loadScript(`${STATIC_PREFIX}/js/layout-ui.js`);
    await loadScript(`${STATIC_PREFIX}/js/app.js`);
  }

  function showBootError(error) {
    console.error(error);
    const mount = document.createElement("pre");
    mount.className = "small-output";
    mount.textContent = `页面初始化失败: ${error.message || String(error)}`;
    document.body.appendChild(mount);
  }

  async function bootstrap() {
    ensureRegistry();
    await mountWidgets();
    await loadComponentScripts();
    await loadRuntimeScripts();
  }

  bootstrap().catch(showBootError);
})();
