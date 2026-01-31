"use client";

import React, { useState, useEffect } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  SelectGroup,
  SelectLabel,
  SelectSeparator,
} from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Loader2,
  AlertTriangle,
  Trash2,
  ChevronDown,
  Search,
  Info,
} from "lucide-react";
import {
  fetchApi,
  OpenRouterModel,
  saveOpenRouterApiKey,
  checkOpenRouterApiKey,
  removeOpenRouterApiKey,
  getOpenRouterModels,
  saveAnthropicApiKey,
  checkAnthropicApiKey,
  removeAnthropicApiKey,
  saveOpenAIApiKey,
  checkOpenAIApiKey,
  removeOpenAIApiKey,
} from "@/lib/api";
import { useAuth } from "@/components/MockAuthProvider";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";

// Gemini Models List (User Specified)
const geminiModels = [
  { id: "gemini-3-pro-preview", name: "Gemini 3.0 Pro Preview" },
  { id: "gemini-3-flash-preview", name: "Gemini 3.0 Flash Preview" },
  { id: "gemini-2.5-pro", name: "Gemini 2.5 Pro" },
  { id: "gemini-flash-latest", name: "Gemini Flash Latest" },
  { id: "gemini-flash-lite-latest", name: "Gemini Flash Lite Latest" },
];

// Anthropic Models List (User Specified, Pro Only)
const anthropicModels = [
  {
    id: "anthropic/claude-opus-4-1",
    name: "Anthropic Claude Opus 4.1",
  },
  {
    id: "anthropic/claude-sonnet-4-5",
    name: "Anthropic Claude Sonnet 4.5",
  },
  {
    id: "anthropic/claude-3-7-sonnet-latest",
    name: "Anthropic Claude 3.7 Sonnet",
  },
  {
    id: "anthropic/claude-haiku-4-5-20251001",
    name: "Anthropic Claude 4.5 Haiku",
  },
];

// OpenAI Models List (User Specified, Pro Only)
const openaiModels = [
  { id: "openai/gpt-5.1-2025-11-13", name: "OpenAI GPT-5.1" },
  { id: "openai/gpt-5-pro-2025-10-06", name: "OpenAI GPT-5 Pro" },
  { id: "openai/gpt-5-2025-08-07", name: "OpenAI GPT-5" },
  { id: "openai/gpt-5-mini-2025-08-07", name: "OpenAI GPT-5 Mini" },
  { id: "openai/gpt-5-nano-2025-08-07", name: "OpenAI GPT-5 Nano" },
];

// Embedding Models List - Object structure for consistency
const embeddingModels = [
  { id: "models/gemini-embedding-001", name: "Google Text Embedding 001" },
];

// Define the form schema using Zod
const formSchema = z.object({
  mainLLM: z.string().min(1, "Please select a Main LLM."),
  checkLLM: z.string().min(1, "Please select a Check LLM."),
  embeddingsModel: z.string().min(1, "Please select an Embeddings Model."),
  titleGenerationLLM: z
    .string()
    .min(1, "Please select a Title Generation LLM."),
  extractionLLM: z.string().min(1, "Please select an Extraction LLM."),
  knowledgeBaseQueryLLM: z
    .string()
    .min(1, "Please select a Knowledge Base Query LLM."),
  temperature: z.number().min(0).max(2),
  apiKey: z.string().optional(),
});

type FormData = z.infer<typeof formSchema>;

interface ApiKeyStatus {
  isSet: boolean;
  apiKey: string | null;
}

interface ModelSettings {
  mainLLM: string;
  checkLLM: string;
  embeddingsModel: string;
  titleGenerationLLM: string;
  extractionLLM: string;
  knowledgeBaseQueryLLM: string;
  temperature: number;
}

const presets = {
  fastest: {
    mainLLM: "gemini-flash-lite-latest",
    checkLLM: "gemini-flash-lite-latest",
    embeddingsModel: "models/gemini-embedding-001",
    titleGenerationLLM: "gemini-flash-lite-latest",
    extractionLLM: "gemini-flash-lite-latest",
    knowledgeBaseQueryLLM: "gemini-flash-lite-latest",
    temperature: 0.7,
  },
  intelligent: {
    mainLLM: "gemini-flash-latest",
    checkLLM: "gemini-flash-latest",
    embeddingsModel: "models/gemini-embedding-001",
    titleGenerationLLM: "gemini-flash-latest",
    extractionLLM: "gemini-flash-latest",
    knowledgeBaseQueryLLM: "gemini-flash-latest",
    temperature: 0.6,
  },
  mostIntelligent: {
    mainLLM: "gemini-3-pro-preview",
    checkLLM: "gemini-flash-latest",
    embeddingsModel: "models/gemini-embedding-001",
    titleGenerationLLM: "gemini-flash-latest",
    extractionLLM: "gemini-flash-latest",
    knowledgeBaseQueryLLM: "gemini-flash-latest",
    temperature: 0.5,
  },
};

interface SettingsFormProps {
  isProUser: boolean;
}


