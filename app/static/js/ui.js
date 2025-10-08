const MODALITY_RULES = {
  settlenet: {
    disabled: true,
    options: [{ label: "All", value: "all" }],
  },
  convnext_all: {
    disabled: true,
    options: [{ label: "All", value: "all" }],
  },
  convnext_bc: {
    disabled: true,
    options: [{ label: "Building Count", value: "building_count" }],
  },
  convnext_satellite: {
    disabled: true,
    options: [{ label: "Satellite", value: "satellite" }],
  },
};

const FALLBACK_MODALITIES = {
  disabled: false,
  options: [
    { label: "Satellite", value: "satellite" },
    { label: "Building Count", value: "building_count" },
    { label: "All", value: "all" },
  ],
};

export function createUIController({
  statusElement,
  progressIndicator,
  progressBarFill,
  progressLabel,
  uploadButton,
  fileNameDisplay,
}) {
  if (!statusElement || !progressIndicator || !progressBarFill || !progressLabel || !uploadButton || !fileNameDisplay) {
    throw new Error("Missing UI elements for controller initialisation");
  }

  const defaultUploadText = uploadButton.textContent || "Analyze";

  function setStatus(message, { isError = false } = {}) {
    statusElement.textContent = message;
    statusElement.classList.toggle("is-error", isError);
  }

  function resetProgress() {
    progressBarFill.style.width = "0%";
    progressLabel.textContent = "Queued…";
  }

  function showProgress() {
    progressIndicator.classList.add("is-active");
  }

  function hideProgress() {
    progressIndicator.classList.remove("is-active");
  }

  function disableUpload(label = "Processing…") {
    uploadButton.disabled = true;
    uploadButton.textContent = label;
  }

  function enableUpload() {
    uploadButton.disabled = false;
    uploadButton.textContent = defaultUploadText;
  }

  function setFileName(name) {
    fileNameDisplay.textContent = name || "No file chosen.";
  }

  function updateProgress(data) {
    const ratio = Math.max(0, Math.min(1, Number(data?.progress ?? 0)));
    progressBarFill.style.width = `${Math.round(ratio * 100)}%`;

    const total = data?.tiles_total ?? 0;
    const processed = data?.tiles_processed ?? 0;

    if (total > 0) {
      progressLabel.textContent = `Tiles ${processed}/${total}`;
    } else if (data?.message) {
      progressLabel.textContent = data.message;
    } else {
      progressLabel.textContent = "Processing…";
    }
  }

  function markComplete(message = "Done") {
    progressBarFill.style.width = "100%";
    progressLabel.textContent = message;
  }

  return {
    setStatus,
    resetProgress,
    showProgress,
    hideProgress,
    disableUpload,
    enableUpload,
    updateProgress,
    markComplete,
    setFileName,
  };
}

export function wireModelModalityBehavior(modelSelect, modalitySelect) {
  if (!modelSelect || !modalitySelect) return;

  function applyRules(modelValue) {
    const rule = MODALITY_RULES[modelValue] ?? FALLBACK_MODALITIES;

    modalitySelect.innerHTML = "";
    for (const option of rule.options) {
      const opt = new Option(option.label, option.value);
      modalitySelect.add(opt);
    }

    modalitySelect.disabled = rule.disabled;
    modalitySelect.selectedIndex = 0;
  }

  modelSelect.addEventListener("change", () => applyRules(modelSelect.value));
  applyRules(modelSelect.value);
}

export function bindHeroInteractions({ navLinks, navContainer, navHandle }) {
  const body = document.body;
  let navCloseTimeout = null;

  function clearNavCloseTimer() {
    if (navCloseTimeout) {
      window.clearTimeout(navCloseTimeout);
      navCloseTimeout = null;
    }
  }

  if (navContainer && navHandle) {
    const navLinksList = navContainer.querySelector(".nav-links");

    const setExpanded = (expanded) => {
      navContainer.classList.toggle("is-open", expanded);
      navHandle.setAttribute("aria-expanded", expanded ? "true" : "false");
    };

    const openNav = () => {
      clearNavCloseTimer();
      setExpanded(true);
    };

    const scheduleCloseNav = () => {
      clearNavCloseTimer();
      navCloseTimeout = window.setTimeout(() => setExpanded(false), 160);
    };

    navHandle.addEventListener("mouseenter", openNav);
    navHandle.addEventListener("focus", openNav);
    navHandle.addEventListener("mouseleave", scheduleCloseNav);
    navHandle.addEventListener("blur", scheduleCloseNav);
    navHandle.addEventListener("click", (event) => {
      event.preventDefault();
      const willOpen = !navContainer.classList.contains("is-open");
      if (willOpen) {
        openNav();
      } else {
        setExpanded(false);
      }
    });

  navLinksList?.addEventListener("mouseenter", openNav);
  navLinksList?.addEventListener("mouseleave", scheduleCloseNav);
    navLinksList?.addEventListener("click", () => {
      setExpanded(false);
    });

    setExpanded(false);
  }

  function handleScroll() {
    if (window.scrollY > 50) {
      body.classList.add("scrolled");
    } else {
      body.classList.remove("scrolled");
    }
  }

  window.addEventListener("scroll", handleScroll, { passive: true });

  navLinks?.forEach((link) => {
    if (link.dataset.scrollTop !== undefined) {
      link.addEventListener("click", (event) => {
        event.preventDefault();
        body.classList.remove("scrolled");
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    }
  });

  handleScroll();
}