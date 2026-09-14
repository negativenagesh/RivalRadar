"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import {
  OPERATOR_EVENT,
  type ImageModel,
  type OperatorState,
  type TextModel,
  type Vendor,
  chipLabel,
  hasOperatorKey,
  loadOperatorState,
  maskOperatorKey,
  resolveImageModel,
  resolveTextModel,
  saveImageModel,
  saveOperatorKey,
  saveTextModel,
} from "@/lib/operator-models";
import { GEMINI_KEY_EVENT } from "@/lib/gemini-key";
import { OperatorModelsSheet } from "@/components/operator-models-sheet";

type OperatorModelsContextValue = {
  state: OperatorState;
  readyText: boolean;
  readyImage: boolean;
  textModel: TextModel | null;
  imageModel: ImageModel | null;
  chipLabel: string;
  setKey: (vendor: Vendor, raw: string) => void;
  setTextModel: (model: TextModel) => void;
  setImageModel: (model: ImageModel) => void;
  openSheet: () => void;
};

const OperatorModelsContext = createContext<OperatorModelsContextValue | null>(null);

function subscribe(onStoreChange: () => void) {
  window.addEventListener(OPERATOR_EVENT, onStoreChange);
  window.addEventListener(GEMINI_KEY_EVENT, onStoreChange);
  window.addEventListener("storage", onStoreChange);
  return () => {
    window.removeEventListener(OPERATOR_EVENT, onStoreChange);
    window.removeEventListener(GEMINI_KEY_EVENT, onStoreChange);
    window.removeEventListener("storage", onStoreChange);
  };
}

function getSnapshot() {
  return JSON.stringify(loadOperatorState());
}

function getServerSnapshot() {
  return JSON.stringify({
    gemini: "",
    deepseek: "",
    nvidia: "",
    textModel: "gemini",
    imageModel: "nano_banana",
  } satisfies OperatorState);
}

export function OperatorModelsProvider({ children }: { children: ReactNode }) {
  const raw = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const state = useMemo<OperatorState>(() => JSON.parse(raw) as OperatorState, [raw]);
  const [sheetOpen, setSheetOpen] = useState(false);

  const textModel = resolveTextModel(state);
  const imageModel = resolveImageModel(state);

  const setKey = useCallback((vendor: Vendor, value: string) => {
    saveOperatorKey(vendor, value);
  }, []);

  const value = useMemo<OperatorModelsContextValue>(
    () => ({
      state,
      readyText: textModel !== null,
      readyImage: imageModel !== null,
      textModel,
      imageModel,
      chipLabel: chipLabel(state),
      setKey,
      setTextModel: saveTextModel,
      setImageModel: saveImageModel,
      openSheet: () => setSheetOpen(true),
    }),
    [state, textModel, imageModel, setKey],
  );

  return (
    <OperatorModelsContext.Provider value={value}>
      {children}
      <OperatorModelsSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        state={state}
        textModel={textModel}
        imageModel={imageModel}
        setKey={setKey}
        setTextModel={saveTextModel}
        setImageModel={saveImageModel}
      />
    </OperatorModelsContext.Provider>
  );
}

export function useOperatorModels(): OperatorModelsContextValue {
  const ctx = useContext(OperatorModelsContext);
  if (!ctx) {
    throw new Error("useOperatorModels must be used inside OperatorModelsProvider");
  }
  return ctx;
}

/** Back-compat for screens that only care about the Gemini slice. */
export function useGeminiKey() {
  const op = useOperatorModels();
  return {
    key: op.state.gemini,
    masked: maskOperatorKey(op.state.gemini),
    ready: hasOperatorKey(op.state.gemini),
    setKey: (raw: string) => op.setKey("gemini", raw),
    clear: () => op.setKey("gemini", ""),
  };
}
