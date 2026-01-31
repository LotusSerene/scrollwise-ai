"use client";

import React, { forwardRef, useImperativeHandle, useState } from "react";
import { useEditor, EditorContent, Editor, BubbleMenu } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Mention from "@tiptap/extension-mention";
import { suggestion } from "./editor/suggestion";
import {
  Bold,
  Italic,
  Strikethrough,
  Code,
  Undo,
  Redo,
  Save,
  Sparkles,
  Text,
  WrapText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Extension } from "@tiptap/core";
import { SuggestionOptions } from "@tiptap/suggestion";

// Custom extension to manage codexItems storage
const CodexStorage = Extension.create({
  name: "codexStorage",
  addStorage() {
    return {
      codexItems: [],
    };
  },
});

// MENU BAR COMPONENT
// ===================
const MenuBar = ({
  editor,
  onSave,
}: {
  editor: Editor | null;
  onSave: () => void;
}) => {
  if (!editor) {
    return null;
  }

  return (
    <div className="border border-input bg-transparent rounded-t-md p-1 flex items-center space-x-1">
      <Button
        onClick={() => editor.chain().focus().toggleBold().run()}
        disabled={!editor.can().chain().focus().toggleBold().run()}
        variant={editor.isActive("bold") ? "secondary" : "ghost"}
        size="icon"
        aria-label="Toggle bold"
      >
        <Bold className="h-4 w-4" />
      </Button>
      <Button
        onClick={() => editor.chain().focus().toggleItalic().run()}
        disabled={!editor.can().chain().focus().toggleItalic().run()}
        variant={editor.isActive("italic") ? "secondary" : "ghost"}
        size="icon"
        aria-label="Toggle italic"
      >
        <Italic className="h-4 w-4" />
      </Button>
      <Button
        onClick={() => editor.chain().focus().toggleStrike().run()}
        disabled={!editor.can().chain().focus().toggleStrike().run()}
        variant={editor.isActive("strike") ? "secondary" : "ghost"}
        size="icon"
        aria-label="Toggle strikethrough"
      >
        <Strikethrough className="h-4 w-4" />
      </Button>
      <Button
        onClick={() => editor.chain().focus().toggleCode().run()}
        disabled={!editor.can().chain().focus().toggleCode().run()}
        variant={editor.isActive("code") ? "secondary" : "ghost"}
        size="icon"
        aria-label="Toggle code"
      >
        <Code className="h-4 w-4" />
      </Button>
      <div className="flex-grow" />
      <Button
        onClick={() => editor.chain().focus().undo().run()}
        disabled={!editor.can().chain().focus().undo().run()}
        variant="ghost"
        size="icon"
        aria-label="Undo"
      >
        <Undo className="h-4 w-4" />
      </Button>
      <Button
        onClick={() => editor.chain().focus().redo().run()}
        disabled={!editor.can().chain().focus().redo().run()}
        variant="ghost"
        size="icon"
        aria-label="Redo"
      >
        <Redo className="h-4 w-4" />
      </Button>
      <Button onClick={onSave} variant="ghost" size="icon" aria-label="Save">
        <Save className="h-4 w-4" />
      </Button>
    </div>
  );
};

// MAIN RICH TEXT EDITOR COMPONENT
// ================================
interface RichTextEditorProps {
  content: string;
  onChange: (htmlContent: string) => void;
  onSave: () => void;
  editable?: boolean;
  codexItems: { id: string; name: string; type: string }[];
  onTextAction: (action: string, customPrompt?: string) => void;
  isActionLoading: boolean;
}

const RichTextEditor = forwardRef<Editor, RichTextEditorProps>(
  (
    {
      content,
      onChange,
      onSave,
      editable = true,
      codexItems,
      onTextAction,
      isActionLoading,
    },
    ref
  ) => {
    const [isCustomPromptOpen, setIsCustomPromptOpen] = useState(false);
    const [customPrompt, setCustomPrompt] = useState("");

    const editor = useEditor({
      extensions: [
        StarterKit,
        CodexStorage,
        Mention.configure({
          HTMLAttributes: {
            class: "bg-primary/20 text-primary font-semibold rounded-md px-1",
          },
          suggestion: suggestion as unknown as SuggestionOptions,
        }),
      ],
      content,
      onUpdate: ({ editor }) => {
        onChange(editor.getHTML());
      },
      editable,
    });

    if (
      editor &&
      JSON.stringify(editor.storage.codexStorage.codexItems) !==
        JSON.stringify(codexItems)
    ) {
      editor.storage.codexStorage.codexItems = codexItems;
    }

    useImperativeHandle(ref, () => editor!, [editor]);

    const handleCustomPromptSubmit = () => {
      if (customPrompt.trim()) {
        onTextAction("custom", customPrompt);
        setIsCustomPromptOpen(false);
        setCustomPrompt("");
      }
    };

    return (
      <div className="flex flex-col h-full">
        <MenuBar editor={editor} onSave={onSave} />
        {editor && (
          <BubbleMenu
            editor={editor}
            tippyOptions={{ duration: 100 }}
            className="bg-background border border-border rounded-lg shadow-xl p-1 flex gap-1"
          >
            <Button
              onClick={() => onTextAction("revise")}
              variant="ghost"
              size="sm"
              disabled={isActionLoading}
            >
              <Sparkles className="h-4 w-4 mr-2" /> Revise
            </Button>
            <Button
              onClick={() => onTextAction("extend")}
              variant="ghost"
              size="sm"
              disabled={isActionLoading}
            >
              <WrapText className="h-4 w-4 mr-2" /> Extend
            </Button>
            <Button
              onClick={() => setIsCustomPromptOpen(true)}
              variant="ghost"
              size="sm"
              disabled={isActionLoading}
            >
              <Text className="h-4 w-4 mr-2" /> Custom
            </Button>
          </BubbleMenu>
        )}
        <EditorContent
          editor={editor}
          className="flex-grow overflow-y-auto p-4 border-l border-r border-b border-input rounded-b-md focus:outline-none"
        />
        <Dialog open={isCustomPromptOpen} onOpenChange={setIsCustomPromptOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Custom Edit</DialogTitle>
            </DialogHeader>
            <div className="py-4">
              <Input
                placeholder="e.g., 'Make this more dramatic'"
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCustomPromptSubmit()}
              />
            </div>
            <DialogFooter>
              <Button
                onClick={handleCustomPromptSubmit}
                disabled={!customPrompt.trim()}
              >
                Submit
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
  }
);

RichTextEditor.displayName = "RichTextEditor";

export default RichTextEditor;