export function SettingsForm({ isProUser }: SettingsFormProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [apiKeyStatus, setApiKeyStatus] = useState<ApiKeyStatus>({
    isSet: false,
    apiKey: null,
  });
  const [showApiKey, setShowApiKey] = useState(false);
  const [currentApiKeyInput, setCurrentApiKeyInput] = useState("");

  const [openrouterApiKeyStatus, setOpenrouterApiKeyStatus] =
    useState<ApiKeyStatus>({ isSet: false, apiKey: null });
  const [showOpenRouterApiKey, setShowOpenRouterApiKey] = useState(false);
  const [currentOpenRouterApiKeyInput, setCurrentOpenRouterApiKeyInput] =
    useState("");
  const [showOpenRouterKeyWarning, setShowOpenRouterKeyWarning] =
    useState(false);

  const [anthropicApiKeyStatus, setAnthropicApiKeyStatus] =
    useState<ApiKeyStatus>({ isSet: false, apiKey: null });
  const [showAnthropicApiKey, setShowAnthropicApiKey] = useState(false);
  const [currentAnthropicApiKeyInput, setCurrentAnthropicApiKeyInput] =
    useState("");
  const [showAnthropicKeyWarning, setShowAnthropicKeyWarning] = useState(false);

  const [openaiApiKeyStatus, setOpenaiApiKeyStatus] = useState<ApiKeyStatus>({
    isSet: false,
    apiKey: null,
  });
  const [showOpenaiApiKey, setShowOpenaiApiKey] = useState(false);
  const [currentOpenaiApiKeyInput, setCurrentOpenaiApiKeyInput] = useState("");
  const [showOpenaiKeyWarning, setShowOpenaiKeyWarning] = useState(false);

  const [openrouterModels, setOpenrouterModels] = useState<OpenRouterModel[]>(
    []
  );
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [modelFilter, setModelFilter] = useState<
    "all" | "gemini" | "openrouter" | "anthropic" | "openai"
  >("all");
  const [modelSearchTerm, setModelSearchTerm] = useState("");

  const auth = useAuth();

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      mainLLM: presets.intelligent.mainLLM,
      checkLLM: presets.intelligent.checkLLM,
      embeddingsModel: embeddingModels[0].id,
      titleGenerationLLM: presets.intelligent.titleGenerationLLM,
      extractionLLM: presets.intelligent.extractionLLM,
      knowledgeBaseQueryLLM: presets.intelligent.knowledgeBaseQueryLLM,
      temperature: 0.7,
      apiKey: "",
    },
  });

  const watchedLLMFields = form.watch([
    "mainLLM",
    "checkLLM",
    "titleGenerationLLM",
    "extractionLLM",
    "knowledgeBaseQueryLLM",
  ]);

  useEffect(() => {
    if (!isProUser) {
      setShowOpenRouterKeyWarning(false);
      setShowAnthropicKeyWarning(false);
      setShowOpenaiKeyWarning(false);
      return;
    }
    const openRouterSelected = Object.values(watchedLLMFields).some(
      (modelId) =>
        typeof modelId === "string" && modelId.startsWith("openrouter/")
    );
    setShowOpenRouterKeyWarning(
      openRouterSelected && !openrouterApiKeyStatus.isSet
    );

    const anthropicSelected = Object.values(watchedLLMFields).some(
      (modelId) =>
        typeof modelId === "string" && modelId.startsWith("anthropic/")
    );
    setShowAnthropicKeyWarning(
      anthropicSelected && !anthropicApiKeyStatus.isSet
    );

    const openaiSelected = Object.values(watchedLLMFields).some(
      (modelId) => typeof modelId === "string" && modelId.startsWith("openai/")
    );
    setShowOpenaiKeyWarning(openaiSelected && !openaiApiKeyStatus.isSet);
  }, [
    watchedLLMFields,
    openrouterApiKeyStatus.isSet,
    anthropicApiKeyStatus.isSet,
    openaiApiKeyStatus.isSet,
    isProUser,
  ]);

  useEffect(() => {
    const fetchSettings = async (token: string | undefined) => {
      if (!token) {
        toast.error("Authentication token is missing.");
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      try {
        const fetchPromises: Promise<unknown>[] = [
          fetchApi<ApiKeyStatus>("/settings/api-key", {}, token),
          fetchApi<ModelSettings>("/settings/model", {}, token),
        ];
        if (isProUser) {
          fetchPromises.push(
            checkOpenRouterApiKey(token),
            getOpenRouterModels(token),
            checkAnthropicApiKey(token),
            checkOpenAIApiKey(token)
          );
        }
        const results = await Promise.all(fetchPromises);
        const geminiKeyStatus = results[0] as ApiKeyStatus;
        const modelSettingsData = results[1] as ModelSettings | null;
        setApiKeyStatus(geminiKeyStatus);

        if (isProUser && results.length > 2) {
          const orKeyStatus = results[2] as ApiKeyStatus;
          const orModels = results[3] as OpenRouterModel[];
          const anthropicKey = results[4] as ApiKeyStatus;
          const openaiKey = results[5] as ApiKeyStatus;
          setOpenrouterApiKeyStatus(orKeyStatus);
          setOpenrouterModels(orModels || []);
          setAnthropicApiKeyStatus(anthropicKey);
          setOpenaiApiKeyStatus(openaiKey);
        } else {
          setOpenrouterApiKeyStatus({ isSet: false, apiKey: null });
          setOpenrouterModels([]);
          setAnthropicApiKeyStatus({ isSet: false, apiKey: null });
          setOpenaiApiKeyStatus({ isSet: false, apiKey: null });
        }

        if (modelSettingsData) {
          form.reset({
            mainLLM: modelSettingsData.mainLLM || presets.intelligent.mainLLM,
            checkLLM:
              modelSettingsData.checkLLM || presets.intelligent.checkLLM,
            embeddingsModel:
              modelSettingsData.embeddingsModel ||
              presets.intelligent.embeddingsModel,
            titleGenerationLLM:
              modelSettingsData.titleGenerationLLM ||
              presets.intelligent.titleGenerationLLM,
            extractionLLM:
              modelSettingsData.extractionLLM ||
              presets.intelligent.extractionLLM,
            knowledgeBaseQueryLLM:
              modelSettingsData.knowledgeBaseQueryLLM ||
              presets.intelligent.knowledgeBaseQueryLLM,
            temperature:
              modelSettingsData.temperature ?? presets.intelligent.temperature,
            apiKey: "",
          });
          const initialPreset = determinePreset(modelSettingsData);
          setSelectedPreset(initialPreset);
          if (initialPreset === "custom") setIsAdvancedOpen(true);
        } else {
          const defaultSettings = presets.intelligent;
          setSelectedPreset("intelligent");
          form.reset({ ...defaultSettings, apiKey: "" });
        }
      } catch (err) {
        console.error("Failed to fetch settings:", err);
        toast.error("Failed to load settings.");
        const defaultSettings = presets.intelligent;
        setSelectedPreset("intelligent");
        form.reset({ ...defaultSettings, apiKey: "" });
      } finally {
        setIsLoading(false);
      }
    };
    if (!auth.isLoading && auth.isAuthenticated && auth.user?.id_token) {
      fetchSettings(auth.user.id_token);
    } else if (!auth.isLoading && !auth.isAuthenticated) {
      toast.error("Authentication required.");
      setIsLoading(false);
    }
  }, [
    auth.isLoading,
    auth.isAuthenticated,
    auth.user?.id_token,
    form,
    isProUser,
  ]);

  const determinePreset = (settings: ModelSettings): string => {
    for (const [presetName, presetValues] of Object.entries(presets)) {
      if (
        Object.keys(presetValues).every(
          (key) =>
            settings[key as keyof ModelSettings] ===
            presetValues[key as keyof ModelSettings]
        )
      ) {
        return presetName;
      }
    }
    return "custom";
  };

  const handleSaveApiKey = async () => {
    if (!currentApiKeyInput) return toast.error("API Key cannot be empty.");
    if (!auth.user?.id_token) return toast.error("Authentication required.");
    const toastId = toast.loading("Saving Gemini API Key...");
    setIsSubmitting(true);
    try {
      await fetchApi(
        "/settings/api-key",
        {
          method: "POST",
          body: JSON.stringify({ apiKey: currentApiKeyInput }),
        },
        auth.user.id_token
      );
      setApiKeyStatus({
        isSet: true,
        apiKey: "****" + currentApiKeyInput.slice(-4),
      });
      setCurrentApiKeyInput("");
      setShowApiKey(false);
      toast.success("Gemini API Key saved.", { id: toastId });
    } catch (err) {
      toast.error((err as Error).message || "Failed to save Gemini API Key.", {
        id: toastId,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemoveApiKey = async () => {
    if (!auth.user?.id_token) return toast.error("Authentication required.");
    const toastId = toast.loading("Removing Gemini API Key...");
    setIsSubmitting(true);
    try {
      await fetchApi(
        "/settings/api-key",
        { method: "DELETE" },
        auth.user.id_token
      );
      setApiKeyStatus({ isSet: false, apiKey: null });
      toast.success("Gemini API Key removed.", { id: toastId });
    } catch (err) {
      toast.error(
        (err as Error).message || "Failed to remove Gemini API Key.",
        { id: toastId }
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSaveOpenRouterApiKey = async () => {
    if (!currentOpenRouterApiKeyInput)
      return toast.error("OpenRouter API Key cannot be empty.");
    if (!auth.user?.id_token) return toast.error("Authentication required.");
    const toastId = toast.loading("Saving OpenRouter API Key...");
    setIsSubmitting(true);
    try {
      await saveOpenRouterApiKey(
        currentOpenRouterApiKeyInput,
        auth.user.id_token
      );
      setOpenrouterApiKeyStatus({
        isSet: true,
        apiKey: "****" + currentOpenRouterApiKeyInput.slice(-4),
      });
      setCurrentOpenRouterApiKeyInput("");
      setShowOpenRouterApiKey(false);
      toast.success("OpenRouter API Key saved.", { id: toastId });
    } catch (err) {
      toast.error(
        (err as Error).message || "Failed to save OpenRouter API Key.",
        { id: toastId }
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemoveOpenRouterApiKey = async () => {
    if (!auth.user?.id_token) return toast.error("Authentication required.");
    const toastId = toast.loading("Removing OpenRouter API Key...");
    setIsSubmitting(true);
    try {
      await removeOpenRouterApiKey(auth.user.id_token);
      setOpenrouterApiKeyStatus({ isSet: false, apiKey: null });
      toast.success("OpenRouter API Key removed.", { id: toastId });
    } catch (err) {
      toast.error(
        (err as Error).message || "Failed to remove OpenRouter API Key.",
        { id: toastId }
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSaveAnthropicApiKey = async () => {
    if (!currentAnthropicApiKeyInput)
      return toast.error("Anthropic API Key cannot be empty.");
    if (!auth.user?.id_token) return toast.error("Authentication required.");
    const toastId = toast.loading("Saving Anthropic API Key...");
    setIsSubmitting(true);
    try {
      await saveAnthropicApiKey(
        currentAnthropicApiKeyInput,
        auth.user.id_token
      );
      setAnthropicApiKeyStatus({
        isSet: true,
        apiKey: "****" + currentAnthropicApiKeyInput.slice(-4),
      });
      setCurrentAnthropicApiKeyInput("");
      setShowAnthropicApiKey(false);
      toast.success("Anthropic API Key saved.", { id: toastId });
    } catch (err) {
      toast.error(
        (err as Error).message || "Failed to save Anthropic API Key.",
        { id: toastId }
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemoveAnthropicApiKey = async () => {
    if (!auth.user?.id_token) return toast.error("Authentication required.");
    const toastId = toast.loading("Removing Anthropic API Key...");
    setIsSubmitting(true);
    try {
      await removeAnthropicApiKey(auth.user.id_token);
      setAnthropicApiKeyStatus({ isSet: false, apiKey: null });
      toast.success("Anthropic API Key removed.", { id: toastId });
    } catch (err) {
      toast.error(
        (err as Error).message || "Failed to remove Anthropic API Key.",
        { id: toastId }
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSaveOpenaiApiKey = async () => {
    if (!currentOpenaiApiKeyInput)
      return toast.error("OpenAI API Key cannot be empty.");
    if (!auth.user?.id_token) return toast.error("Authentication required.");
    const toastId = toast.loading("Saving OpenAI API Key...");
    setIsSubmitting(true);
    try {
      await saveOpenAIApiKey(currentOpenaiApiKeyInput, auth.user.id_token);
      setOpenaiApiKeyStatus({
        isSet: true,
        apiKey: "****" + currentOpenaiApiKeyInput.slice(-4),
      });
      setCurrentOpenaiApiKeyInput("");
      setShowOpenaiApiKey(false);
      toast.success("OpenAI API Key saved.", { id: toastId });
    } catch (err) {
      toast.error((err as Error).message || "Failed to save OpenAI API Key.", {
        id: toastId,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemoveOpenaiApiKey = async () => {
    if (!auth.user?.id_token) return toast.error("Authentication required.");
    const toastId = toast.loading("Removing OpenAI API Key...");
    setIsSubmitting(true);
    try {
      await removeOpenAIApiKey(auth.user.id_token);
      setOpenaiApiKeyStatus({ isSet: false, apiKey: null });
      toast.success("OpenAI API Key removed.", { id: toastId });
    } catch (err) {
      toast.error(
        (err as Error).message || "Failed to remove OpenAI API Key.",
        { id: toastId }
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePresetChange = (presetName: string) => {
    if (presetName === "custom") {
      setSelectedPreset("custom");
      setIsAdvancedOpen(true);
      return;
    }
    const presetValues = presets[presetName as keyof typeof presets];
    if (presetValues) {
      setSelectedPreset(presetName);
      form.reset({ ...presetValues, apiKey: "" }); // Reset form with preset values
      toast.success(`Applied '${presetName}' preset.`);
    }
  };

  const handleModelChange = () => {
    if (selectedPreset !== "custom") setSelectedPreset("custom");
  };

  const formatPresetLabel = (key: string) => {
    const spaced = key.replace(/([A-Z])/g, " $1").trim();
    return spaced.charAt(0).toUpperCase() + spaced.slice(1);
  };

  const availableModels = React.useMemo(() => {
    let models: { id: string; name: string; source: string }[] = [];
    if (modelFilter === "all" || modelFilter === "gemini")
      models = models.concat(
        geminiModels.map((m) => ({ ...m, source: "gemini" }))
      );
    if (isProUser && (modelFilter === "all" || modelFilter === "openrouter"))
      models = models.concat(
        openrouterModels.map((m) => ({
          id: `openrouter/${m.id}`,
          name: `${m.name} (OpenRouter)`,
          source: "openrouter",
        }))
      );
    if (isProUser && (modelFilter === "all" || modelFilter === "anthropic"))
      models = models.concat(
        anthropicModels.map((m) => ({ ...m, source: "anthropic" }))
      );
    if (isProUser && (modelFilter === "all" || modelFilter === "openai"))
      models = models.concat(
        openaiModels.map((m) => ({ ...m, source: "openai" }))
      );
    if (modelSearchTerm)
      return models.filter((model) =>
        model.name.toLowerCase().includes(modelSearchTerm.toLowerCase())
      );
    return models;
  }, [modelFilter, modelSearchTerm, openrouterModels, isProUser]);

  const embeddingModelsList = React.useMemo(
    () => embeddingModels.map((m) => ({ ...m, source: "gemini" })),
    []
  );

  // Add back the onSubmitModelSettings function
  async function onSubmitModelSettings(values: FormData) {
    if (!auth.user?.id_token) return toast.error("Authentication required.");
    const toastId = toast.loading("Saving model settings...");
    setIsSubmitting(true);
    try {
      await fetchApi(
        "/settings/model",
        { method: "POST", body: JSON.stringify(values) },
        auth.user.id_token
      );
      // setFullModelSettings(values); // This was removed as fullModelSettings is unused
      toast.success("Model settings saved.", { id: toastId });
    } catch (err) {
      toast.error((err as Error).message || "Failed to save model settings.", {
        id: toastId,
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading)
    return (
      <div className="flex justify-center items-center h-40">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );

  return (
    <Form {...form}>
      <div className="space-y-4 border-b border-border pb-6 mb-6">
        <h3 className="text-lg font-medium text-foreground">
          Gemini API Key (Required)
        </h3>
        <FormDescription className="text-muted-foreground">
          Your Google AI Studio API key is required for core functionality like
          embeddings. Get your key from{" "}
          <a
            href="https://aistudio.google.com/api-keys"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline"
          >
            Google AI Studio
          </a>
          . It&apos;s free.
        </FormDescription>
        {apiKeyStatus.isSet && !showApiKey ? (
          <div className="flex items-center gap-4 p-3 bg-accent/50 rounded-md border border-border">
            <span className="font-mono text-muted-foreground flex-grow">
              **********{apiKeyStatus.apiKey?.slice(-4)}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowApiKey(true)}
              disabled={isSubmitting}
            >
              Update Key
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleRemoveApiKey}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              <span className="ml-2">Remove</span>
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Input
              type="password"
              placeholder="Enter your Gemini API Key"
              value={currentApiKeyInput}
              onChange={(e) => setCurrentApiKeyInput(e.target.value)}
              className="flex-grow"
              disabled={isSubmitting}
            />
            <Button
              onClick={handleSaveApiKey}
              disabled={isSubmitting || !currentApiKeyInput}
              className="min-w-[80px]"
            >
              {isSubmitting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Save"
              )}
            </Button>
            {apiKeyStatus.isSet && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setShowApiKey(false);
                  setCurrentApiKeyInput("");
                }}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
            )}
          </div>
        )}
      </div>

      {/* OpenRouter Section */}
      <div className="space-y-4 border-b border-border pb-6 mb-6">
        <h3 className="text-lg font-medium text-foreground">
          OpenRouter API Key{" "}
        </h3>
        {isProUser && (
          <>
            <FormDescription className="text-muted-foreground">
              Pro Feature: Needed for OpenRouter models.{" "}
              <a
                href="https://openrouter.ai/keys"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline ml-1"
              >
                Get Key
              </a>
              .
            </FormDescription>
            {openrouterApiKeyStatus.isSet && !showOpenRouterApiKey ? (
              <div className="flex items-center gap-4 p-3 bg-accent/50 rounded-md border border-border">
                <span className="font-mono text-muted-foreground flex-grow">
                  **********{openrouterApiKeyStatus.apiKey?.slice(-4)}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowOpenRouterApiKey(true)}
                  disabled={isSubmitting}
                >
                  Update
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleRemoveOpenRouterApiKey}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                  <span className="ml-2">Remove</span>
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Input
                  type="password"
                  placeholder="sk-or-..."
                  value={currentOpenRouterApiKeyInput}
                  onChange={(e) =>
                    setCurrentOpenRouterApiKeyInput(e.target.value)
                  }
                  className="flex-grow"
                  disabled={isSubmitting}
                />
                <Button
                  onClick={handleSaveOpenRouterApiKey}
                  disabled={isSubmitting || !currentOpenRouterApiKeyInput}
                  className="min-w-[80px]"
                >
                  {isSubmitting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    "Save"
                  )}
                </Button>
                {openrouterApiKeyStatus.isSet && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setShowOpenRouterApiKey(false);
                      setCurrentOpenRouterApiKeyInput("");
                    }}
                    disabled={isSubmitting}
                  >
                    Cancel
                  </Button>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Anthropic Section */}
      <div className="space-y-4 border-b border-border pb-6 mb-6">
        <h3 className="text-lg font-medium text-foreground">
          Anthropic API Key
        </h3>
        {true && (
          <>
            <FormDescription className="text-muted-foreground">
              Pro Feature: Needed for Anthropic (Claude) models.
            </FormDescription>
            {anthropicApiKeyStatus.isSet && !showAnthropicApiKey ? (
              <div className="flex items-center gap-4 p-3 bg-accent/50 rounded-md border border-border">
                <span className="font-mono text-muted-foreground flex-grow">
                  **********{anthropicApiKeyStatus.apiKey?.slice(-4)}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowAnthropicApiKey(true)}
                  disabled={isSubmitting}
                >
                  Update
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleRemoveAnthropicApiKey}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                  <span className="ml-2">Remove</span>
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Input
                  type="password"
                  placeholder="Enter Anthropic API Key"
                  value={currentAnthropicApiKeyInput}
                  onChange={(e) =>
                    setCurrentAnthropicApiKeyInput(e.target.value)
                  }
                  className="flex-grow"
                  disabled={isSubmitting}
                />
                <Button
                  onClick={handleSaveAnthropicApiKey}
                  disabled={isSubmitting || !currentAnthropicApiKeyInput}
                  className="min-w-[80px]"
                >
                  {isSubmitting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    "Save"
                  )}
                </Button>
                {anthropicApiKeyStatus.isSet && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setShowAnthropicApiKey(false);
                      setCurrentAnthropicApiKeyInput("");
                    }}
                    disabled={isSubmitting}
                  >
                    Cancel
                  </Button>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* OpenAI Section */}
      <div className="space-y-4 border-b border-border pb-6 mb-6">
        <h3 className="text-lg font-medium text-foreground">
          OpenAI API Key
        </h3>
        {true && (
          <>
            <FormDescription className="text-muted-foreground">
              Pro Feature: Needed for direct OpenAI models.
            </FormDescription>
            {openaiApiKeyStatus.isSet && !showOpenaiApiKey ? (
              <div className="flex items-center gap-4 p-3 bg-accent/50 rounded-md border border-border">
                <span className="font-mono text-muted-foreground flex-grow">
                  **********{openaiApiKeyStatus.apiKey?.slice(-4)}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowOpenaiApiKey(true)}
                  disabled={isSubmitting}
                >
                  Update
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleRemoveOpenaiApiKey}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                  <span className="ml-2">Remove</span>
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Input
                  type="password"
                  placeholder="Enter OpenAI API Key (sk-...)"
                  value={currentOpenaiApiKeyInput}
                  onChange={(e) => setCurrentOpenaiApiKeyInput(e.target.value)}
                  className="flex-grow"
                  disabled={isSubmitting}
                />
                <Button
                  onClick={handleSaveOpenaiApiKey}
                  disabled={isSubmitting || !currentOpenaiApiKeyInput}
                  className="min-w-[80px]"
                >
                  {isSubmitting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    "Save"
                  )}
                </Button>
                {openaiApiKeyStatus.isSet && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setShowOpenaiApiKey(false);
                      setCurrentOpenaiApiKeyInput("");
                    }}
                    disabled={isSubmitting}
                  >
                    Cancel
                  </Button>
                )}
              </div>
            )}
          </>
        )}
      </div>

      <form
        onSubmit={form.handleSubmit(onSubmitModelSettings)}
        className="space-y-6"
      >
        <h3 className="text-lg font-medium text-foreground">
          Model Configuration
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="ghost" size="icon" className="ml-2 h-6 w-6">
                <Info className="h-4 w-4 text-muted-foreground" />
                <span className="sr-only">Info</span>
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[625px] bg-card border-border text-card-foreground">
              <DialogHeader>
                <DialogTitle>LLM Configuration Guide</DialogTitle>
                <DialogDescription>
                  Understand what each LLM setting controls.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4 text-sm">
                {[
                  {
                    title: "Main LLM",
                    desc: "Core creative tasks like chapter generation.",
                  },
                  {
                    title: "Check LLM",
                    desc: "Analytical tasks like title generation, codex extraction.",
                  },
                  {
                    title: "Embeddings Model",
                    desc: "Numerical representations for knowledge base. Requires Gemini.",
                  },
                  {
                    title: "Title Generation LLM",
                    desc: "Dedicated for chapter titles.",
                  },
                  {
                    title: "Extraction LLM",
                    desc: "Extracting structured info (codex items).",
                  },
                  {
                    title: "Knowledge Base Query LLM",
                    desc: "Processes KB chat queries.",
                  },
                  {
                    title: "Temperature",
                    desc: "Controls randomness (0.2 focused, 0.8 creative).",
                  },
                ].map((item) => (
                  <div
                    key={item.title}
                    className="grid grid-cols-[1fr_3fr] items-start gap-4"
                  >
                    <span className="font-semibold text-foreground">
                      {item.title}:
                    </span>
                    <span className="text-muted-foreground">{item.desc}</span>
                  </div>
                ))}
              </div>
            </DialogContent>
          </Dialog>
        </h3>

        <div className="space-y-2">
          <FormLabel className="text-foreground">
            Configuration Preset
          </FormLabel>
          <FormDescription className="text-muted-foreground pb-2">
            Choose a preset or select &apos;Custom&apos; via Advanced Settings.
          </FormDescription>
          <RadioGroup
            value={selectedPreset || "custom"}
            onValueChange={handlePresetChange}
            className="grid grid-cols-1 sm:grid-cols-3 gap-4"
          >
            {(Object.keys(presets) as Array<keyof typeof presets>).map(
              (presetKey) => (
                <FormItem
                  key={presetKey}
                  className="flex items-center space-x-3 space-y-0"
                >
                  <FormControl>
                    <RadioGroupItem
                      value={presetKey}
                      id={`preset-${presetKey}`}
                    />
                  </FormControl>
                  <FormLabel
                    htmlFor={`preset-${presetKey}`}
                    className="font-normal cursor-pointer"
                  >
                    {formatPresetLabel(presetKey)}
                  </FormLabel>
                </FormItem>
              )
            )}
          </RadioGroup>
        </div>

        <div className="flex justify-start pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
          >
            {isAdvancedOpen ? "Hide Advanced" : "Show Advanced"} Settings{" "}
            <ChevronDown
              className={`ml-2 h-4 w-4 transition-transform ${isAdvancedOpen ? "rotate-180" : ""
                }`}
            />
          </Button>
        </div>

        {isAdvancedOpen && (
          <div className="space-y-6 border-l-2 border-primary/20 pl-4 ml-1 pt-4 animate-in fade-in duration-300">
            {isProUser && (
              <div className="flex flex-wrap gap-2 items-center">
                <RadioGroup
                  value={modelFilter}
                  onValueChange={(v) =>
                    setModelFilter(
                      v as
                      | "all"
                      | "gemini"
                      | "openrouter"
                      | "anthropic"
                      | "openai"
                    )
                  }
                  className="flex flex-wrap gap-2"
                >
                  {["all", "gemini", "openrouter", "anthropic", "openai"].map(
                    (filter) => (
                      <FormItem
                        key={filter}
                        className="flex items-center space-x-1 space-y-0"
                      >
                        <FormControl>
                          <RadioGroupItem
                            value={filter}
                            id={`filter-${filter}`}
                          />
                        </FormControl>
                        <FormLabel
                          htmlFor={`filter-${filter}`}
                          className="font-normal cursor-pointer text-sm px-2 py-1 rounded-md border data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
                        >
                          {filter.charAt(0).toUpperCase() + filter.slice(1)}
                        </FormLabel>
                      </FormItem>
                    )
                  )}
                </RadioGroup>
                <div className="relative flex-grow min-w-[200px]">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    type="text"
                    placeholder="Search models..."
                    value={modelSearchTerm}
                    onChange={(e) => setModelSearchTerm(e.target.value)}
                    className="pl-10 h-9"
                  />
                </div>
              </div>
            )}

            {[
              {
                name: "mainLLM",
                label: "Main LLM",
                desc: "Primary model for core generation.",
              },
              {
                name: "checkLLM",
                label: "Check LLM",
                desc: "Model for validation tasks.",
              },
              {
                name: "titleGenerationLLM",
                label: "Title Generation LLM",
                desc: "Model for generating titles.",
              },
              {
                name: "extractionLLM",
                label: "Extraction LLM",
                desc: "Model for data extraction.",
              },
              {
                name: "knowledgeBaseQueryLLM",
                label: "Knowledge Base Query LLM",
                desc: "Model for KB queries.",
              },
            ].map((llmField) => (
              <FormField
                key={llmField.name}
                control={form.control}
                name={llmField.name as keyof FormData}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-foreground">
                      {llmField.label}
                    </FormLabel>
                    <Select
                      onValueChange={(value) => {
                        field.onChange(value);
                        handleModelChange();
                      }}
                      value={String(field.value || "")}
                      defaultValue={String(field.value || "")}
                      disabled={isSubmitting}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue
                            placeholder={`Select a ${llmField.label}`}
                          />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent className="bg-popover border-border text-popover-foreground max-h-[300px]">
                        {isProUser ? (
                          <>
                            <SelectGroup>
                              <SelectLabel>Gemini</SelectLabel>
                              {availableModels
                                .filter((m) => m.source === "gemini")
                                .map((model) => (
                                  <SelectItem
                                    key={model.id}
                                    value={model.id}
                                    className="hover:bg-accent focus:bg-accent"
                                  >
                                    {model.name}
                                  </SelectItem>
                                ))}
                            </SelectGroup>
                            <SelectSeparator />
                            <SelectGroup>
                              <SelectLabel>OpenRouter</SelectLabel>
                              {availableModels
                                .filter((m) => m.source === "openrouter")
                                .map((model) => (
                                  <SelectItem
                                    key={model.id}
                                    value={model.id}
                                    className="hover:bg-accent focus:bg-accent"
                                  >
                                    {model.name}
                                  </SelectItem>
                                ))}
                            </SelectGroup>
                            <SelectSeparator />
                            <SelectGroup>
                              <SelectLabel>Anthropic</SelectLabel>
                              {availableModels
                                .filter((m) => m.source === "anthropic")
                                .map((model) => (
                                  <SelectItem
                                    key={model.id}
                                    value={model.id}
                                    className="hover:bg-accent focus:bg-accent"
                                  >
                                    {model.name}
                                  </SelectItem>
                                ))}
                            </SelectGroup>
                            <SelectSeparator />
                            <SelectGroup>
                              <SelectLabel>OpenAI</SelectLabel>
                              {availableModels
                                .filter((m) => m.source === "openai")
                                .map((model) => (
                                  <SelectItem
                                    key={model.id}
                                    value={model.id}
                                    className="hover:bg-accent focus:bg-accent"
                                  >
                                    {model.name}
                                  </SelectItem>
                                ))}
                            </SelectGroup>
                          </>
                        ) : (
                          availableModels
                            .filter((m) => m.source === "gemini")
                            .map((model) => (
                              <SelectItem
                                key={model.id}
                                value={model.id}
                                className="hover:bg-accent focus:bg-accent"
                              >
                                {model.name}
                              </SelectItem>
                            ))
                        )}
                      </SelectContent>
                    </Select>
                    <FormDescription className="text-muted-foreground">
                      {llmField.desc}
                    </FormDescription>
                    <FormMessage className="text-destructive" />
                  </FormItem>
                )}
              />
            ))}

            <FormField
              control={form.control}
              name="embeddingsModel"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-foreground">
                    Embeddings Model
                  </FormLabel>
                  <Select
                    onValueChange={(value) => {
                      field.onChange(value);
                      handleModelChange();
                    }}
                    value={String(field.value || "")}
                    defaultValue={String(field.value || "")}
                    disabled={isSubmitting || true}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select Embeddings Model" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent className="bg-popover border-border text-popover-foreground">
                      {embeddingModelsList.map((model) => (
                        <SelectItem
                          key={model.id}
                          value={model.id}
                          className="hover:bg-accent focus:bg-accent"
                        >
                          {model.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormDescription className="text-muted-foreground">
                    Model for text embeddings (Requires Gemini API Key).
                  </FormDescription>
                  <FormMessage className="text-destructive" />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="temperature"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-foreground">
                    Temperature:{" "}
                    {typeof field.value === "number"
                      ? field.value.toFixed(1)
                      : "N/A"}
                  </FormLabel>
                  <FormControl>
                    <Controller
                      name="temperature"
                      control={form.control}
                      render={({ field: controllerField }) => (
                        <Slider
                          min={0}
                          max={2}
                          step={0.1}
                          defaultValue={[controllerField.value]}
                          onValueChange={(value) => {
                            controllerField.onChange(value[0]);
                            handleModelChange();
                          }}
                          disabled={isSubmitting}
                          className="pt-2"
                        />
                      )}
                    />
                  </FormControl>
                  <FormDescription className="text-muted-foreground">
                    Controls randomness (0.2 focused, 0.8 creative).
                  </FormDescription>
                  <FormMessage className="text-destructive" />
                </FormItem>
              )}
            />
          </div>
        )}

        {isProUser && showOpenRouterKeyWarning && (
          <Alert className="mt-4">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>OpenRouter API Key Missing</AlertTitle>
            <AlertDescription>
              OpenRouter model selected, but key not set. Add key above.
            </AlertDescription>
          </Alert>
        )}
        {isProUser && showAnthropicKeyWarning && (
          <Alert className="mt-4">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Anthropic API Key Missing</AlertTitle>
            <AlertDescription>
              Anthropic model selected, but key not set. Add key above.
            </AlertDescription>
          </Alert>
        )}
        {isProUser && showOpenaiKeyWarning && (
          <Alert className="mt-4">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>OpenAI API Key Missing</AlertTitle>
            <AlertDescription>
              OpenAI model selected, but key not set. Add key above.
            </AlertDescription>
          </Alert>
        )}

        <Alert className="mt-4 border-blue-500/50 bg-blue-500/10 text-blue-700 dark:text-blue-300">
          <Info className="h-4 w-4 text-blue-500" />
          <AlertTitle className="text-blue-600 dark:text-blue-400">
            Important Note on Embeddings
          </AlertTitle>
          <AlertDescription>
            ScrollWise uses Google&apos;s `gemini-embedding-001` for knowledge
            base embeddings. A Gemini API key is required for Codex, KB Chat,
            etc., even if other providers are used for generation.
          </AlertDescription>
        </Alert>

        <div className="flex justify-between pt-4">
          <Button
            type="submit"
            disabled={isSubmitting || isLoading}
            className="min-w-[120px]"
          >
            {isSubmitting || isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              "Save Settings"
            )}
          </Button>
        </div>
      </form>
    </Form>
  );
}
