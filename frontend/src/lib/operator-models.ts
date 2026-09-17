import { GEMINI_KEY_EVENT, GEMINI_KEY_STORAGE, hasGeminiKey, maskGeminiKey } from "./gemini-key";

export const OPERATOR_EVENT = "rivalradar:operator-models";
export const DEEPSEEK_KEY_STORAGE = "rivalradar.operator.deepseekKey";
export const NVIDIA_KEY_STORAGE = "rivalradar.operator.nvidiaKey";
export const AGNES_KEY_STORAGE = "rivalradar.operator.agnesKey";
export const TEXT_MODEL_STORAGE = "rivalradar.operator.textModel";
export const IMAGE_MODEL_STORAGE = "rivalradar.operator.imageModel";

export type TextModel = "gemini" | "deepseek" | "gptoss";
export type ImageModel = "nano_banana" | "agnes" | "nvidia_flux";
export type Vendor = "gemini" | "deepseek" | "nvidia" | "agnes";

export type OperatorState = {
  gemini: string;
  deepseek: string;
  nvidia: string;
  agnes: string;
  textModel: TextModel;
  imageModel: ImageModel;
};

const TEXT_MODELS: TextModel[] = ["gemini", "deepseek", "gptoss"];
const IMAGE_MODELS: ImageModel[] = ["nano_banana", "agnes", "nvidia_flux"];

function read(storageKey: string): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(storageKey)?.trim() ?? "";
  } catch {
    return "";
  }
}

function write(storageKey: string, raw: string): string {
  const key = raw.trim();
  if (typeof window === "undefined") return key;
  try {
    if (key) window.localStorage.setItem(storageKey, key);
    else window.localStorage.removeItem(storageKey);
  } catch {
    // private mode
  }
  return key;
}

function emit(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(OPERATOR_EVENT));
  window.dispatchEvent(new Event(GEMINI_KEY_EVENT));
}

export function hasOperatorKey(key: string): boolean {
  return hasGeminiKey(key);
}

export function maskOperatorKey(key: string): string {
  return maskGeminiKey(key);
}

export function loadOperatorState(): OperatorState {
  const textRaw = read(TEXT_MODEL_STORAGE);
  const imageRaw = read(IMAGE_MODEL_STORAGE);
  return {
    gemini: read(GEMINI_KEY_STORAGE),
    deepseek: read(DEEPSEEK_KEY_STORAGE),
    nvidia: read(NVIDIA_KEY_STORAGE),
    agnes: read(AGNES_KEY_STORAGE),
    // Defaults: gpt-oss text + Agnes image — server env keys drive them when
    // the operator hasn't pasted anything.
    textModel: TEXT_MODELS.includes(textRaw as TextModel) ? (textRaw as TextModel) : "gptoss",
    imageModel: IMAGE_MODELS.includes(imageRaw as ImageModel)
      ? (imageRaw as ImageModel)
      : "agnes",
  };
}

export function saveOperatorKey(vendor: Vendor, raw: string): string {
  const stored =
    vendor === "gemini"
      ? write(GEMINI_KEY_STORAGE, raw)
      : vendor === "deepseek"
        ? write(DEEPSEEK_KEY_STORAGE, raw)
        : vendor === "nvidia"
          ? write(NVIDIA_KEY_STORAGE, raw)
          : write(AGNES_KEY_STORAGE, raw);
  emit();
  return stored;
}

export function saveTextModel(model: TextModel): TextModel {
  write(TEXT_MODEL_STORAGE, model);
  emit();
  return model;
}

export function saveImageModel(model: ImageModel): ImageModel {
  write(IMAGE_MODEL_STORAGE, model);
  emit();
  return model;
}

export function resolveTextModel(state: OperatorState): TextModel | null {
  const order: TextModel[] = [state.textModel, "gptoss", "gemini", "deepseek"];
  const seen = new Set<TextModel>();
  for (const model of order) {
    if (seen.has(model)) continue;
    seen.add(model);
    if (model === "gemini" && hasOperatorKey(state.gemini)) return "gemini";
    if (model === "deepseek" && hasOperatorKey(state.deepseek)) return "deepseek";
    if (model === "gptoss" && hasOperatorKey(state.nvidia)) return "gptoss";
  }
  return null;
}

export function resolveImageModel(state: OperatorState): ImageModel | null {
  if (state.imageModel === "agnes" && hasOperatorKey(state.agnes)) return "agnes";
  if (state.imageModel === "nvidia_flux" && hasOperatorKey(state.nvidia)) return "nvidia_flux";
  if (state.imageModel === "nano_banana" && hasOperatorKey(state.gemini)) return "nano_banana";
  if (hasOperatorKey(state.agnes)) return "agnes";
  if (hasOperatorKey(state.gemini)) return "nano_banana";
  if (hasOperatorKey(state.nvidia)) return "nvidia_flux";
  return null;
}

export function textModelLabel(model: TextModel): string {
  if (model === "deepseek") return "DeepSeek V4.1 Flash";
  if (model === "gptoss") return "GPT-OSS 20B";
  return "Gemini 3.6 Flash";
}

export function imageModelLabel(model: ImageModel | null): string {
  if (model === "agnes") return "Agnes Image 2.0 Flash";
  if (model === "nvidia_flux") return "NVIDIA FLUX";
  if (model === "nano_banana") return "Nano Banana 2";
  return "no image model";
}

export function chipLabel(
  state: OperatorState,
  serverDefaults?: { text_model: string | null; available: boolean } | null,
): string {
  const text = resolveTextModel(state);
  if (!text) {
    if (serverDefaults?.available && serverDefaults.text_model) {
      const label = textModelLabel(serverDefaults.text_model as TextModel);
      return `${label} · server`;
    }
    return "Models";
  }
  if (text === "deepseek") return `DeepSeek ${maskOperatorKey(state.deepseek)}`;
  if (text === "gptoss") return `OSS-20B ${maskOperatorKey(state.nvidia)}`;
  return `Gemini ${maskOperatorKey(state.gemini)}`;
}

export function operatorChipClasses(ready: boolean): string {
  return ready
    ? "border-primary/40 bg-primary/10 text-primary"
    : "animate-pulse border-primary/60 bg-primary/15 text-primary shadow-[0_0_28px_-4px_oklch(0.87_0.24_128)]";
}
