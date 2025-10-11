const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB
const MODALITY_MAP = {
  satellite: "satellite",
  building_count: "bc",
  building_height: "bh",
  all: "all",
};

function getZipInstance() {
  const JSZip = window.JSZip;
  if (!JSZip) {
    throw new Error("ZIP validation unavailable. JSZip missing.");
  }
  return new JSZip();
}

async function validateZip(file) {
  const zip = getZipInstance();
  const zipContent = await zip.loadAsync(file);
  const tiffFiles = Object.keys(zipContent.files).filter((name) => /\.(tif|tiff)$/i.test(name));
  if (tiffFiles.length === 0) {
    throw new Error("ZIP file must contain at least one .tif or .tiff file");
  }
}

async function validateFile(file) {
  if (!/\.(tif|tiff|zip)$/i.test(file.name)) {
    throw new Error("Please upload a .tif, .tiff, or .zip file");
  }

  if (file.size > MAX_FILE_SIZE) {
    throw new Error("File size must be less than 100MB");
  }

  if (file.name.toLowerCase().endsWith(".zip")) {
    await validateZip(file);
  }
}

export function initializeUploadWorkflow({
  elements,
  ui,
  mapController,
  onResult,
  onError,
}) {
  const {
    fileInput,
    uploadButton,
    modelSelect,
    modalitySelect,
    opacitySlider,
    toggleInput,
    toggleMask,
  } = elements;

  if (!fileInput || !uploadButton || !modelSelect || !modalitySelect || !opacitySlider) {
    throw new Error("Missing required elements for upload workflow");
  }

  let activeJobId = null;
  let progressPollHandle = null;
  const jobContexts = new Map();

  function stopProgressPolling() {
    if (progressPollHandle) {
      window.clearTimeout(progressPollHandle);
      progressPollHandle = null;
    }
  }

  function resetWorkflowState() {
    stopProgressPolling();
    activeJobId = null;
    ui.hideProgress();
    ui.enableUpload();
  }

  async function pollProgress(jobId) {
    if (activeJobId !== jobId) return;

    const jobContext = jobContexts.get(jobId) ?? {};

    try {
      const response = await fetch(`/progress/${jobId}?t=${Date.now()}`);
      if (!response.ok) {
        throw new Error("Unable to retrieve progress updates.");
      }

      const data = await response.json();
      ui.updateProgress(data);

      if (data.status === "completed") {
        activeJobId = null;
        jobContexts.delete(jobId);
        ui.markComplete("Done");
        stopProgressPolling();
        resetWorkflowState();
        const model = jobContext.model ?? modelSelect.value;
        const modelLabel = jobContext.modelLabel
          ?? modelSelect.options[modelSelect.selectedIndex]?.text?.trim()
          ?? model;
        const opacity = jobContext.opacity ?? Number(opacitySlider.value);
        const fileName = jobContext.fileName
          || data.result?.metadata?.input_file
          || "uploaded input";
        onResult?.(data.result, {
          model,
          modelLabel,
          opacity,
          fileName,
        });
        return;
      }

      if (data.status === "failed") {
        jobContexts.delete(jobId);
        throw new Error(data.error || "Processing failed");
      }

      progressPollHandle = window.setTimeout(() => pollProgress(jobId), 1000);
    } catch (error) {
      jobContexts.delete(jobId);
      console.error("Progress polling error", error);
      const message = error instanceof Error ? error.message : String(error);
      resetWorkflowState();
      ui.setStatus(`Error: ${message}`, { isError: true });
      onError?.(message);
    }
  }

  function startProgressPolling(jobId, context = {}) {
    activeJobId = jobId;
    stopProgressPolling();
    ui.resetProgress();
    ui.showProgress();
    jobContexts.set(jobId, {
      ...context,
      jobId,
    });
    pollProgress(jobId);
  }

  async function handleUpload() {
    if (uploadButton.disabled) return;

    const file = fileInput.files?.[0];
    if (!file) {
      ui.setStatus("No file selected.", { isError: true });
      onError?.("No file selected");
      return;
    }

    try {
      await validateFile(file);
    } catch (validationError) {
      const message = validationError instanceof Error ? validationError.message : String(validationError);
      ui.setStatus(`Error: ${message}`, { isError: true });
      fileInput.value = "";
      ui.setFileName("No file chosen.");
      onError?.(message);
      return;
    }

    const modelType = modelSelect.value;
    const selectedModelOption = modelSelect.options[modelSelect.selectedIndex];
    const modelLabel = selectedModelOption?.text?.trim() || modelType;
    const opacityValue = Number(opacitySlider.value);
    const modalityKey = modalitySelect.value;
    const modality = MODALITY_MAP[modalityKey] ?? "satellite";

    ui.setStatus("Uploading…");
    ui.disableUpload();
    ui.hideProgress();
    ui.resetProgress();

    const payload = new FormData();
    payload.append("file", file);
    payload.append("model_type", modelType);
    payload.append("modality", modality);
    payload.append("threshold", "0.7");

    try {
      const response = await fetch("/upload", { method: "POST", body: payload });
      const responseData = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(responseData.error || `Server error: ${response.status}`);
      }

      if (!responseData.job_id) {
        throw new Error("Server did not return a job identifier.");
      }

      ui.setStatus("Upload complete.");
      startProgressPolling(responseData.job_id, {
        model: modelType,
        modelLabel,
        opacity: opacityValue,
        fileName: file.name,
      });
    } catch (error) {
      console.error("Upload error", error);
      const message = error instanceof Error ? error.message : String(error);
      resetWorkflowState();
      ui.setStatus(`Error: ${message}`, { isError: true });
      onError?.(message);
    }
  }

  async function handleFileChange() {
    stopProgressPolling();
    activeJobId = null;
    ui.hideProgress();
    ui.enableUpload();

    const file = fileInput.files?.[0];
    if (!file) {
      ui.setFileName("No file chosen.");
      ui.setStatus("Ready.");
      ui.resetProgress();
      return;
    }

    ui.setFileName(file.name);

    try {
      await validateFile(file);
      ui.setStatus("File ready.");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      ui.setStatus(`Error: ${message}`, { isError: true });
      fileInput.value = "";
      ui.setFileName("No file chosen.");
      onError?.(message);
    }
  }

  function handleOpacityChange() {
    mapController?.updateMaskOpacity(Number(opacitySlider.value));
  }

  function handleInputToggle() {
    mapController?.toggleInput(toggleInput.checked);
  }

  function handleMaskToggle() {
    mapController?.toggleMask(toggleMask.checked);
  }

  fileInput.addEventListener("change", handleFileChange);
  uploadButton.addEventListener("click", (event) => {
    event.preventDefault();
    handleUpload();
  });
  opacitySlider.addEventListener("input", handleOpacityChange);

  toggleInput?.addEventListener("change", handleInputToggle);
  toggleMask?.addEventListener("change", handleMaskToggle);

  return {
    teardown() {
      stopProgressPolling();
      fileInput.removeEventListener("change", handleFileChange);
      opacitySlider.removeEventListener("input", handleOpacityChange);
      toggleInput?.removeEventListener("change", handleInputToggle);
      toggleMask?.removeEventListener("change", handleMaskToggle);
    },
  };
}