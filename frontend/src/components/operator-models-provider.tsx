"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
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
import { getServerModelDefaults, type ServerModelDefaults } from "@/lib/api";

type OperatorModelsContextValue = {
  state: OperatorState;
  readyText: boolean;
  readyImage: boolean;
  textModel: TextModel | null;
  imageModel: ImageModel | null;
  /** True when the effective model comes from server env keys, not the chip. */
  serverText: boolean;
  serverImage: boolean;
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
    agnes: "",
    textModel: "gptoss",
    imageModel: "agnes",
  } satisfies OperatorState);
}

export function OperatorModelsProvider({ children }: { children: ReactNode }) {
  const raw = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const state = useMemo<OperatorState>(() => JSON.parse(raw) as OperatorState, [raw]);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [serverDefaults, setServerDefaults] = useState<ServerModelDefaults | null>(null);

  useEffect(() => {
    let alive = true;
    getServerModelDefaults()
      .then((defaults) => {
        if (alive) setServerDefaults(defaults);
      })
      .catch(() => {
        /* gateway down — chip keys still work */
      });
    return () => {
      alive = false;
    };
  }, []);

  const localText = resolveTextModel(state);
  const localImage = resolveImageModel(state);
  const serverImageModel =
    localImage === null && serverDefaults?.image_model
      ? (serverDefaults.image_model as ImageModel)
      : null;
  const serverTextModel =
    localText === null && serverDefaults?.text_model
      ? (serverDefaults.text_model as TextModel)
      : null;
  const textModel = localText ?? serverTextModel;
  const imageModel = localImage ?? serverImageModel;

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
      serverText: localText === null && serverTextModel !== null,
      serverImage: localImage === null && serverImageModel !== null,
      chipLabel: chipLabel(state, serverDefaults),
      setKey,
      setTextModel: saveTextModel,
      setImageModel: saveImageModel,
      openSheet: () => setSheetOpen(true),
    }),
    [state, textModel, imageModel, localText, localImage, serverTextModel, serverImageModel, serverDefaults, setKey],
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
